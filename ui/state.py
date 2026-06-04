from dataclasses import dataclass, field
from typing import Any

@dataclass
class AppState:
    step: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    log_lines: list[str] = field(default_factory=list)
    step_running: bool = False
    brd_input: str = ""
    
    # API settings
    groq_api_key: str = ""
    google_api_key: str = ""
    huggingface_api_key: str = ""
    openrouter_api_key: str = ""
    
    # Model selections
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-2.0-flash"
    hf_model: str = "Qwen/Qwen2.5-72B-Instruct"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

def init_state(st_session_state):
    if "app_state" not in st_session_state:
        st_session_state.app_state = AppState()
