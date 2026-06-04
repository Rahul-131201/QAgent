"""
agents/healing_agent.py — Healing Agent
========================================
Auto-fixes broken Playwright/pytest scripts using Groq (LLaMA3-70b),
guided by structured failure analysis and FAISS few-shot memory.

Flow:
    state.failure_analysis (is_healable=True subset)
        →  FAISS retrieve_similar_fixes      (few-shot examples)
        →  ChatGroq                          (patch generation)
        →  ast.parse() syntax validation
        →  write tests/generated/healed/
        →  FAISS store_fix                   (persist for future runs)
        →  state.healed_scripts (list of healed file paths)
        →  state.feedback       (append healing summaries)
"""

from __future__ import annotations

import ast
import hashlib
import logging
import re
import textwrap
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

import config
from graph.state import QAgentState
from memory.faiss_store import get_memory

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

HEALED_DIR: Path = config.HEALED_TESTS_DIR

# ── Healing rule hints (injected into prompt per error_type) ──────────────────

_HEALING_RULES: dict[str, str] = {
    "selector_changed": (
        "The selector no longer matches the DOM. "
        "Replace the broken selector with a data-testid alternative "
        "(e.g. page.get_by_test_id('submit-btn')) or a stable ARIA role locator. "
        "Never hard-code CSS class names or auto-generated IDs."
    ),
    "timeout": (
        "A wait or network call exceeded its timeout. "
        "Add page.wait_for_selector(..., timeout=10000) before interactions, "
        "or increase existing timeouts. "
        "For flaky network calls, add a retry decorator:\n"
        "    @pytest.mark.flaky(reruns=2, reruns_delay=1)"
    ),
    "assertion_mismatch": (
        "The observed value does not match the expected_result. "
        "Re-examine the expected value; use flexible matchers where appropriate "
        "(e.g. expect(locator).to_contain_text(...) instead of exact match). "
        "Ensure test data is deterministic."
    ),
    "network_error": (
        "A network or HTTP error occurred. "
        "Add a retry decorator (@pytest.mark.flaky(reruns=3, reruns_delay=2)) "
        "and wrap the network call in try/except to log the response body. "
        "Mock external dependencies when possible."
    ),
    "logic_error": (
        "The test logic is incorrect. "
        "Re-read the expected_result and fix the test steps to match it. "
        "Ensure preconditions are set up correctly before assertions."
    ),
    "unknown": (
        "The root cause is unclear. "
        "Add additional logging (print / page.screenshot) to aid diagnosis. "
        "Keep changes minimal and preserve the original test intent."
    ),
}

# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Senior Test Automation Engineer. Fix the broken Playwright/pytest
script provided. Follow these constraints:
  - Return ONLY the complete, corrected Python source — no markdown fences,
    no explanation, no prose.
  - Preserve the original test intent; only change what is broken.
  - The output must be syntactically valid Python 3.11+.
  - Apply ONLY the healing rule relevant to the error type.
  - Incorporate lessons from the few-shot examples when available.
"""

_USER_PROMPT_TEMPLATE = """\
Fix the broken test script below.

=== ERROR ANALYSIS ===
tc_id          : {tc_id}
error_type     : {error_type}
root_cause     : {root_cause}
fix_suggestion : {fix_suggestion}

=== HEALING RULE ===
{healing_rule}

=== FEW-SHOT EXAMPLES FROM MEMORY (may be empty) ===
{few_shot}

=== BROKEN SCRIPT ===
{broken_script}

Return ONLY the corrected Python source — no markdown, no explanation.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:python)?\s*\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _validate_syntax(source: str, tc_id: str) -> str:
    ast.parse(source)   # raises SyntaxError on invalid code
    return source


def _format_few_shot(fixes: list[dict]) -> str:
    if not fixes:
        return "(none available)"
    parts = []
    for i, fix in enumerate(fixes, 1):
        snippet = fix.get("healed_script", "")[:600]
        strategy = fix.get("strategy", fix.get("fix_suggestion", "N/A"))
        parts.append(
            f"[Example {i}]\n"
            f"error_type : {fix.get('error_type', 'N/A')}\n"
            f"strategy   : {strategy}\n"
            f"snippet    :\n{textwrap.indent(snippet, '    ')}"
        )
    return "\n\n".join(parts)


def _find_original_script(tc_id: str, test_scripts: list[str]) -> str | None:
    """
    Return the source of the script file that contains tc_id.

    Searches the file name and content for either the dashed or underscored
    form of the tc_id (e.g. "TC-001" or "TC_001" / "tc_001").
    """
    # Normalise: TC-001 → tc_001 (underscore form used in function names)
    tc_normalised = tc_id.lower().replace("-", "_")
    tc_lower      = tc_id.lower()       # dashed form, e.g. "tc-001"

    for path_str in test_scripts:
        path = Path(path_str)
        if not path.exists():
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            continue
        source_lower = source.lower()
        # Match: filename contains tc_001, OR source contains tc-001 OR tc_001
        if (
            tc_normalised in path.name.lower()
            or tc_lower     in source_lower
            or tc_normalised in source_lower
        ):
            return source

    return None


