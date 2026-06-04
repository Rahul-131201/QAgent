# 🤖 QAgent — AI-Powered QA Automation Pipeline

QAgent is a **LangGraph multi-agent system** that converts a Business Requirement Document (BRD) into executable Playwright/pytest test scripts, runs them, analyses failures, and self-heals in a feedback loop — all orchestrated through a **Next.js + FastAPI** web interface with real-time streaming output.

The LLM layer uses a **5-provider fallback chain** (GPT-4o-mini → Groq → OpenRouter → Gemini → HuggingFace) with automatic rate-limit recovery, structured JSON outputs, and live token streaming.

---

## Architecture

```
BRD Input (text / PDF / DOCX / XLSX / TXT)
         │
         ▼  [FAISS BRD semantic cache — skip LLM if cosine ≥ 0.97]
 ┌─────────────────────┐
 │  Requirement Agent  │ ── GPT-4o-mini / Groq (json_mode)
 │  (BRD → user stories│
 └────────┬────────────┘
          │
          ▼  [parallel — one thread per story]
 ┌─────────────────────┐
 │   QA Review Agent   │ ── _FallbackChainLLM (json_mode)
 │  (ambiguity + AC    │
 │   gap detection)    │
 └────────┬────────────┘
          │
          ▼
 ┌─────────────────────┐
 │  Test Case Agent    │ ── _FallbackChainLLM (json_mode, retry on parse fail)
 │  (positive/negative │
 │   /edge test cases) │
 └────────┬────────────┘
          │
          ▼  [parallel — one thread per story; guaranteed 1 TC per gap]
 ┌─────────────────────┐
 │   Coverage Agent    │ ── _FallbackChainLLM (json_mode)
 │  (boundary/security │
 │   /perf/a11y gaps)  │
 └────────┬────────────┘
          │
          ▼
 ┌─────────────────────┐
 │    Script Agent     │ ── _FallbackChainLLM
 │  (pytest/Playwright │
 │   code generation)  │
 └────────┬────────────┘
          │
          ▼
 ┌─────────────────────┐
 │  Execution Agent    │ ── subprocess + pytest-json-report
 │  (runs test files,  │
 │   captures results) │
 └────────┬────────────┘
          │
          ▼
 ┌─────────────────────┐
 │  Failure Analysis   │ ── _FallbackChainLLM + FAISS memory
 │  (root cause class- │
 │   ification)        │
 └────────┬────────────┘
          │
          ▼  [stall detection — skips duplicate patch hashes]
 ┌─────────────────────┐
 │   Healing Agent     │ ── _FallbackChainLLM + FAISS few-shot examples
 │  (auto-fix broken   │
 │   scripts)          │
 └────────┬────────────┘
          │
          ▼
 🔁  Feedback Loop  (LangGraph conditional edges)
     ├─ all passed    → END
     ├─ logic errors  → loop back to QA Review Agent
     ├─ script errors → loop back to Script Agent
     └─ iteration ≥ 3 → END (max retries reached)
```

### LLM Fallback Chain

Every agent routes calls through `_FallbackChainLLM`, which tries providers in order and automatically skips any that hit a rate limit or quota:

```
GPT-4o-mini  →  Groq (llama-3.3-70b)  →  OpenRouter (llama-3.3-70b)  →  Gemini 2.0 Flash  →  HuggingFace (Qwen2.5-72B)
```

All agents use **`json_mode=True`** which binds `response_format={"type":"json_object"}` for OpenAI/Groq/OpenRouter, ensuring parse-reliable structured output.

### Component Overview

| Component | File | Notes |
|---|---|---|
| Requirement Agent | `agents/requirement_agent.py` | BRD → user stories; FAISS BRD cache |
| QA Review Agent | `agents/qa_review_agent.py` | Story validation; runs in parallel threads |
| Test Case Agent | `agents/test_case_agent.py` | TC generation; json_mode + retry on parse fail |
| Coverage Agent | `agents/coverage_agent.py` | Gap detection; guaranteed 1 TC per gap; parallel |
| Script Agent | `agents/script_agent.py` | Playwright/pytest code generation |
| Execution Agent | `agents/execution_agent.py` | subprocess test runner |
| Failure Analysis Agent | `agents/failure_analysis_agent.py` | Root cause classification + FAISS |
| Healing Agent | `agents/healing_agent.py` | Script self-healing; stall detection via SHA-256 |
| Stream Context | `agents/stream_context.py` | Thread-local LLM streaming callback |
| State Graph | `graph/workflow.py` | LangGraph StateGraph with conditional feedback |
| Shared State | `graph/state.py` | `QAgentState` TypedDict (incl. `healing_hashes`) |
| Vector Memory | `memory/faiss_store.py` | FAISS namespaces: test_cases, failures, fixes, brd_cache |
| FastAPI Backend | `api/main.py` | REST + WebSocket; BRD file upload endpoint |
| Next.js Frontend | `frontend/` | Pipeline UI at `/pipeline`; landing page at `/` |

