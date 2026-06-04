import json
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

from ui.utils import extract_pdf_text, save_json, create_zip, apply_keys_to_env, reload_config

@st.dialog("Review Story")
def _review_dialog(story):
    st.write(f"**{story.get('story_id')} - {story.get('title')}**")
    st.write(f"Confidence: {story.get('qa_confidence', 1.0):.0%}")
    for n in story.get("qa_notes", []):
        st.write(f"- {n}")

def _run_agent(app_state, agent_fn, state_dict: dict) -> dict:
    log_lines = app_state.log_lines

    class _Capture:
        def __init__(self, real):
            self._r = real
        def write(self, text):
            self._r.write(text)
            stripped = text.strip()
            if stripped:
                log_lines.append(stripped)
        def flush(self): self._r.flush()
        def isatty(self): return False

    real = sys.stdout
    sys.stdout = _Capture(real)
    try:
        result = agent_fn(state_dict)
    finally:
        sys.stdout = real
    
    app_state.log_lines = log_lines
    return result

def _run_step(app_state, step: int) -> None:
    apply_keys_to_env(app_state)
    reload_config()
    state = app_state.state

    if step == 1:
        from agents.requirement_agent import requirement_agent
        state = _run_agent(app_state, requirement_agent, state)
    elif step == 2:
        from agents.qa_review_agent import qa_review_agent
        state = _run_agent(app_state, qa_review_agent, state)
    elif step == 3:
        from agents.test_case_agent import test_case_agent
        state = _run_agent(app_state, test_case_agent, state)
    elif step == 4:
        from agents.coverage_agent import coverage_agent
        state = _run_agent(app_state, coverage_agent, state)
    elif step == 5:
        from agents.script_agent import script_agent
        state = _run_agent(app_state, script_agent, state)
    elif step == 6:
        from agents.execution_agent import execution_agent
        state = _run_agent(app_state, execution_agent, state)
    elif step == 7:
        from agents.failure_analysis_agent import failure_analysis_agent
        state = _run_agent(app_state, failure_analysis_agent, state)
    elif step == 8:
        failures = [r for r in state.get("failure_analysis", []) if r.get("is_healable")]
        if failures:
            from agents.healing_agent import healing_agent
            state = _run_agent(app_state, healing_agent, state)
        else:
            app_state.log_lines.append("Healing Agent: no healable failures — skipped.")

    app_state.state = state
    app_state.step = step