def _heal_one(
    llm,
    analysis: dict,
    broken_script: str,
    few_shot: list[dict],
    max_retries: int = 2,
) -> str:
    """Generate a healed script for one failure; retry on SyntaxError."""
    error_type: str = analysis.get("error_type", "unknown")
    healing_rule = _HEALING_RULES.get(error_type, _HEALING_RULES["unknown"])

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_USER_PROMPT_TEMPLATE.format(
                tc_id=analysis.get("tc_id", "?"),
                error_type=error_type,
                root_cause=analysis.get("root_cause", "")[:500],
                fix_suggestion=analysis.get("fix_suggestion", "")[:500],
                healing_rule=healing_rule,
                few_shot=_format_few_shot(few_shot),
                broken_script=broken_script[:3000],  # guard token budget
            )
        ),
    ]

    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):
        try:
            response = llm.invoke(messages)
            source = _strip_fences(response.content)
            _validate_syntax(source, analysis.get("tc_id", "?"))
            return source

        except SyntaxError as exc:
            last_error = exc
            logger.warning(
                "Healing Agent attempt %d/%d for %s — SyntaxError: %s",
                attempt, max_retries + 1, analysis.get("tc_id"), exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"The generated code has a SyntaxError: {exc}\n"
                            "Fix it and return ONLY the corrected raw Python source."
                        )
                    )
                )

    raise RuntimeError(
        f"Healing Agent failed for {analysis.get('tc_id')} "
        f"after {max_retries + 1} attempts. Last error: {last_error}"
    )


def _healed_path(tc_id: str) -> Path:
    fname = f"healed_{tc_id.lower().replace('-', '_')}.py"
    return HEALED_DIR / fname


# ── Agent node ────────────────────────────────────────────────────────────────

def healing_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: failure_analysis (is_healable subset) → healed_scripts.

    For every healable failure:
      1. 1.3 Stall detection — if the same patch hash was generated in a
         previous iteration, skip the LLM call and mark as un-healable.
      2. Loads the original broken script from disk.
      3. Retrieves few-shot fix examples from FAISS.
      4. Asks Groq to produce a corrected script.
      5. Validates syntax with ast.parse().
      6. Writes to tests/generated/healed/.
      7. Persists the fix to FAISS memory.
      8. Appends a feedback message to state.
    """
    healable = [a for a in state["failure_analysis"] if a.get("is_healable")]

    if not healable:
        print("✅ Healing Agent: No healable failures.")
        logger.info("Healing Agent: nothing to heal.")
        return {**state, "healed_scripts": [], "healing_hashes": state.get("healing_hashes") or {}}

    HEALED_DIR.mkdir(parents=True, exist_ok=True)

    llm    = config.get_groq_llm(temperature=0.1)
    memory = get_memory()

    # 1.3: load accumulated patch hashes from previous iterations
    healing_hashes: dict[str, list[str]] = dict(state.get("healing_hashes") or {})

    healed_paths: list[str] = []
    new_feedback: list[str] = list(state.get("feedback", []))

    for analysis in healable:
        tc_id: str = analysis.get("tc_id", "UNKNOWN")
        error_msg: str = (
            analysis.get("root_cause", "")
            or analysis.get("fix_suggestion", "")
        )

        # ── Load original broken script ───────────────────────────────────
        broken_script = _find_original_script(tc_id, state["test_scripts"])
        if broken_script is None:
            logger.warning("Healing Agent: could not find source for %s, skipping.", tc_id)
            new_feedback.append(f"[Healing] {tc_id}: source file not found, skipped.")
            continue

        # ── FAISS few-shot examples ───────────────────────────────────────
        similar_fixes = memory.retrieve_similar_fixes(error_msg, k=3)

        # ── Generate healed script ────────────────────────────────────────
        try:
            healed_source = _heal_one(llm, analysis, broken_script, similar_fixes)
        except RuntimeError as exc:
            logger.error("Healing Agent: %s", exc)
            new_feedback.append(f"[Healing] {tc_id}: healing failed — {exc}")
            continue

        # ── 1.3: Stall detection ──────────────────────────────────────────
        source_hash = hashlib.sha256(healed_source.encode()).hexdigest()[:16]
        prev_hashes = healing_hashes.get(tc_id, [])
        if source_hash in prev_hashes:
            print(
                f"  🔁 {tc_id}: stalled healing loop detected "
                f"(identical patch produced again), marking un-healable."
            )
            logger.warning(
                "Healing Agent: stalled for %s — patch hash %s already seen in %s",
                tc_id, source_hash, prev_hashes,
            )
            new_feedback.append(
                f"[Healing] {tc_id}: stalled — identical patch detected "
                f"(hash={source_hash}), skipping further attempts."
            )
            continue
        healing_hashes.setdefault(tc_id, []).append(source_hash)

        # ── Write to disk ─────────────────────────────────────────────────
        out_path = _healed_path(tc_id)
        out_path.write_text(healed_source, encoding="utf-8")
        healed_paths.append(str(out_path))

        logger.info("Healing Agent: healed %s → %s", tc_id, out_path)

        # ── Store fix in FAISS ────────────────────────────────────────────
        fix_record = {
            "tc_id": tc_id,
            "error_type": analysis.get("error_type"),
            "original_error": error_msg[:400],
            "fix_suggestion": analysis.get("fix_suggestion", ""),
            "strategy": _HEALING_RULES.get(analysis.get("error_type", "unknown"), ""),
            "healed_script": healed_source[:800],
        }
        memory.store_fix(fix_record)

        fix_summary = analysis.get("fix_suggestion", analysis.get("root_cause", ""))[:120]
        feedback_msg = f"Healed {tc_id}: {fix_summary}"
        new_feedback.append(feedback_msg)

        print(f"  🩹 {tc_id} healed → {out_path.name} | {analysis['error_type']}")

    memory.save()

    print(
        f"✅ Healing Agent: {len(healed_paths)}/{len(healable)} scripts healed → "
        f"{HEALED_DIR}"
    )
    logger.info(
        "✅ Healing Agent: %d/%d healed, written to %s",
        len(healed_paths), len(healable), HEALED_DIR,
    )

    return {
        **state,
        "healed_scripts": healed_paths,
        "feedback": new_feedback,
        "healing_hashes": healing_hashes,
    }
