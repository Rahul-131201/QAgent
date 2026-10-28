<div align="center">

<img src="https://img.shields.io/badge/QAgent-AI%20QA%20Automation-6366f1?style=for-the-badge&logo=robot&logoColor=white" alt="QAgent" height="60"/>

# 🤖 QAgent — Autonomous AI-Powered QA Pipeline

**Transform a Business Requirement Document into a self-healing Playwright test suite — fully autonomous, end-to-end.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.47+-2EAD33?style=flat-square&logo=playwright&logoColor=white)](https://playwright.dev)
[![FAISS](https://img.shields.io/badge/FAISS-Vector%20Memory-FF6B35?style=flat-square&logo=meta&logoColor=white)](https://faiss.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

<br/>

> **9 autonomous AI agents** orchestrated by LangGraph. One BRD goes in.  
> A complete, executed, and self-healed Playwright test suite comes out.

<br/>

[🚀 Quick Start](#-quick-start) · [🏗️ Architecture](#%EF%B8%8F-architecture) · [🤖 Agents](#-agent-pipeline) · [🔌 API Reference](#-api-reference) · [⚙️ Configuration](#%EF%B8%8F-configuration) · [🗺️ Roadmap](#%EF%B8%8F-roadmap)

</div>

---

## ✨ What Is QAgent?

QAgent is a **LangGraph multi-agent system** that orchestrates a 9-step autonomous pipeline:

1. Parses your **Business Requirement Document** (BRD)
2. Generates **user stories** with Given-When-Then acceptance criteria
3. Validates and enriches stories through a **QA review pass**
4. Produces **structured test cases** (positive, negative, edge scenarios)
5. Identifies **coverage gaps** across boundary, security, performance, and a11y layers
6. Writes production-ready **Playwright/pytest automation scripts** to disk
7. **Executes** the generated test suite end-to-end
8. **Classifies failures** across 11 root-cause categories using LLM + FAISS
9. **Self-heals** broken scripts and routes back through the loop — up to 3 times

All of this runs through a **beautiful Next.js dashboard** with real-time WebSocket log streaming and live LLM token output.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QAgent Pipeline Architecture                        │
└─────────────────────────────────────────────────────────────────────────────┘

  BRD Input (text / PDF / DOCX / XLSX / TXT / CSV)
           │
           ▼  ┌─ FAISS BRD Cache ─────────────────────────────────────────┐
  ┌────────────────────┐  cosine ≥ 0.97 → instant return (zero LLM cost)  │
  │  Requirement Agent │ ── Groq llama-3.3-70b / json_mode                 │
  │  BRD → User Stories│    7-field schema + Pydantic validation            │
  └────────┬───────────┘    GWT + Fibonacci estimation validators           │
           │                                                                │
           ▼  [parallel — ThreadPoolExecutor, one thread per story]         │
  ┌────────────────────┐                                                    │
  │   QA Review Agent  │ ── _FallbackChainLLM / json_mode                  │
  │  Ambiguity + AC    │    Confidence scoring, needs_review flag           │
  │  gap detection     │                                                    │
  └────────┬───────────┘                                                    │
           │                                                                │
           ▼                                                                │
  ┌────────────────────┐                                                    │
  │  Test Case Agent   │ ── _FallbackChainLLM / json_mode                  │
  │  Positive/Negative │    Retry on JSON parse fail                        │
  │  + Edge test cases │                                                    │
  └────────┬───────────┘                                                    │
           │                                                                │
           ▼  [parallel — ThreadPoolExecutor; guaranteed 1 TC per gap]      │
  ┌────────────────────┐                                                    │
  │   Coverage Agent   │ ── _FallbackChainLLM / json_mode                  │
  │  Boundary, security│    Validates TC count matches gap count            │
  │  perf, a11y gaps   │                                                    │
  └────────┬───────────┘                                                    │
           │                                                                │
           ▼                                                                │
  ┌────────────────────┐                                                    │
  │    Script Agent    │ ── _FallbackChainLLM                               │
  │  pytest + Playwright   Generates full test files to disk                │
  │  code generation   │                                                    │
  └────────┬───────────┘                                                    │
           │                                                                │
           ▼                                                                │
  ┌────────────────────┐                                                    │
  │  Execution Agent   │ ── subprocess + pytest-json-report                 │
  │  Runs test files   │    Captures output, duration, error messages       │
  └────────┬───────────┘                                                    │
           │                                                                │
           ▼                                                                │
  ┌────────────────────┐                                                    │
  │  Failure Analysis  │ ── _FallbackChainLLM + FAISS failure memory        │
  │  Root cause class- │    11 error categories, is_healable flag           │
  │  ification        │                                                    │
  └────────┬───────────┘                                                    │
           │                                                                │
           ▼  [stall detection — SHA-256 patch hash deduplication]          │
  ┌────────────────────┐                                                    │
  │   Healing Agent    │ ── _FallbackChainLLM + FAISS few-shot fixes        │
  │  Auto-fix broken   │    ast.parse() syntax validation                   │
  │  scripts          │    Writes to tests/generated/healed/               │
  └────────┬───────────┘                                                    │
           │                                                                └
           ▼
  🔁  LangGraph Conditional Routing
      ├─ all_passed              → END  ✅
      ├─ logic_error / ambiguous → qa_review  (full loop from story review)
      ├─ design_error            → test_case  (regenerate test cases only)
      ├─ script_error (healable) → script     (regenerate scripts only)
      └─ iteration ≥ 3           → END  ⚠️ (max retries reached)
```

### 🔗 LLM Fallback Chain

Every agent routes through `_FallbackChainLLM` — a 5-provider waterfall with automatic rate-limit recovery:

```
GPT-4o-mini → Groq (llama-3.3-70b) → OpenRouter (llama-3.3-70b) → Gemini 2.0 Flash → HuggingFace (Qwen2.5-72B)
```

- On **429 / quota / auth errors** → silently skip to next provider
- On **any other error** → re-raise immediately  
- Supports both **streaming** (via `llm.stream()`) and **non-streaming** fallback
- **`json_mode=True`** binds `response_format={"type":"json_object"}` on OpenAI/Groq/OpenRouter for parse-reliable structured output

---

## 🤖 Agent Pipeline

| # | Agent | File | Key Capability |
|---|-------|------|----------------|
| 1 | **Requirement Agent** | [`agents/requirement_agent.py`](agents/requirement_agent.py) | BRD → 7-field user stories; FAISS BRD semantic cache (cosine ≥ 0.97); Pydantic GWT + Fibonacci validators |
| 2 | **QA Review Agent** | [`agents/qa_review_agent.py`](agents/qa_review_agent.py) | Ambiguity detection, completeness scoring, `needs_review` flag; parallel ThreadPoolExecutor |
| 3 | **Test Case Agent** | [`agents/test_case_agent.py`](agents/test_case_agent.py) | Positive / negative / edge TC generation; `json_mode` with retry on parse fail |
| 4 | **Coverage Agent** | [`agents/coverage_agent.py`](agents/coverage_agent.py) | Boundary, security, performance, a11y gap detection; guaranteed 1 TC per gap; parallel |
| 5 | **Script Agent** | [`agents/script_agent.py`](agents/script_agent.py) | Playwright/pytest script generation; writes `.py` files to `tests/generated/` |
| 6 | **Execution Agent** | [`agents/execution_agent.py`](agents/execution_agent.py) | subprocess + `pytest-json-report`; captures status, duration, error messages per TC |
| 7 | **Failure Analysis Agent** | [`agents/failure_analysis_agent.py`](agents/failure_analysis_agent.py) | Root-cause classification across 11 categories; FAISS failure memory retrieval |
| 8 | **Healing Agent** | [`agents/healing_agent.py`](agents/healing_agent.py) | LLM-guided script repair; FAISS few-shot fixes; SHA-256 stall detection; `ast.parse()` syntax check |
| — | **Stream Context** | [`agents/stream_context.py`](agents/stream_context.py) | Thread-local LLM token callback → WebSocket → browser |

---

## 💡 Key Features

<table>
<tr>
<td width="50%">

### ⚡ Real-time Token Streaming
Every LLM generation streams tokens via a thread-local callback → FastAPI WebSocket → Next.js UI. Watch responses appear character-by-character live in the browser.

### 🧠 FAISS Semantic Memory (4 Namespaces)
```
brd_cache   ← BRD → user_stories (cosine ≥ 0.97 skip)
test_cases  ← indexed past test cases
failures    ← indexed failure records
fixes       ← indexed healing strategies
```
Embeddings use `all-MiniLM-L6-v2` (local, no API key needed).

### 🩹 Smart Self-Healing with Stall Detection
The Healing Agent computes a **SHA-256 prefix hash** of each generated patch. If the same hash was already tried for that test case in a previous iteration, the patch is skipped, preventing infinite loops on unfixable failures.

</td>
<td width="50%">

### 🔀 4-Way Conditional Routing
LangGraph conditional edges intelligently route after healing:
- **Logic errors** → back to QA Review (full loop)
- **Design errors** → back to Test Case generation
- **Script errors** → back to Script Agent only
- **All passed / max iter** → END

### 🔁 Parallel Execution
`QA Review Agent` and `Coverage Agent` run each user story in a `ThreadPoolExecutor`, cutting wall-clock time proportionally to story count.

### 📄 Multi-Format BRD Upload
The `/api/brd/upload` endpoint accepts:
`PDF` · `DOCX` · `XLSX / XLS` · `TXT` · `CSV` · `MD`  
(max 10 MB) — drag-and-drop in the pipeline UI.

### ✅ Guaranteed Coverage
Coverage Agent validates that every identified gap has exactly one derived TC. Mismatch → `ValueError` → automatic retry.

</td>
</tr>
</table>

---

## 🗂️ Project Structure

```
QAgent/
├── agents/                           ← All AI agent logic
│   ├── requirement_agent.py          ← BRD → user stories (FAISS BRD cache, Pydantic validation)
│   ├── qa_review_agent.py            ← Story validation + enrichment (parallel)
│   ├── test_case_agent.py            ← Test case generation (json_mode + retry)
│   ├── coverage_agent.py             ← Gap detection + guaranteed TC per gap (parallel)
│   ├── script_agent.py               ← Playwright/pytest code generation
│   ├── execution_agent.py            ← subprocess test runner (pytest-json-report)
│   ├── failure_analysis_agent.py     ← Root cause classification + FAISS lookup
│   ├── healing_agent.py              ← Script self-healing (stall detection, FAISS few-shot)
│   ├── stream_context.py             ← Thread-local LLM streaming callback
│   └── utils.py                      ← Shared helpers (JSON extraction, etc.)
│
├── api/
│   └── main.py                       ← FastAPI: REST steps + WebSocket + BRD file upload
│
├── frontend/                         ← Next.js 15 + React 19 + Tailwind v4
│   └── src/
│       ├── app/
│       │   ├── page.tsx              ← Animated landing page (Framer Motion + ParticleField)
│       │   └── pipeline/
│       │       └── page.tsx          ← Pipeline UI (live log stream, data viewer, upload)
│       └── components/               ← Navbar, ParticleField, ThreeAvatar, …
│
├── graph/
│   ├── state.py                      ← QAgentState TypedDict (15 fields, run_id → pass_rate)
│   └── workflow.py                   ← LangGraph StateGraph + step timings + 4-way routing
│
├── memory/
│   └── faiss_store.py                ← QAgentMemory: 4 FAISS namespaces, BRD semantic cache
│
├── tests/
│   ├── generated/                    ← AI-generated Playwright test scripts (output)
│   │   └── healed/                   ← Self-healed script variants
│   └── test_agents.py                ← pytest unit tests for all agents
│
├── outputs/                          ← Pipeline JSON outputs per run
│   ├── user_stories.json
│   ├── reviewed_stories.json
│   └── test_cases.json
│
├── config.py                         ← Central config + _FallbackChainLLM (5-provider chain)
├── requirements.txt                  ← Python dependencies
├── Makefile                          ← install / run / test / lint
├── start_dev.ps1                     ← Starts uvicorn + Next.js dev server (Windows)
├── build.sh                          ← Production build script
├── sample_brd.md                     ← Example BRD (TodoMVC)
├── .env.example                      ← Environment variable template
└── setup.md                          ← Detailed setup guide
```

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| LLM API key | At least one (OpenAI, Groq, Gemini, OpenRouter, or HuggingFace) |

### 1 — Clone & Install

```bash
git clone https://github.com/your-username/qagent.git
cd qagent

# Create and activate virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# Install Python dependencies + Playwright browser
make install
# Equivalent to:
#   pip install -r requirements.txt
#   playwright install chromium

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 2 — Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — at minimum, set **one** LLM provider:

```env
# ── Primary Provider (recommended) ──────────────────────────────────────────
GPT_API_KEY=sk-...                        # OpenAI GPT-4o-mini

# ── Fallback Providers (optional but recommended for resilience) ─────────────
GROQ_API_KEY=gsk_...                      # Groq — llama-3.3-70b
GOOGLE_API_KEY=AIza...                    # Google Gemini 2.0 Flash
OPENROUTER_API_KEY=sk-or-...              # OpenRouter
HUGGINGFACE_API_KEY=hf_...                # HuggingFace Qwen2.5-72B

# ── Pipeline Tuning (optional) ───────────────────────────────────────────────
MAX_ITERATIONS=3                          # max self-healing loops
LLM_TEMPERATURE=0.2                       # LLM sampling temperature
LLM_MAX_RETRIES=2                         # JSON parse retry attempts
```

### 3 — Start the Development Servers

**Option A — Single command (Windows PowerShell):**
```powershell
.\start_dev.ps1
```

**Option B — Two separate terminals:**
```bash
# Terminal 1 — FastAPI backend (http://localhost:8000)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Next.js frontend (http://localhost:3000)
cd frontend && npm run dev
```

Open **[http://localhost:3000](http://localhost:3000)** → click **Launch Pipeline** → paste your BRD → run!

### 4 — Run Tests

```bash
make test
# Equivalent to: pytest tests/ -v --tb=short
```

### 5 — Lint

```bash
make lint
# Equivalent to: ruff check .
```

---

## 🐍 Programmatic Usage

```python
from graph.workflow import run_pipeline

brd = """
Users must be able to register with an email address and password.
Passwords must be at least 8 characters and contain one uppercase letter.
Users should receive a confirmation email after successful registration.
"""

final_state = run_pipeline(brd)

print(f"Status     : {final_state['status']}")           # all_passed | partial_pass | failed
print(f"Iterations : {final_state['iteration']}")         # 1-3
print(f"Pass rate  : {final_state['pass_rate']:.0%}")     # 0% – 100%
print(f"Stories    : {len(final_state['user_stories'])}")
print(f"Test cases : {len(final_state['test_cases'])}")
print(f"Scripts    : {final_state['test_scripts']}")       # file paths
print(f"Timings    : {final_state['step_timings']}")       # per-agent wall-clock seconds
```

---

## 🔌 API Reference

The FastAPI backend runs on port **8000** and serves an interactive Swagger UI at `/docs`.

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/session` | Create a new pipeline session → returns `session_id` |
| `GET` | `/api/session/{session_id}` | Get current step, state snapshot, and log lines |
| `POST` | `/api/pipeline/{session_id}/step/{step_id}` | Execute one pipeline step (body: `{"brd_input": "..."}` for step 1) |
| `POST` | `/api/pipeline/{session_id}/seed` | Pre-seed state to start from an intermediate agent (steps 2–6) |
| `POST` | `/api/brd/upload` | Upload BRD file → returns extracted plain text |
| `WebSocket` | `/ws/logs/{session_id}` | Real-time log + LLM token stream |

### Step IDs

| Step | Agent |
|------|-------|
| `1` | Requirement Agent |
| `2` | QA Review Agent |
| `3` | Test Case Agent |
| `4` | Coverage Agent |
| `5` | Script Agent |
| `6` | Execution Agent |
| `7` | Failure Analysis Agent |
| `8` | Healing Agent |

### WebSocket Message Types

```json
{ "type": "log",          "data": "✅ Step 3 complete" }
{ "type": "stream_token", "agent": "requirement_agent", "data": "As a user..." }
{ "type": "error",        "data": "Rate limit hit on Groq — switching to Gemini" }
```

### BRD Upload Example

```bash
curl -X POST http://localhost:8000/api/brd/upload \
  -F "file=@my_requirements.pdf"

# Response:
# { "filename": "my_requirements.pdf", "text": "...", "characters": 4821 }
```

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GPT_API_KEY` / `OPENAI_API_KEY` | — | OpenAI key for GPT-4o-mini **(primary)** |
| `GROQ_API_KEY` | — | Groq key — 1st fallback |
| `GOOGLE_API_KEY` | — | Google Gemini key — 2nd fallback |
| `OPENROUTER_API_KEY` | — | OpenRouter key — 3rd fallback |
| `HUGGINGFACE_API_KEY` | — | HuggingFace key — last-resort fallback |
| `USE_GEMINI` | `true` | Include Gemini in the fallback chain |
| `USE_HUGGINGFACE` | `false` | Include HuggingFace in the fallback chain |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | OpenRouter model |
| `HF_MODEL` | `Qwen/Qwen2.5-72B-Instruct` | HuggingFace model |
| `MAX_ITERATIONS` | `3` | Maximum self-healing feedback loop iterations |
| `LLM_TEMPERATURE` | `0.2` | LLM sampling temperature (lower = more deterministic) |
| `LLM_MAX_RETRIES` | `2` | JSON parse retry attempts per agent |
| `QAGENT_QUIET` | `` | Suppress startup diagnostics when set |

---

## 🧩 Pipeline State Schema

The shared `QAgentState` TypedDict flows through every node:

```python
class QAgentState(TypedDict):
    run_id: str                        # unique UUID per pipeline run
    brd: str                           # raw BRD text input
    user_stories: list[dict]           # 7-field stories (story_id, title, story, AC, priority, estimation, description)
    reviewed_stories: list[dict]       # QA-reviewed stories with confidence scores
    test_cases: list[dict]             # formal test cases (id, title, steps, expected_result)
    coverage_gaps: list[str]           # descriptions of uncovered scenarios
    test_scripts: list[str]            # file paths to generated .py test scripts
    execution_results: list[dict]      # {tc_id, file, status, duration, error_message}
    failure_analysis: list[dict]       # {tc_id, root_cause, error_type, fix_suggestion, is_healable}
    healed_scripts: list[str]          # file paths to self-healed scripts
    healing_hashes: dict[str, list]    # tc_id → SHA-256 prefix hashes of past patches
    feedback: list[str]                # human-readable inter-agent messages
    iteration: int                     # current feedback loop counter (0–3)
    status: str                        # "running" | "all_passed" | "partial_pass" | "failed"
    step_timings: dict[str, float]     # node_name → wall-clock seconds
    pass_rate: float                   # fraction of tests passed (0.0–1.0)
```

---

## 🛠️ How to Add a New Agent

**1. Create the agent file** in `agents/my_agent.py`:

```python
from graph.state import QAgentState
import config

def my_agent(state: QAgentState) -> QAgentState:
    llm = config.get_groq_llm(temperature=0.2)
    # ... build messages, call llm.invoke(..., json_mode=True), parse result ...
    return {**state, "my_output_field": result}
```

**2. Register the node** in `graph/workflow.py`:

```python
from agents.my_agent import my_agent

graph.add_node("my_agent", _timed("my_agent", my_agent))
graph.add_edge("previous_node", "my_agent")
graph.add_edge("my_agent", "next_node")
```

**3. Add the output field** to `QAgentState` in `graph/state.py` and initialise it in `initial_state()`.

**4. Write a unit test** in `tests/test_agents.py` using `@patch` to mock the LLM call.

---

## 🧱 Tech Stack

<table>
<tr><th>Layer</th><th>Technology</th><th>Purpose</th></tr>
<tr><td rowspan="3"><b>Orchestration</b></td><td>LangGraph 0.2+</td><td>Multi-agent StateGraph with conditional feedback edges</td></tr>
<tr><td>LangChain 0.3+</td><td>LLM abstractions, message formatting, document handling</td></tr>
<tr><td>Python ThreadPoolExecutor</td><td>Parallel per-story processing in QA Review + Coverage</td></tr>
<tr><td rowspan="5"><b>LLM Providers</b></td><td>OpenAI GPT-4o-mini</td><td>Primary provider (json_mode, streaming)</td></tr>
<tr><td>Groq (llama-3.3-70b)</td><td>1st fallback — extremely fast inference</td></tr>
<tr><td>OpenRouter</td><td>2nd fallback — multi-model gateway</td></tr>
<tr><td>Google Gemini 2.0 Flash</td><td>3rd fallback</td></tr>
<tr><td>HuggingFace (Qwen2.5-72B)</td><td>Last-resort fallback</td></tr>
<tr><td rowspan="2"><b>Memory / RAG</b></td><td>FAISS (CPU)</td><td>Local vector store — 4 namespaces</td></tr>
<tr><td>sentence-transformers/all-MiniLM-L6-v2</td><td>Local embeddings (no API key required)</td></tr>
<tr><td rowspan="2"><b>Test Automation</b></td><td>Playwright 1.47+</td><td>Browser automation for generated test scripts</td></tr>
<tr><td>pytest + pytest-json-report</td><td>Test runner with structured JSON output</td></tr>
<tr><td rowspan="2"><b>Backend</b></td><td>FastAPI 0.115+</td><td>REST API + WebSocket server</td></tr>
<tr><td>Uvicorn</td><td>ASGI server with async support</td></tr>
<tr><td rowspan="4"><b>Frontend</b></td><td>Next.js 15 + React 19</td><td>SSR + app router</td></tr>
<tr><td>Tailwind CSS v4</td><td>Utility-first styling</td></tr>
<tr><td>Framer Motion</td><td>Animations and page transitions</td></tr>
<tr><td>Three.js</td><td>3D avatar rendering</td></tr>
<tr><td rowspan="2"><b>Document Parsing</b></td><td>pdfplumber + PyPDF2</td><td>PDF text extraction</td></tr>
<tr><td>python-docx, openpyxl</td><td>DOCX and XLSX parsing</td></tr>
<tr><td><b>Code Quality</b></td><td>Ruff + Pydantic v2</td><td>Linting and data validation</td></tr>
</table>

---

## ⚠️ Known Limitations

| Limitation | Details |
|------------|---------|
| **Single-page Playwright scripts** | The Script Agent generates tests assuming a single-page context. Multi-page flows (e.g. OAuth redirects) may need manual adjustment. |
| **FAISS memory is in-process** | The FAISS index is persisted to disk but loaded once per process. Concurrent writes from multiple workers are not supported. |
| **Scanned PDF quality** | `pdfplumber` may produce noisy text for scanned or image-based PDFs. Use text-based PDFs for best results. |
| **Token limits on large BRDs** | Very large BRDs (>10,000 tokens) may be truncated by the LLM context window. Consider splitting large documents. |
| **No UI authentication** | The Next.js app has no authentication. Do not expose it on a public network with real API keys in the backend. |
| **Streaming fallback** | If a provider doesn't support `stream()`, the agent falls back to a blocking `invoke()` call and the live stream is skipped for that turn. |
| **Financial domain bias** | The Requirement Agent system prompt is tuned for Financial & Insurance domains. BRDs from other domains will work but may produce less precise role naming. |

---

## 🗺️ Roadmap

- [ ] **CI/CD integration** — GitHub Actions workflow to run QAgent on every PR and post results as a comment
- [ ] **Jira / Linear sync** — Automatically create test cases and user stories as tickets
- [ ] **Multi-browser support** — Extend the Script Agent to generate Firefox and WebKit variants
- [ ] **LangSmith tracing** — Full agent trace observability via LangSmith
- [ ] **Persistent shared memory** — Replace in-process FAISS singleton with Pinecone / Weaviate for multi-worker deployments
- [ ] **Human-in-the-loop** — Manual approval checkpoint between QA Review and Test Case generation
- [ ] **Custom embedding models** — Allow swapping `all-MiniLM-L6-v2` for domain-specific fine-tuned embeddings
- [ ] **Test result history** — Persist pass/fail trends across pipeline runs in a lightweight DB
- [ ] **Streamlit dashboard** — Alternative local UI via the existing `ui/` module (`make run`)
- [ ] **Docker Compose** — One-command deployment of the full stack

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repo and create a feature branch: `git checkout -b feat/my-feature`
2. Make changes and add tests in `tests/test_agents.py`
3. Run `make lint && make test` to verify
4. Open a Pull Request with a clear description

---

## 📄 License

[MIT](https://opensource.org/licenses/MIT) © 2026 QAgent Nexus

---

<div align="center">

Built with ❤️ using **LangGraph**, **FastAPI**, **Next.js**, and **Playwright**

*Transform requirements into quality — autonomously.*

</div>
