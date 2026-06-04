"""
graph/workflow.py — QAgent LangGraph Orchestration
====================================================
Defines and compiles the full multi-agent state machine.

Pipeline (linear → conditional feedback loop):

    START
      └─▶ requirement
            └─▶ qa_review          (parallel per-story)
                  └─▶ test_case
                        └─▶ coverage  (parallel per-story)
                              └─▶ script
                                    └─▶ execution
                                          └─▶ analysis
                                                └─▶ healing
                                                      └─▶ [should_continue]
                                                            ├─▶ END           (all passed OR iteration ≥ 3)
                                                            ├─▶ qa_review     (story logic errors / ambiguity)
                                                            ├─▶ test_case     (test design errors)
                                                            └─▶ script        (selector / runtime fixes only)
"""

from __future__ import annotations

import logging
import time

from langgraph.graph import StateGraph, START, END

from graph.state import QAgentState, initial_state
from agents.requirement_agent    import requirement_agent
from agents.qa_review_agent      import qa_review_agent
from agents.test_case_agent      import test_case_agent
from agents.coverage_agent       import coverage_agent
from agents.script_agent         import script_agent
from agents.execution_agent      import execution_agent
from agents.failure_analysis_agent import failure_analysis_agent
from agents.healing_agent        import healing_agent

logger = logging.getLogger(__name__)

# ── Step-timing decorator ─────────────────────────────────────────────────────

def _timed(name: str, fn):
    """Wrap a node function to record wall-clock elapsed time in state.step_timings."""
    def _wrapper(state: QAgentState) -> QAgentState:
        t0 = time.perf_counter()
        result = fn(state)
        elapsed = round(time.perf_counter() - t0, 3)
        timings = dict(result.get("step_timings") or {})
        timings[name] = elapsed
        logger.info("step_timings: %s → %.3fs", name, elapsed)
        return {**result, "step_timings": timings}
    _wrapper.__name__ = name
    return _wrapper


# ── Healing wrapper ───────────────────────────────────────────────────────────

def _healing_node(state: QAgentState) -> QAgentState:
    """Run healing_agent, increment the feedback-loop counter, compute pass_rate."""
    result = healing_agent(state)
    new_iteration = state.get("iteration", 0) + 1

    # Compute pass_rate from execution_results
    exec_results = result.get("execution_results") or []
    if exec_results:
        passed = sum(1 for r in exec_results if r.get("status") == "passed")
        pass_rate = round(passed / len(exec_results), 4)
    else:
        pass_rate = state.get("pass_rate", 0.0)

    logger.info(
        "QAgent workflow: iteration → %d | pass_rate: %.1f%%",
        new_iteration, pass_rate * 100,
    )
    return {**result, "iteration": new_iteration, "pass_rate": pass_rate}


# ── Conditional routing ───────────────────────────────────────────────────────

# Error types that require re-examining the test design (not just re-scripting)
_TEST_DESIGN_ERRORS = {"assertion_logic", "wrong_expected_value", "missing_step"}

# Error types that are purely scripting/locator issues — re-generate script only
_SCRIPT_ERRORS = {"selector_changed", "timeout", "playwright_api", "import_error"}


