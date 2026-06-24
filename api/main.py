import asyncio
import io
import sys
import uuid
import json
import traceback
from contextlib import redirect_stdout
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

import config
from ui.state import AppState
from graph.state import initial_state

# --- Importers for Agents ---
from agents.requirement_agent import requirement_agent
from agents.qa_review_agent import qa_review_agent
from agents.test_case_agent import test_case_agent
from agents.coverage_agent import coverage_agent
from agents.script_agent import script_agent
from agents.execution_agent import execution_agent
from agents.failure_analysis_agent import failure_analysis_agent
from agents.healing_agent import healing_agent

app = FastAPI(title="QAgent API", description="FastAPI Backend for QAgent Pipeline")

# Enable CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========== Root endpoint for API info ===========
@app.get("/")
async def root():
    """Root endpoint that returns API information."""
    return {
        "service": "QAgent API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "openapi": "/openapi.json",
            "create_session": "POST /api/session",
            "get_session": "GET /api/session/{session_id}",
            "run_step": "POST /api/pipeline/{session_id}/step/{step_id}",
            "upload_brd": "POST /api/brd/upload",
            "logs_websocket": "WS /ws/logs/{session_id}"
        },
        "quick_start": [
            "1. POST /api/session to create a session",
            "2. POST /api/pipeline/{session_id}/step/1 with BRD input to start pipeline",
            "3. GET /api/session/{session_id} to check progress",
            "4. WS /ws/logs/{session_id} to stream logs"
        ]
    }

# In-memory session store
sessions: Dict[str, AppState] = {}
# Active WebSocket connections per session
active_websockets: Dict[str, list[WebSocket]] = {}

class StartPipelineRequest(BaseModel):
    brd_input: str

class SeedStateRequest(BaseModel):
    start_step: int   # 2 = QA Review, 4 = Coverage, 6 = Execution
    input_text: str   # Raw user input to pre-seed the appropriate state field

class StepResponse(BaseModel):
    status: str
    step: int
    data: Dict[str, Any]


def _parse_test_cases_from_text(text: str) -> list[dict]:
    """Parse test cases from JSON or wrap plain text as a single test case."""
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except Exception:
        pass
    # Fallback: split on blank lines to create multiple test cases
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    return [
        {"id": f"TC-{i+1}", "title": f"Test Case {i+1}", "description": block,
         "steps": [], "expected_result": ""}
        for i, block in enumerate(blocks)
    ]


def _safe_encode_state(state_dict: dict) -> dict:
    """
    Safely convert a QAgentState dict to a JSON-serialisable plain dict.

    Uses a json round-trip with a default=str handler which correctly handles
    Path objects, datetimes, and other non-serialisable leaf values while
    preserving all dict/list structure intact.
    """
    try:
        return json.loads(json.dumps(state_dict, default=str))
    except Exception:
        # Last resort: stringify every non-primitive value individually
        return {
            k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v
            for k, v in state_dict.items()
        }

async def broadcast_log(session_id: str, message: str):
    """Send log lines to all connected WebSocket clients for a session."""
    if session_id in active_websockets:
        dead_sockets = []
        for ws in active_websockets[session_id]:
            try:
                await ws.send_json({"type": "log", "data": message})
            except Exception:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            active_websockets[session_id].remove(ws)


async def broadcast_stream_token(session_id: str, agent: str, token: str):
    """Send a single streaming LLM token to WebSocket clients (1.2)."""
    if session_id in active_websockets:
        dead_sockets = []
        for ws in active_websockets[session_id]:
            try:
                await ws.send_json({"type": "stream_token", "agent": agent, "data": token})
            except Exception:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            active_websockets[session_id].remove(ws)

class StreamInterceptor:
    """Intercepts sys.stdout to stream to WebSockets in real-time."""
    def __init__(self, session_id: str, original_stdout, loop):
        self.session_id = session_id
        self.original_stdout = original_stdout
        self.loop = loop

    def write(self, text: str):
        try:
            self.original_stdout.write(text)
        except UnicodeEncodeError:
            self.original_stdout.write(text.encode('ascii', 'replace').decode('ascii'))
        stripped = text.strip()
        if stripped:
            if self.session_id in sessions:
                sessions[self.session_id].log_lines.append(stripped)
            # Use threadsafe since this is called from a threadpool
            asyncio.run_coroutine_threadsafe(
                broadcast_log(self.session_id, stripped),
                self.loop
            )

    def flush(self):
        self.original_stdout.flush()
        
    def isatty(self):
        return False

