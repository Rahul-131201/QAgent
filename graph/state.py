"""
graph/state.py — QAgent Shared Pipeline State
==============================================
Defines the single TypedDict that flows through every node in the
LangGraph state machine.  All agents read from and write to this dict.
"""

from __future__ import annotations

import uuid
from typing import TypedDict


class QAgentState(TypedDict):
    # ── Run identity ─────────────────────────────────────────────────────────
    run_id: str                     # unique UUID for this pipeline run (for logs/FAISS)

    # ── Input ────────────────────────────────────────────────────────────────
    brd: str                        # raw Business Requirement Document text

    # ── Requirement Agent ────────────────────────────────────────────────────
    user_stories: list[dict]        # structured user stories extracted from BRD

    # ── QA Review Agent ──────────────────────────────────────────────────────
    reviewed_stories: list[dict]    # stories validated / enriched by QA reviewer

    # ── Test Case Agent ──────────────────────────────────────────────────────
    test_cases: list[dict]          # formal test cases (id, title, steps, expected)

    # ── Coverage Agent ───────────────────────────────────────────────────────
    coverage_gaps: list[str]        # descriptions of uncovered scenarios

    # ── Script Agent ─────────────────────────────────────────────────────────
    test_scripts: list[str]         # file paths to generated test scripts

    # ── Execution Agent ──────────────────────────────────────────────────────
    execution_results: list[dict]   # {tc_id, file, status, duration, error_message} per run

    # ── Failure Analysis Agent ───────────────────────────────────────────────
    failure_analysis: list[dict]    # {tc_id, root_cause, error_type, suggestion} per failure

    # ── Healing Agent ────────────────────────────────────────────────────────
    healed_scripts: list[str]       # file paths to healed scripts after self-healing
    healing_hashes: dict[str, list[str]]  # tc_id → SHA-256 prefix hashes of past patches

    # ── Feedback / Loop Control ──────────────────────────────────────────────
    feedback: list[str]             # human-readable messages passed between nodes
    iteration: int                  # current feedback-loop iteration (max 3)
    status: str                     # "running" | "all_passed" | "partial_pass" | "failed"

    # ── Observability ────────────────────────────────────────────────────────
    step_timings: dict[str, float]  # node_name → wall-clock seconds for that step
    pass_rate: float                # fraction of tests that passed (0.0–1.0)


def initial_state(brd: str) -> QAgentState:
    """Return a clean QAgentState seeded with a BRD string."""
    return QAgentState(
        run_id=str(uuid.uuid4()),
        brd=brd,
        user_stories=[],
        reviewed_stories=[],
        test_cases=[],
        coverage_gaps=[],
        test_scripts=[],
        execution_results=[],
        failure_analysis=[],
        healed_scripts=[],
        healing_hashes={},
        feedback=[],
        iteration=0,
        status="running",
        step_timings={},
        pass_rate=0.0,
    )