def should_continue(state: QAgentState) -> str:
    """
    Finer-grained routing after the healing node.

    Priority order (highest first):
      1. "end"        — all_passed OR max iterations reached
      2. "qa_review"  — story-level logic errors or low-confidence stories
      3. "test_case"  — test-design errors (wrong assertions, missing steps)
      4. "script"     — pure scripting/selector/timeout issues (only when healable)
      5. "end"        — fallback when nothing is healable (avoid infinite loop)
    """
    status    = state.get("status", "running")
    iteration = state.get("iteration", 0)

    if status == "all_passed":
        logger.info("should_continue → END (all tests passed)")
        return "end"

    if iteration >= 3:
        logger.info("should_continue → END (max iterations=%d reached)", iteration)
        return "end"

    failures = state.get("failure_analysis") or []
    reviewed = state.get("reviewed_stories") or []

    # ── Story-level issues: route all the way back to qa_review ──────────────
    has_logic_errors = any(f.get("error_type") == "logic_error" for f in failures)
    has_ambiguous    = any(s.get("needs_review") is True for s in reviewed)

    if has_logic_errors or has_ambiguous:
        logger.info(
            "should_continue → qa_review (logic_errors=%s, ambiguous=%s)",
            has_logic_errors, has_ambiguous,
        )
        return "qa_review"

    # ── Test-design issues: regenerate test cases from reviewed_stories ───────
    has_design_errors = any(
        f.get("error_type") in _TEST_DESIGN_ERRORS for f in failures
    )
    if has_design_errors:
        logger.info("should_continue → test_case (test-design errors detected)")
        return "test_case"

    # ── Scripting/selector issues: just regenerate scripts ────────────────────
    # Only route to "script" when there is at least one healable failure to fix.
    # If all remaining failures are un-healable, stop to avoid an infinite loop.
    has_healable = any(f.get("is_healable") for f in failures)
    if has_healable:
        logger.info("should_continue → script (selector/runtime issues, healable failures present)")
        return "script"

    logger.info(
        "should_continue → END (no healable failures remain, %d un-healable)", len(failures)
    )
    return "end"


# ── Build graph ───────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(QAgentState)

    # ── Nodes (all wrapped with timing) ───────────────────────────────────
    graph.add_node("requirement", _timed("requirement", requirement_agent))
    graph.add_node("qa_review",   _timed("qa_review",   qa_review_agent))
    graph.add_node("test_case",   _timed("test_case",   test_case_agent))
    graph.add_node("coverage",    _timed("coverage",    coverage_agent))
    graph.add_node("script",      _timed("script",      script_agent))
    graph.add_node("execution",   _timed("execution",   execution_agent))
    graph.add_node("analysis",    _timed("analysis",    failure_analysis_agent))
    graph.add_node("healing",     _timed("healing",     _healing_node))

    # ── Linear edges ──────────────────────────────────────────────────────
    graph.add_edge(START,         "requirement")
    graph.add_edge("requirement", "qa_review")
    graph.add_edge("qa_review",   "test_case")
    graph.add_edge("test_case",   "coverage")
    graph.add_edge("coverage",    "script")
    graph.add_edge("script",      "execution")
    graph.add_edge("execution",   "analysis")
    graph.add_edge("analysis",    "healing")

    # ── Conditional feedback edge (4-way) ─────────────────────────────────
    graph.add_conditional_edges(
        "healing",
        should_continue,
        {
            "end":       END,
            "qa_review": "qa_review",
            "test_case": "test_case",
            "script":    "script",
        },
    )

    return graph


# ── Compiled app (module-level singleton) ─────────────────────────────────────

_graph = _build_graph()
app = _graph.compile()


# ── Public entry point ────────────────────────────────────────────────────────

def run_pipeline(brd: str) -> QAgentState:
    """
    Run the full QAgent pipeline from a raw BRD string.

    Args:
        brd: Business Requirement Document text.

    Returns:
        Final QAgentState after the pipeline completes.
    """
    logger.info("QAgent pipeline starting …")
    print("🚀 QAgent pipeline starting …\n")

    state = initial_state(brd)
    final_state: QAgentState = app.invoke(state)

    status    = final_state.get("status", "unknown")
    iteration = final_state.get("iteration", 0)
    pass_rate = final_state.get("pass_rate", 0.0)
    timings   = final_state.get("step_timings", {})

    icon = "✅" if status == "all_passed" else "⚠️ "
    print(
        f"\n{icon} QAgent pipeline complete — "
        f"status: {status} | iterations: {iteration} | pass_rate: {pass_rate:.0%}"
    )
    if timings:
        total = sum(timings.values())
        breakdown = " | ".join(f"{k}: {v:.1f}s" for k, v in timings.items())
        print(f"⏱  Timings ({total:.1f}s total): {breakdown}")

    logger.info(
        "QAgent pipeline complete — status: %s, iterations: %d, pass_rate: %.1f%%",
        status, iteration, pass_rate * 100,
    )
    return final_state

