import re
import pandas as pd
import streamlit as st

def render_analytics(app_state):
    state = app_state.state
    step = app_state.step

    if step < 3:
        st.info("Run the pipeline through Step 3 (Test Cases) for charts.")
        return

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        _plotly_ok = True
    except ImportError:
        _plotly_ok = False
        st.warning("Install plotly for charts: pip install plotly")

    tcs = state.get("test_cases", [])
    exec_results = state.get("execution_results", [])
    gaps = state.get("coverage_gaps", [])

    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Test Coverage by Type")
        if tcs and _plotly_ok:
            cnt = pd.Series([t.get("type", "?") for t in tcs]).value_counts()
            fig = px.pie(values=cnt.values, names=cnt.index, hole=0.45,
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=280)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Pass / Fail Distribution")
        if exec_results and _plotly_ok:
            cnt2 = pd.Series([r.get("status", "?") for r in exec_results]).value_counts()
            cmap = {"passed": "#27ae60", "failed": "#c0392b", "error": "#e67e22"}
            fig2 = px.bar(x=cnt2.index, y=cnt2.values, color=cnt2.index,
                          color_discrete_map=cmap, labels={"x": "Status", "y": "Count"})
            fig2.update_layout(showlegend=False, margin=dict(t=0, b=0), height=280)
            st.plotly_chart(fig2, use_container_width=True)
        elif not exec_results:
            st.info("Run Execution Agent for this chart.")

    with c3:
        st.subheader("Gap Severity Distribution")
        if gaps and _plotly_ok:
            sevs = []
            for g in gaps:
                m = re.match(r"\[[^\]]+\]\[([^\]]+)\]", g)
                sevs.append(m.group(1) if m else "Unknown")
            cnt3 = pd.Series(sevs).value_counts()
            cmap3 = {"High": "#c0392b", "Medium": "#e67e22", "Low": "#27ae60"}
            fig3 = px.bar(x=cnt3.index, y=cnt3.values, color=cnt3.index,
                          color_discrete_map=cmap3, labels={"x": "Severity", "y": "Count"})
            fig3.update_layout(showlegend=False, margin=dict(t=0, b=0), height=280)
            st.plotly_chart(fig3, use_container_width=True)
        elif not gaps:
            st.info("Run Coverage Agent for this chart.")

    if tcs and _plotly_ok:
        st.subheader("Test Cases by Priority x Type")
        df_tc = pd.DataFrame(tcs)
        if "priority" in df_tc.columns and "type" in df_tc.columns:
            cnt4 = df_tc.groupby(["priority", "type"]).size().reset_index(name="count")
            fig4 = px.bar(cnt4, x="priority", y="count", color="type", barmode="group",
                          color_discrete_sequence=px.colors.qualitative.Set2)
            fig4.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(fig4, use_container_width=True)
