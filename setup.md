# QAgent Setup and Run Guide

## Frontend URL
The platform is accessible at:
- **Local:** [http://localhost:3000](http://localhost:3000)

## Backend API
The FastAPI backend runs at:
- **Local:** [http://localhost:8000](http://localhost:8000)

## Startup Commands

### Automatic (Windows PowerShell)
Run the following script from the project root to start both the backend and frontend:
```powershell
.\start_dev.ps1
```

### Manual (Separate Terminals)

**Terminal 1 — Backend (FastAPI):**
```bash
.venv\Scripts\activate
uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — Frontend (Next.js):**
```bash
cd frontend
npm run dev
```

## Default Credentials
- **Authentication:** None (The platform currently has no UI authentication as per design limitations).
- **API Keys:** Required in the `.env` file for LLM providers (Groq, OpenAI, Gemini, etc.).

## Environment Configuration
Ensure your `.env` file is populated with at least one valid API key:
- `GROQ_API_KEY`
- `GPT_API_KEY` (OpenAI)
- `GOOGLE_API_KEY`
- `OPENROUTER_API_KEY`

## Pathforge Platform

### Frontend URL
The platform is accessible at:
- **Local:** [http://localhost:3001](http://localhost:3001)

### Startup Commands
```bash
cd c:\Users\Rahul\Projects\Roadmap\pathforge
npm run dev
```

### Default Credentials
- **Authentication:** None. Please register a new account on the Sign Up page.

