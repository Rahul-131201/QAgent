"""
ui/app.py — QAgent Streamlit Frontend
======================================
Run with:
    streamlit run ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

# -- Path setup ----------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# -- Page config ---------------------------------------------------------------
st.set_page_config(
    page_title="QAgent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -- CSS -----------------------------------------------------------------------
st.markdown(
    """
    <style>
    .badge-high   { background:#c0392b; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; }
    .badge-medium { background:#e67e22; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; }
    .badge-low    { background:#27ae60; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.75rem; }
    .needs-review { background:#c0392b22; border-left:4px solid #c0392b; padding:6px 10px; border-radius:4px; margin:4px 0; }
    .card         { background:#1e1e2e; border-radius:8px; padding:12px 16px; margin-bottom:8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -- Imports -------------------------------------------------------------------
from ui.state import init_state
from ui.components.sidebar import render_sidebar
from ui.views.pipeline_view import render_pipeline
from ui.views.analytics_view import render_analytics

# -- Main ----------------------------------------------------------------------
def main():
    # Initialize robust session state
    init_state(st.session_state)
    app_state = st.session_state.app_state
    
    # Bootstrap initial env state
    if app_state.step == 0 and not app_state.groq_api_key:
        from ui.utils import load_env
        load_env(app_state)
    
    # Render UI
    render_sidebar(app_state)
    
    st.title("QAgent - AI-Powered QA Automation")
    st.caption("Step-by-step pipeline: AI Agents + FAISS + Playwright")

    tab_pipeline, tab_analytics = st.tabs(["Pipeline", "Analytics"])

    with tab_pipeline:
        render_pipeline(app_state)
        
    with tab_analytics:
        render_analytics(app_state)

if __name__ == "__main__":
    main()