def render_pipeline(app_state):
    step = app_state.step
    state = app_state.state

    # -- STEP 0 -- BRD Input
    with st.expander("Step 0 - BRD Input", expanded=(step == 0)):
        col_text, col_upload = st.columns([2, 1])
        with col_upload:
            uploaded = st.file_uploader("Upload PDF BRD", type=["pdf"])
            if uploaded:
                pdf_text = extract_pdf_text(uploaded)
                if pdf_text:
                    app_state.brd_input = pdf_text
                    st.success(f"Extracted {len(pdf_text):,} chars from PDF.")
        with col_text:
            brd_text = st.text_area("Paste BRD text", value=app_state.brd_input, height=260,
                placeholder="As a user I want to log in with email and password...")
            if brd_text != app_state.brd_input:
                app_state.brd_input = brd_text

        if step == 0:
            if st.button("Start - Generate User Stories", type="primary", use_container_width=True):
                brd = app_state.brd_input.strip()
                if not brd:
                    st.error("Enter or upload a BRD first.")
                else:
                    with st.spinner("Running Requirement Agent..."):
                        try:
                            from graph.state import initial_state
                            app_state.state = initial_state(brd)
                            _run_step(app_state, 1)
                            save_json(app_state.state["user_stories"], "user_stories.json")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Requirement Agent error: {exc}")

    # -- STEP 1 -- User Stories
    if step >= 1:
        stories = state.get("user_stories", [])
        if stories:
            with st.expander(f"User Stories ({len(stories)})", expanded=(step == 1)):
                df = pd.DataFrame(stories)
                st.data_editor(df, use_container_width=True, hide_index=True)
                
        if step == 1:
            st.info("User Stories generated and saved to outputs/user_stories.json")
            if st.button("Continue - Run QA Review Agent", type="primary", use_container_width=True):
                with st.spinner("Running QA Review Agent..."):
                    try:
                        _run_step(app_state, 2)
                        save_json(app_state.state["reviewed_stories"], "reviewed_stories.json")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"QA Review Agent error: {exc}")

    # -- STEP 2 -- QA Review
    if step >= 2:
        reviewed = state.get("reviewed_stories", [])
        if reviewed:
            with st.expander(f"QA Review ({len(reviewed)} stories)", expanded=(step == 2)):
                for s in reviewed:
                    needs = s.get("needs_review", False)
                    conf = s.get("qa_confidence", 1.0)
                    if needs:
                        col1, col2 = st.columns([0.8, 0.2])
                        with col1:
                            st.markdown(f'<div class="needs-review"><strong>{s.get("story_id")} - {s.get("title")}</strong> (confidence: {conf:.0%})</div>', unsafe_allow_html=True)
                        with col2:
                            if st.button("View Notes", key=f"view_{s.get('story_id')}"):
                                _review_dialog(s)
                    else:
                        st.success(f"{s.get('story_id')} - {s.get('title')} (confidence: {conf:.0%})")
                        
        if step == 2:
            st.info("Stories reviewed. Ready to generate test cases.")
            if st.button("Continue - Generate Test Cases", type="primary", use_container_width=True):
                with st.spinner("Running Test Case Agent..."):
                    try:
                        _run_step(app_state, 3)
                        save_json(app_state.state["test_cases"], "test_cases.json")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Test Case Agent error: {exc}")

    # -- STEP 3 -- Test Cases
    if step >= 3:
        tcs = state.get("test_cases", [])
        if tcs:
            with st.expander(f"Test Cases ({len(tcs)})", expanded=(step == 3)):
                type_filter = st.multiselect("Filter by type", options=["positive", "negative", "edge"], default=["positive", "negative", "edge"])
                filtered = [tc for tc in tcs if tc.get("type") in type_filter]
                st.data_editor(pd.DataFrame(filtered), use_container_width=True, hide_index=True)
                
        if step == 3:
            st.info("Test cases generated and saved to outputs/test_cases.json")
            if st.button("Continue - Run Coverage Analysis", type="primary", use_container_width=True):
                with st.spinner("Running Coverage Agent..."):
                    try:
                        _run_step(app_state, 4)
                        save_json(app_state.state["coverage_gaps"], "coverage_gaps.json")
                        save_json(app_state.state["test_cases"], "test_cases_with_gaps.json")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Coverage Agent error: {exc}")

    # -- STEP 4 -- Coverage
    if step >= 4:
        gaps = state.get("coverage_gaps", [])
        if gaps:
            with st.expander(f"Coverage Gaps ({len(gaps)})", expanded=(step == 4)):
                for g in gaps:
                    st.markdown(f"- {g}")
                    
        if step == 4:
            st.info("Coverage analysis complete. Ready to generate Playwright scripts.")
            if st.button("Continue - Generate Scripts", type="primary", use_container_width=True):
                with st.spinner("Running Script Agent..."):
                    try:
                        _run_step(app_state, 5)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Script Agent error: {exc}")

    # -- STEP 5 -- Scripts
    if step >= 5:
        scripts = state.get("test_scripts", [])
        if scripts:
            with st.expander(f"Generated Scripts ({len(scripts)})", expanded=(step == 5)):
                for p_str in scripts:
                    p = Path(p_str)
                    st.markdown(f"**`{p.name}`**")
                    if p.exists():
                        st.code(p.read_text(encoding="utf-8"), language="python")

        if step == 5:
            st.info("Scripts generated. Ready to execute tests.")
            if st.button("Continue - Run Tests", type="primary", use_container_width=True):
                with st.spinner("Running Execution Agent..."):
                    try:
                        _run_step(app_state, 6)
                        save_json(app_state.state["execution_results"], "execution_results.json")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Execution Agent error: {exc}")

    # -- STEP 6 -- Execution
    if step >= 6:
        results = state.get("execution_results", [])
        if results:
            with st.expander(f"Execution Results ({len(results)})", expanded=(step == 6)):
                df = pd.DataFrame(results)
                show_cols = [c for c in ["tc_id", "file", "status", "duration", "error_message"] if c in df.columns]
                def _colour(val):
                    return "background-color:#1a6b3c;color:#fff" if val == "passed" else "background-color:#6b1a1a;color:#fff"
                st.dataframe(df[show_cols].style.applymap(_colour, subset=["status"]), use_container_width=True, hide_index=True)
                
        if step == 6:
            failures = [r for r in state.get("execution_results", []) if r.get("status") in ("failed", "error")]
            if failures:
                st.info(f"{len(failures)} test(s) failed. Analyse failures?")
                if st.button("Continue - Analyse Failures", type="primary", use_container_width=True):
                    with st.spinner("Running Failure Analysis Agent..."):
                        try:
                            _run_step(app_state, 7)
                            save_json(app_state.state["failure_analysis"], "failure_analysis.json")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failure Analysis Agent error: {exc}")
            else:
                st.success("All tests passed! No failure analysis needed.")
                if st.button("Finish Pipeline", use_container_width=True):
                    with st.spinner("Finishing up..."):
                        _run_step(app_state, 7)
                        _run_step(app_state, 8)
                        st.balloons()
                        st.rerun()

    # -- STEP 7 -- Failure Analysis
    if step >= 7:
        fas = state.get("failure_analysis", [])
        if fas:
            with st.expander(f"Failure Analysis ({len(fas)})", expanded=(step == 7)):
                for fa in fas:
                    icon = "🟢 Healable" if fa.get("is_healable") else "🔴 Not Healable"
                    st.markdown(
                        f'<div class="card"><strong>{icon} - {fa.get("tc_id","?")} / {fa.get("error_type","?")}</strong> '
                        f'(confidence: {fa.get("confidence",0):.0%})<br/>'
                        f'<em>Root cause:</em> {fa.get("root_cause","")}<br/>'
                        f'<em>Fix:</em> {fa.get("fix_suggestion","")}</div>',
                        unsafe_allow_html=True)
                        
        if step == 7:
            healable = [f for f in state.get("failure_analysis", []) if f.get("is_healable")]
            if healable:
                st.info(f"{len(healable)} healable failure(s). Auto-heal scripts?")
                if st.button("Continue - Heal Scripts", type="primary", use_container_width=True):
                    with st.spinner("Running Healing Agent..."):
                        try:
                            _run_step(app_state, 8)
                            st.balloons()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Healing Agent error: {exc}")
            else:
                st.info("No healable failures - skipping Healing Agent.")
                if st.button("Mark Pipeline Complete", use_container_width=True):
                    with st.spinner("Completing pipeline..."):
                        _run_step(app_state, 8)
                        st.balloons()
                        st.rerun()

    # -- STEP 8 -- Complete
    if step >= 8:
        healed = state.get("healed_scripts", [])
        if healed:
            with st.expander(f"Healed Scripts ({len(healed)})", expanded=True):
                for h_str in healed:
                    h = Path(h_str)
                    st.markdown(f"**Healed:** `{h.name}`")
                    if h.exists():
                        st.code(h.read_text(encoding="utf-8"), language="python")
        
        st.success("Pipeline complete! All 8 agents have run.")
        
        with st.expander("Downloads", expanded=False):
            tcs = state.get("test_cases", [])
            if tcs:
                st.download_button("Download All Test Cases (JSON)", data=json.dumps(tcs, indent=2).encode(), file_name="all_test_cases.json", mime="application/json", use_container_width=True)
            
            all_scripts = state.get("test_scripts", []) + state.get("healed_scripts", [])
            if all_scripts:
                zip_data = create_zip(all_scripts)
                st.download_button("Download All Scripts (ZIP)", data=zip_data, file_name="all_scripts.zip", mime="application/zip", use_container_width=True)

    # -- Pipeline log
    log = app_state.log_lines
    if log:
        with st.expander("Pipeline Log", expanded=False):
            st.code("\n".join(log), language="text")
