"""
agents/failure_analysis_agent.py — Failure Analysis Agent
==========================================================
Analyses failed/errored test results, classifies root cause using
Google Gemini enriched with FAISS memory context, and stores results
for future healing.

Flow:
    state.execution_results (failed/error subset)
        →  FAISS retrieve_similar_failures  (context enrichment)
        →  ChatGoogleGenerativeAI           (root-cause classification)
        →  FAISS store_failure              (persist for future runs)
        →  state.failure_analysis (list[dict])
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

import config
from agents.utils import extract_json, run_parallel
from graph.state import QAgentState
from memory.faiss_store import get_memory

logger = logging.getLogger(__name__)

# ── Pydantic model ────────────────────────────────────────────────────────────

class FailureAnalysis(BaseModel):
    tc_id: str
    error_type: Literal[
        "selector_changed",
        "timeout",
        "assertion_mismatch",
        "assertion_logic",
        "wrong_expected_value",
        "missing_step",
        "network_error",
        "logic_error",
        "import_error",
        "playwright_api",
        "unknown",
    ]
    root_cause: str = Field(..., min_length=10)
    confidence: float = Field(..., ge=0.0, le=1.0)
    fix_suggestion: str = Field(..., min_length=10)
    is_healable: bool

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Senior QA Automation Engineer specialising in test failure diagnosis.
Given a test failure (traceback, error message) and optionally similar past
failures with their fixes, classify the root cause and suggest a concrete fix.

Root cause categories:
  - selector_changed    : A CSS/ARIA selector no longer matches the DOM
  - timeout             : page.wait_for_selector or network call exceeded timeout
  - assertion_mismatch  : The observed value differs from expected_result
  - assertion_logic     : Wrong assertion type or incorrect comparison logic
  - wrong_expected_value: The expected value in the test itself is incorrect
  - missing_step        : A required prerequisite step is missing from the test
  - network_error       : HTTP error, CORS, or third-party service failure
  - logic_error         : Incorrect test logic or wrong test data (general)
  - import_error        : Missing module or import statement error
  - playwright_api      : Deprecated or incorrect Playwright API usage
  - unknown             : Cannot classify with available information

Return ONLY a valid JSON object — no markdown fences, no explanation.
"""

_USER_PROMPT_TEMPLATE = """\
Analyse the following test failure and return a structured diagnosis.

Schema:
{{
  "tc_id":          "{tc_id}",
  "error_type":     "selector_changed|timeout|assertion_mismatch|network_error|logic_error|unknown",
  "root_cause":     "<detailed explanation>",
  "confidence":     0.0–1.0,
  "fix_suggestion": "<specific, actionable fix>",
  "is_healable":    true | false
}}

--- FAILURE DETAILS ---
tc_id         : {tc_id}
file          : {file}
status        : {status}
error_message : {error_message}
traceback     :
{traceback}

--- SIMILAR PAST FAILURES & FIXES (from memory, may be empty) ---
{similar_context}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    return extract_json(text)


def _format_similar(similar: list[dict]) -> str:
    if not similar:
        return "(none found)"
    parts = []
    for i, item in enumerate(similar, 1):
        parts.append(
            f"[{i}] error: {item.get('error_message', 'N/A')} | "
            f"fix: {item.get('fix_suggestion', item.get('healed_script', 'N/A')[:120])}"
        )
    return "\n".join(parts)


def _analyse_failure(
    llm,
    failure: dict,
    similar: list[dict],
    max_retries: int = 2,
) -> dict:
    """Run Gemini for one failure record; retry on parse/validation errors."""
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_USER_PROMPT_TEMPLATE.format(
                tc_id=failure.get("tc_id", "UNKNOWN"),
                file=failure.get("file", ""),
                status=failure.get("status", ""),
                error_message=failure.get("error_message", "")[:600],
                traceback=failure.get("traceback", "")[:1200],
                similar_context=_format_similar(similar),
            )
        ),
    ]

    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):
        try:
            response = llm.invoke(messages)
            data = json.loads(_extract_json(response.content))
            # Ensure tc_id is always preserved from the original failure record
            data.setdefault("tc_id", failure.get("tc_id", "UNKNOWN"))
            validated = FailureAnalysis.model_validate(data)
            return validated.model_dump()

        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Failure Analysis Agent attempt %d/%d for %s — %s: %s",
                attempt, max_retries + 1,
                failure.get("tc_id", "?"),
                type(exc).__name__, exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"Your previous response caused a parse/validation error: {exc}\n"
                            "Fix it and return ONLY a valid JSON object matching the schema."
                        )
                    )
                )

    raise RuntimeError(
        f"Failure Analysis Agent failed for {failure.get('tc_id')} "
        f"after {max_retries + 1} attempts. Last error: {last_error}"
    )


# ── Agent node ────────────────────────────────────────────────────────────────

def failure_analysis_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: execution_results (failures) → failure_analysis.

    Runs all failure analyses concurrently (one LLM call per failure in
    parallel) then stores results to FAISS.
    """
    failed_results = [
        r for r in state["execution_results"]
        if r.get("status") in ("failed", "error")
    ]

    if not failed_results:
        print("✅ Failure Analysis Agent: No failures to analyse.")
        logger.info("Failure Analysis Agent: no failures found, skipping.")
        return {**state, "failure_analysis": []}

    llm    = config.get_openrouter_llm(temperature=0.1)
    memory = get_memory()

    # Pre-fetch similar failures from FAISS (one query per failure)
    similar_by_idx: list[list[dict]] = [
        memory.retrieve_similar_failures(
            failure.get("error_message", "") or failure.get("traceback", ""), k=3
        )
        for failure in failed_results
    ]

    print(f"  ⚡ Failure Analysis Agent: analysing {len(failed_results)} failure(s) in parallel …")

    def _analyse_one(args: tuple) -> dict:
        failure, similar = args
        return _analyse_failure(llm, failure, similar)

    analyses: list[dict] = run_parallel(
        _analyse_one,
        list(zip(failed_results, similar_by_idx)),
        max_workers=4,
        label="failure-analysis",
    )

    for analysis, failure in zip(analyses, failed_results):
        tc_id      = analysis["tc_id"]
        confidence = analysis["confidence"]
        logger.info(
            "Failure Analysis: %s | type: %s | confidence: %.2f | healable: %s",
            tc_id, analysis["error_type"], confidence, analysis["is_healable"],
        )
        print(
            f"  🔬 {tc_id} | {analysis['error_type']} | "
            f"confidence: {confidence:.2f} | healable: {analysis['is_healable']}"
        )
        memory_record = {**failure, **analysis}
        try:
            memory.store_failure(memory_record)
        except Exception as exc:
            logger.warning("Failure Analysis: FAISS store_failure failed — %s", exc)

    try:
        memory.save()
    except Exception as exc:
        logger.warning("Failure Analysis: FAISS save() failed — %s", exc)

    healable   = sum(1 for a in analyses if a["is_healable"])
    unhealable = len(analyses) - healable
    print(
        f"✅ Failure Analysis Agent: Analysed {len(analyses)} failure(s) — "
        f"{healable} healable, {unhealable} not healable"
    )
    logger.info(
        "✅ Failure Analysis Agent: %d analysed, %d healable, %d not healable",
        len(analyses), healable, unhealable,
    )
    return {**state, "failure_analysis": analyses}
