"""
agents/script_agent.py — Script Agent
=======================================
Converts structured manual test cases into executable Playwright + pytest
scripts using Groq (LLaMA3-70b).  Output files are written under
tests/generated/test_{story_id}.py and a shared conftest.py is created.

Flow:
    state.test_cases  →  ChatGroq (per story group)
                      →  write tests/generated/test_{story_id}.py
                      →  state.test_scripts (list of file paths as str)
"""

from __future__ import annotations

import ast
import json
import logging
import re
import textwrap
from collections import defaultdict
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

import config
from graph.state import QAgentState

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

GENERATED_DIR: Path = config.GENERATED_TESTS_DIR
CONFTEST_PATH: Path = GENERATED_DIR / "conftest.py"

# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Senior Test Automation Engineer. Convert manual test cases into
production-quality Playwright + pytest SYNCHRONOUS scripts.

Rules you MUST follow:
  - Use `def test_{tc_id}_description(page):` functions (NOT async def) — NO @pytest.mark.asyncio.
  - YOU MUST include the `tc_id` (with hyphens replaced by underscores) in the test function name. For example, for TC-001, use `def test_TC_001_login(page):`.
  - Use the `page` fixture provided by pytest-playwright. DO NOT define your own `page` fixture.
  - Prefer `data-testid` selectors; fall back to ARIA roles then CSS.
  - Use `expect(locator)` assertions from `playwright.sync_api`.
  - DO NOT use `page.wait_for_selector()` for elements that are hidden (like <title> or <meta>). Use `expect(page).to_have_title(...)` instead.
  - Each function must have a docstring that is the test case title.
  - Group all test functions for the supplied story into ONE Python module.
  - Return ONLY the raw Python source code — no markdown fences, no prose.
  - The module must be syntactically valid Python 3.11+.
  - Import only: pytest, re, and playwright.sync_api items.
  - Do NOT import playwright.async_api. Do NOT use async/await anywhere.
  - Do NOT include a `if __name__ == "__main__"` block.
"""

_USER_PROMPT_TEMPLATE = """\
Generate a complete pytest module for the following test cases.

story_id : {story_id}
filename : test_{story_id_lower}.py

Test Cases (JSON):
{test_cases_json}

Return ONLY raw Python source — no markdown, no explanation.
"""

# ── Conftest ──────────────────────────────────────────────────────────────────

_CONFTEST_SOURCE = textwrap.dedent("""\
    \"\"\"
    conftest.py — Shared Playwright fixtures for QAgent generated tests.
    Uses pytest-playwright's built-in synchronous fixtures.
    \"\"\"
    import pytest


    # pytest-playwright automatically provides: browser, context, page fixtures.
    # Override browser_context_args to set default options if needed.
    @pytest.fixture(scope="session")
    def browser_context_args(browser_context_args):
        return {**browser_context_args, "ignore_https_errors": True}
""")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove ```python … ``` or ``` … ``` wrappers if present."""
    text = text.strip()
    # Match opening fence with optional language tag
    text = re.sub(r"^```(?:python)?\s*\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _to_sync(source: str) -> str:
    """
    Convert async playwright test code to sync pytest-playwright style.
    This is LLM-proof: works regardless of whether the LLM respected the prompt.
    """
    lines = source.splitlines()
    out = []
    for line in lines:
        # Drop @pytest.mark.asyncio and import pytest_asyncio
        if line.strip() in ("@pytest.mark.asyncio", "@pytest.mark.anyio"):
            continue
        if "import pytest_asyncio" in line:
            continue
        # Switch async_api → sync_api imports
        line = line.replace("from playwright.async_api import", "from playwright.sync_api import")
        line = line.replace("playwright.async_api", "playwright.sync_api")
        # async def test_ → def test_
        line = re.sub(r"^(\s*)async def (test_)", r"\1def \2", line)
        # strip leading `await ` from statements
        line = re.sub(r"\bawait\s+", "", line)
        out.append(line)
    return "\n".join(out)


def _validate_syntax(source: str, filename: str) -> str:
    """Raise SyntaxError (caught by caller) if source is not valid Python."""
    ast.parse(source)
    return source


def _generate_module(
    llm,
    story_id: str,
    test_cases: list[dict],
    max_retries: int = 2,
) -> str:
    """Ask the LLM to produce a pytest module; retry on syntax errors."""
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_USER_PROMPT_TEMPLATE.format(
                story_id=story_id,
                story_id_lower=story_id.lower().replace("-", "_"),
                test_cases_json=json.dumps(test_cases, indent=2),
            )
        ),
    ]

    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):
        try:
            response = llm.invoke(messages)
            source = _strip_fences(response.content)
            source = _to_sync(source)          # normalise to sync regardless of LLM output
            _validate_syntax(source, story_id)
            return source

        except SyntaxError as exc:
            last_error = exc
            logger.warning(
                "Script Agent attempt %d/%d for %s — SyntaxError: %s",
                attempt, max_retries + 1, story_id, exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"The generated code has a Python SyntaxError: {exc}\n"
                            "Fix it and return ONLY the corrected raw Python source."
                        )
                    )
                )

    raise RuntimeError(
        f"Script Agent failed for {story_id} after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )


def _write_file(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _ensure_conftest() -> None:
    if not CONFTEST_PATH.exists():
        _write_file(CONFTEST_PATH, _CONFTEST_SOURCE)
        logger.info("Script Agent: wrote conftest.py → %s", CONFTEST_PATH)


# ── Agent node ────────────────────────────────────────────────────────────────

def script_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: test_cases → test_scripts (file paths).

    Groups test cases by story_id, generates one pytest module per group,
    validates syntax with ast.parse(), then writes to tests/generated/.
    """
    llm = config.get_groq_llm(temperature=0.15)

    _ensure_conftest()

    # Group test cases by story_id ──────────────────────────────────────────
    groups: dict[str, list[dict]] = defaultdict(list)
    for tc in state["test_cases"]:
        groups[tc["story_id"]].append(tc)

    written_paths: list[str] = []

    for story_id, tcs in groups.items():
        filename = f"test_{story_id.lower().replace('-', '_')}.py"
        output_path = GENERATED_DIR / filename

        logger.info(
            "Script Agent: generating %s (%d test cases)…", filename, len(tcs)
        )

        source = _generate_module(llm, story_id, tcs)
        _write_file(output_path, source)
        written_paths.append(str(output_path))

        print(f"  ⚙️  {filename} — {len(tcs)} test(s) written, syntax ✅")
        logger.info("Script Agent: wrote %s", output_path)

    print(
        f"✅ Script Agent: Generated {len(written_paths)} test file(s) → "
        f"{GENERATED_DIR}"
    )
    logger.info(
        "✅ Script Agent: Generated %d test files under %s",
        len(written_paths), GENERATED_DIR,
    )

    return {**state, "test_scripts": written_paths}
