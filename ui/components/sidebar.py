import streamlit as st
from ui.utils import load_env

def render_sidebar(app_state):
    with st.sidebar:
        st.title("Configuration")

        with st.expander("API Keys", expanded=False):
            app_state.groq_api_key = st.text_input("GROQ API Key", type="password", value=app_state.groq_api_key)
            app_state.google_api_key = st.text_input("Google API Key", type="password", value=app_state.google_api_key)
            app_state.huggingface_api_key = st.text_input("HuggingFace API Key", type="password", value=app_state.huggingface_api_key)
            app_state.openrouter_api_key = st.text_input("OpenRouter API Key", type="password", value=app_state.openrouter_api_key)

        with st.expander("Models", expanded=False):
            app_state.groq_model = st.selectbox("Groq Model", options=[
                "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant", "llama3-8b-8192", "gemma2-9b-it",
            ], index=0)
            app_state.gemini_model = st.selectbox("Gemini Model", options=[
                "gemini-2.0-flash", "gemini-2.0-flash-lite",
                "gemini-2.5-pro-preview-03-25", "gemini-1.5-flash",
            ], index=0)
            app_state.hf_model = st.selectbox("HuggingFace Model", options=[
                "Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3-70b-chat-hf"
            ], index=0)
            app_state.openrouter_model = st.selectbox("OpenRouter Model", options=[
                "meta-llama/llama-3.3-70b-instruct:free"
            ], index=0)

        if st.button("Load from .env", use_container_width=True):
            load_env(app_state)
            st.rerun()

        st.divider()

        # Pipeline progress visualization
        st.markdown("**Pipeline Progress**")
        _STEP_LABELS = [
            "BRD Input", "Requirement Agent", "QA Review Agent",
            "Test Case Agent", "Coverage Agent", "Script Agent",
            "Execution Agent", "Failure Analysis", "Healing Agent",
        ]
        
        # Use a more modern progress approach
        progress_val = app_state.step / 8 if app_state.step > 0 else 0
        st.progress(progress_val)
        
        for i, label in enumerate(_STEP_LABELS):
            if i < app_state.step or (i == app_state.step and app_state.step > 0):
                st.markdown(f"✅ **{i}.** {label}")
            elif i == app_state.step:
                st.markdown(f"▶️ **{i}.** {label}")
            else:
                st.markdown(f"⏳ **{i}.** <span style='color:gray'>{label}</span>", unsafe_allow_html=True)

        if app_state.step > 0:
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Step", f"{app_state.step} / 8")
            c2.metric("Stories", len(app_state.state.get("user_stories", [])))
            st.metric("Test Cases", len(app_state.state.get("test_cases", [])))
            
            if app_state.step >= 6:
                passed = sum(1 for r in app_state.state.get("execution_results", []) if r.get("status") == "passed")
                failed = sum(1 for r in app_state.state.get("execution_results", []) if r.get("status") != "passed")
                st.metric("Passed / Failed", f"{passed} / {failed}")

        if app_state.step > 0:
            if st.button("Reset Pipeline", use_container_width=True, type="secondary"):
                app_state.step = 0
                app_state.state = {}
                app_state.log_lines = []
                app_state.brd_input = ""
                st.rerun()