---

## Project Structure

```
QAgent/
├── agents/
│   ├── requirement_agent.py      ← BRD → user stories (FAISS BRD cache)
│   ├── qa_review_agent.py        ← story validation + enrichment (parallel)
│   ├── test_case_agent.py        ← manual test case generation (json_mode)
│   ├── coverage_agent.py         ← gap detection + guaranteed TC per gap (parallel)
│   ├── script_agent.py           ← Playwright/pytest code generation
│   ├── execution_agent.py        ← subprocess test runner
│   ├── failure_analysis_agent.py ← root cause classification
│   ├── healing_agent.py          ← script self-healing (stall detection)
│   ├── stream_context.py         ← thread-local LLM streaming callback
│   └── utils.py                  ← shared helpers
├── api/
│   └── main.py                   ← FastAPI: REST steps + WebSocket + BRD upload
├── frontend/                     ← Next.js 15 + React 19 + Tailwind v4
│   └── src/
│       ├── app/
│       │   ├── page.tsx          ← Landing page
│       │   └── pipeline/
│       │       └── page.tsx      ← Pipeline UI (live log stream, data viewer)
│       └── components/           ← Navbar, ParticleField, ThreeAvatar, …
├── graph/
│   ├── state.py                  ← QAgentState TypedDict
│   └── workflow.py               ← LangGraph StateGraph
├── memory/
│   └── faiss_store.py            ← FAISS vector memory (4 namespaces)
├── tests/
│   ├── generated/                ← AI-generated test scripts
│   │   └── healed/               ← Self-healed script variants
│   └── test_agents.py            ← pytest unit tests for agents
├── config.py                     ← Central config + _FallbackChainLLM
├── requirements.txt
├── Makefile
├── start_dev.ps1                 ← Starts both uvicorn + Next.js dev server
└── .env
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- At least one LLM API key (OpenAI, Groq, Google Gemini, OpenRouter, or HuggingFace)

### 1. Clone and install

```bash
git clone https://github.com/your-org/qagent.git
cd qagent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

make install
# equivalent to:
#   pip install -r requirements.txt
#   playwright install chromium

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the keys for the providers you want to use (at least one is required):

```env
# Primary provider (recommended)
GPT_API_KEY=sk-...            # OpenAI / GPT-4o-mini

# Fallback providers (optional but recommended for resilience)
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...
OPENROUTER_API_KEY=sk-or-...
HUGGINGFACE_API_KEY=hf_...
```

### 3. Start the development servers

**Option A — single command (Windows PowerShell):**

```powershell
.\start_dev.ps1
```

**Option B — two separate terminals:**

```bash
# Terminal 1 — FastAPI backend (port 8000)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Next.js frontend (port 3000)
cd frontend
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Run tests

```bash
make test
# equivalent to:
#   pytest tests/ -v --tb=short
```

### 5. Lint

```bash
make lint
# equivalent to:
#   ruff check .
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GPT_API_KEY` / `OPENAI_API_KEY` | ✅ (one provider required) | — | OpenAI key for GPT-4o-mini (primary) |
| `GROQ_API_KEY` | Recommended | — | Groq key — first fallback |
| `GOOGLE_API_KEY` | Optional | — | Google Gemini key — third fallback |
| `OPENROUTER_API_KEY` | Optional | — | OpenRouter key — second fallback |
| `HUGGINGFACE_API_KEY` | Optional | — | HuggingFace key — last-resort fallback |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model name |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model name |
| `OPENROUTER_MODEL` | No | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter model name |
| `HF_MODEL` | No | `Qwen/Qwen2.5-72B-Instruct` | HuggingFace model name |
| `MAX_ITERATIONS` | No | `3` | Max feedback loop iterations |
| `LLM_TEMPERATURE` | No | `0.2` | LLM sampling temperature |
| `LLM_MAX_RETRIES` | No | `2` | JSON parse retry attempts per agent |

---

## API Reference

The FastAPI backend runs on port **8000** and exposes:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/pipeline/{session_id}/step/{step_id}` | Execute one pipeline step (body: `{"brd_input": "..."}`) |
| `POST` | `/api/brd/upload` | Upload a BRD file (PDF / DOCX / XLSX / XLS / TXT / CSV) → returns extracted text |
| `GET` | `/api/pipeline/{session_id}/status` | Get current session state snapshot |
| `WebSocket` | `/ws/logs/{session_id}` | Real-time log + LLM token stream |

### WebSocket message types