def _run_agent_sync(session_id: str, agent_fn, state_dict: dict, loop) -> dict:
    from agents.stream_context import set_token_callback, clear_token_callback

    original_stdout = sys.stdout
    sys.stdout = StreamInterceptor(session_id, original_stdout, loop)

    # 1.2: register per-thread streaming callback so LLM tokens flow to WebSocket
    agent_name = getattr(agent_fn, "__name__", "agent")

    def _stream_cb(aname: str, token: str) -> None:
        asyncio.run_coroutine_threadsafe(
            broadcast_stream_token(session_id, aname, token),
            loop,
        )

    set_token_callback(_stream_cb, agent_name=agent_name)
    try:
        return agent_fn(state_dict)
    finally:
        sys.stdout = original_stdout
        clear_token_callback()

async def _run_agent_async(session_id: str, agent_fn, state_dict: dict) -> dict:
    # Run the blocking agent function in a threadpool to avoid blocking FastAPI event loop
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_agent_sync, session_id, agent_fn, state_dict, loop)

@app.post("/api/session", status_code=201)
async def create_session():
    """Create a new QAgent pipeline session."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = AppState()
    active_websockets[session_id] = []
    return {"session_id": session_id}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    state = sessions[session_id]
    return {
        "step": state.step,
        "state_data": state.state,
        "log_lines": state.log_lines
    }

@app.post("/api/pipeline/{session_id}/seed", status_code=200)
async def seed_pipeline(session_id: str, req: SeedStateRequest):
    """
    Pre-seed the pipeline state to start from an intermediate agent.

    Entry points:
      - start_step=2 → QA Review Agent   (seeds user_stories from plain text)
      - start_step=3 → Test Case Agent   (seeds reviewed_stories from plain text)
      - start_step=4 → Coverage Agent    (seeds test_cases from JSON or text)
      - start_step=5 → Script Agent      (seeds test_cases + empty coverage_gaps)
      - start_step=6 → Execution Agent   (seeds test_scripts from newline-separated paths)
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if req.start_step < 2 or req.start_step > 6:
        raise HTTPException(status_code=400, detail="start_step must be between 2 and 6")
    if not req.input_text.strip():
        raise HTTPException(status_code=400, detail="input_text is required")

    state_dict = initial_state("")

    if req.start_step in (2, 3):
        # Seed user stories from plain text requirements
        base_story = {
            "id": "US-1",
            "title": "User Provided Requirements",
            "description": req.input_text,
            "acceptance_criteria": []
        }
        state_dict["user_stories"] = [base_story]
        if req.start_step == 3:
            state_dict["reviewed_stories"] = [{**base_story, "review_notes": "Pre-seeded by user"}]

    elif req.start_step in (4, 5):
        # Seed test cases from JSON array or plain text
        test_cases = _parse_test_cases_from_text(req.input_text)
        state_dict["test_cases"] = test_cases
        if req.start_step == 5:
            state_dict["coverage_gaps"] = []

    elif req.start_step == 6:
        # Seed test script file paths (one per line)
        paths = [p.strip() for p in req.input_text.splitlines() if p.strip()]
        if not paths:
            raise HTTPException(status_code=400, detail="No valid file paths found in input_text")
        state_dict["test_scripts"] = paths

    app_state = sessions[session_id]
    app_state.state = state_dict
    # Set step to start_step-1 so the next runNextStep call runs start_step
    app_state.step = req.start_step - 1

    await broadcast_log(session_id, f"⚡ Pipeline seeded — starting from Step {req.start_step} ({['','Requirement','QA Review','Test Case','Coverage','Script','Execution'][req.start_step]} Agent)")

    safe_data = _safe_encode_state(state_dict)
    return JSONResponse(content={
        "status": "seeded",
        "start_step": req.start_step,
        "current_step": req.start_step - 1,
        "data": safe_data,
    })

