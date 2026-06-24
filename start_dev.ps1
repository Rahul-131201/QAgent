# Start FastAPI backend in the background
Start-Process -NoNewWindow -FilePath ".\.venv\Scripts\uvicorn.exe" -ArgumentList "api.main:app", "--reload", "--reload-dir", "api", "--reload-dir", "agents", "--port", "8000"

# Start Next.js frontend
cd frontend
npm run dev