```json
{ "type": "log",          "data": "✅ Step 3 complete" }
{ "type": "stream_token", "agent": "requirement_agent", "data": "..." }
{ "type": "error",        "data": "..." }
```

---

## Using QAgent Programmatically

```python
from graph.workflow import run_pipeline

brd = """
Users must be able to register with email and password.
Passwords must be at least 8 characters and contain one uppercase letter.
"""

final_state = run_pipeline(brd)

print(f"Status    : {final_state['status']}")
print(f"Iterations: {final_state['iteration']}")
print(f"Test cases: {len(final_state['test_cases'])}")
print(f"Scripts   : {final_state['test_scripts']}")
```

---

## Key Features

### 1.1 Parallel Agent Execution
`QA Review Agent` and `Coverage Agent` process each user story in a `ThreadPoolExecutor`, cutting wall-clock time proportionally to story count.

### 1.2 Real-time LLM Token Streaming
Every LLM call streams tokens via a thread-local callback (`agents/stream_context.py`) → WebSocket → terminal UI. Partial output appears character-by-character in the browser while generation is still in progress.

### 1.3 Smart Self-Healing Stall Detection
The Healing Agent computes a SHA-256 prefix hash of each patched script. If the same hash was already tried for that test case, the patch is silently skipped, preventing infinite loops on unfixable failures.

### 1.5 FAISS BRD Semantic Cache
Before calling any LLM, the Requirement Agent queries the FAISS `brd_cache` namespace. If a semantically identical BRD has been processed before (cosine similarity ≥ 0.97), the cached user stories are returned instantly with no LLM call.

### 1.6 Structured JSON Outputs
All agents invoke the LLM with `json_mode=True`, which binds `response_format={"type":"json_object"}` on OpenAI / Groq / OpenRouter. This eliminates markdown fences and parse failures.

### 1.7 Guaranteed Coverage TC
The Coverage Agent validates that every identified coverage gap has exactly one derived test case. If the count doesn't match, a `ValueError` is raised and the agent retries, ensuring no gap is ever left without a test.

### BRD File Upload
The `/api/brd/upload` endpoint accepts **PDF, DOCX, XLSX, XLS, TXT, and CSV** files (max 10 MB) and returns the extracted plain text for use as pipeline input. The pipeline UI includes a drag-and-drop upload zone.

---

## How to Add a New Agent

1. **Create the agent file** in `agents/my_agent.py`:

```python
from graph.state import QAgentState

def my_agent(state: QAgentState) -> QAgentState:
    data = state["some_field"]
    # ... do work ...
    return {**state, "some_output_field": result}
```

2. **Register the node** in `graph/workflow.py`:

```python
from agents.my_agent import my_agent

graph.add_node("my_agent", my_agent)
graph.add_edge("previous_node", "my_agent")
graph.add_edge("my_agent", "next_node")
```

3. **Add the output field** to `QAgentState` in `graph/state.py` and initialise it in `initial_state()`.

4. **Write a unit test** in `tests/test_agents.py` using `@patch` to mock the LLM call.

---

## Known Limitations

| Limitation | Details |
|---|---|
| **Single-page Playwright scripts** | The Script Agent generates tests assuming a single-page context. Multi-page flows (e.g. OAuth redirects) may need manual adjustment. |
| **FAISS memory is in-process** | The FAISS index is persisted to disk but loaded once per process. Concurrent writes from multiple workers are not supported. |
| **Scanned PDF quality** | `pdfplumber` may produce noisy text for scanned or image-based PDFs. Use text-based PDFs for best results. |
| **Token limits on large BRDs** | Very large BRDs (>10,000 tokens) may be truncated by the LLM context window. Consider splitting large documents. |
| **No UI authentication** | The Next.js app has no authentication. Do not expose it on a public network with real API keys in the backend. |
| **Streaming fallback** | If a provider doesn't support `stream()`, the agent falls back to a blocking `invoke()` call and the live stream is skipped for that turn. |

---

## Roadmap

- [ ] **CI/CD integration** — GitHub Actions workflow to run QAgent on every PR and post results as a comment
- [ ] **Jira/Linear sync** — automatically create test cases as tickets from `test_cases` state
- [ ] **Multi-browser support** — extend Script Agent to generate Firefox and WebKit variants
- [ ] **LangSmith tracing** — full agent trace observability via LangSmith
- [ ] **Persistent shared memory** — replace in-process FAISS singleton with Pinecone / Weaviate for multi-worker support
- [ ] **Human-in-the-loop** — add a manual approval checkpoint between QA Review and Test Case generation
- [ ] **Custom embedding models** — allow swapping `all-MiniLM-L6-v2` for domain-specific embeddings
- [ ] **Test result history** — persist pass/fail trends across pipeline runs in a lightweight DB

---

## License

MIT