@app.post("/api/pipeline/{session_id}/step/{step_id}")
async def run_pipeline_step(session_id: str, step_id: int, req: StartPipelineRequest = None):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    app_state = sessions[session_id]
    state_dict = app_state.state

    # Broadcast step start
    await broadcast_log(session_id, f"--- Starting Step {step_id} ---")

    try:
        if step_id == 1:
            if not req or not req.brd_input:
                raise HTTPException(status_code=400, detail="BRD input required for step 1")
            app_state.brd_input = req.brd_input
            state_dict = initial_state(req.brd_input)
            state_dict = await _run_agent_async(session_id, requirement_agent, state_dict)
        elif step_id == 2:
            state_dict = await _run_agent_async(session_id, qa_review_agent, state_dict)
        elif step_id == 3:
            state_dict = await _run_agent_async(session_id, test_case_agent, state_dict)
        elif step_id == 4:
            state_dict = await _run_agent_async(session_id, coverage_agent, state_dict)
        elif step_id == 5:
            state_dict = await _run_agent_async(session_id, script_agent, state_dict)
        elif step_id == 6:
            state_dict = await _run_agent_async(session_id, execution_agent, state_dict)
        elif step_id == 7:
            state_dict = await _run_agent_async(session_id, failure_analysis_agent, state_dict)
        elif step_id == 8:
            failures = [r for r in state_dict.get("failure_analysis", []) if r.get("is_healable")]
            if failures:
                state_dict = await _run_agent_async(session_id, healing_agent, state_dict)
            else:
                await broadcast_log(session_id, "Healing Agent: no healable failures — skipped.")
        else:
            raise HTTPException(status_code=400, detail="Invalid step ID")

        app_state.state = state_dict
        app_state.step = step_id
        
        await broadcast_log(session_id, f"--- Completed Step {step_id} ---")
        safe_data = _safe_encode_state(state_dict)
        return JSONResponse(content={"status": "success", "step": step_id, "data": safe_data})

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions unchanged (don't wrap in 500)
        raise
    except Exception as e:
        tb = traceback.format_exc()
        print(f"\n[X] STEP {step_id} EXCEPTION:\n{tb}", flush=True)
        await broadcast_log(session_id, f"❌ Error in Step {step_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# BRD File Upload — extract plain text from PDF / DOCX / XLSX / XLS / TXT / CSV
# ---------------------------------------------------------------------------

ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument",  # .docx / .xlsx
    "application/vnd.ms-excel",                        # .xls
    "application/msword",                              # .doc (best-effort)
    "text/",                                           # .txt / .csv
)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _extract_text(filename: str, data: bytes) -> str:
    """Return plain text extracted from the uploaded file bytes."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        import pdfplumber, io as _io
        text_parts: list[str] = []
        with pdfplumber.open(_io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)

    if ext == "docx":
        import docx, io as _io
        doc = docx.Document(_io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if ext in ("xlsx", "xls"):
        import openpyxl, io as _io
        wb = openpyxl.load_workbook(_io.BytesIO(data), read_only=True, data_only=True)
        rows: list[str] = []
        for sheet in wb.worksheets:
            rows.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(cells):
                    rows.append("\t".join(cells))
        return "\n".join(rows)

    if ext in ("txt", "csv", "md"):
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue

    # Fallback: try raw UTF-8 decode (handles .doc best-effort)
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: .{ext}")


@app.post("/api/brd/upload")
async def upload_brd(file: UploadFile = File(...)):
    """Accept a BRD file and return its text content."""
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    filename = file.filename or "upload"
    text = _extract_text(filename, data)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the file")

    return {"filename": filename, "text": text, "characters": len(text)}


@app.websocket("/ws/logs/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in active_websockets:
        active_websockets[session_id] = []
    
    active_websockets[session_id].append(websocket)
    
    # Send historical logs first
    if session_id in sessions:
        for line in sessions[session_id].log_lines:
            await websocket.send_json({"type": "log", "data": line})
            
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        active_websockets[session_id].remove(websocket)
