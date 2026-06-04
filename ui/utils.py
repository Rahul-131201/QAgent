import io
import json
import os
import zipfile
from pathlib import Path
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def extract_pdf_text(uploaded_file) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        st.error(f"PDF extraction failed: {exc}")
        return ""

def save_json(data: object, filename: str) -> None:
    out_dir = _PROJECT_ROOT / "outputs"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def create_zip(files: list[str]) -> bytes:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p_str in files:
            p = Path(p_str)
            if p.exists():
                zf.write(p, arcname=p.name)
    zip_buf.seek(0)
    return zip_buf.getvalue()

def apply_keys_to_env(app_state) -> None:
    os.environ["GROQ_API_KEY"]   = app_state.groq_api_key
    os.environ["GOOGLE_API_KEY"] = app_state.google_api_key
    os.environ["HUGGINGFACE_API_KEY"] = app_state.huggingface_api_key
    os.environ["OPENROUTER_API_KEY"] = app_state.openrouter_api_key
    os.environ["GROQ_MODEL"]     = app_state.groq_model
    os.environ["GEMINI_MODEL"]   = app_state.gemini_model
    os.environ["HF_MODEL"]       = app_state.hf_model
    os.environ["OPENROUTER_MODEL"] = app_state.openrouter_model

def load_env(app_state) -> None:
    from dotenv import load_dotenv
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        app_state.groq_api_key = os.getenv("GROQ_API_KEY", "")
        app_state.google_api_key = os.getenv("GOOGLE_API_KEY", "")
        app_state.huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY", "")
        app_state.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        app_state.groq_model = os.getenv("GROQ_MODEL", app_state.groq_model)
        app_state.gemini_model = os.getenv("GEMINI_MODEL", app_state.gemini_model)
        app_state.hf_model = os.getenv("HF_MODEL", app_state.hf_model)
        app_state.openrouter_model = os.getenv("OPENROUTER_MODEL", app_state.openrouter_model)
        st.toast("Loaded keys from .env", icon="✅")
    else:
        st.toast(".env not found", icon="⚠️")

def reload_config():
    # Retained for now to ensure agents pick up the new os.environ values
    import importlib
    import config as cfg
    importlib.reload(cfg)
    return cfg
