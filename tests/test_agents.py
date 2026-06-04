"""
tests/test_agents.py — Unit tests for QAgent agents
=====================================================
All LLM calls and FAISS I/O are mocked so no API keys or network
access are required.  Run with:

    pytest tests/test_agents.py -v

Architecture note: All agents call config.get_groq_llm() /
config.get_openrouter_llm() / config.get_gemini_llm(), which return a
_FallbackChainLLM wrapper.  Tests must mock THOSE factory functions,
not the underlying ChatGroq / ChatGoogleGenerativeAI classes directly.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Suppress noisy startup banner from config.py during tests
os.environ.setdefault("QAGENT_QUIET", "1")

# ── Ensure project root is on sys.path ───────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from graph.state import initial_state, QAgentState


# ═══════════════════════════════════════════════════════════════════════════════
# Shared fixtures & helpers
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_BRD = """\
The platform shall allow registered users to log in using their email and
password. Passwords must be at least 8 characters. Users who fail login 3
times must be locked out for 15 minutes. A "Forgot password" link must be
visible on the login page.
"""

# Full 7-field schema required by the UserStory Pydantic model
SAMPLE_USER_STORIES = [
    {
        "story_id": "US-001",
        "title": "User Login with Email and Password",
        "story": "As a registered user, I want to log in with email and password, so that I can access my account.",
        "acceptance_criteria": [
            "Given a registered user, When they enter valid credentials, Then login succeeds",
            "Given a registered user, When they enter wrong password, Then login fails",
            "Given a registered user, When they fail 3 times, Then account locks for 15 minutes",
        ],
        "priority": "High",
        "estimation": 3,
        "description": "Core authentication feature. Ensures users can securely access their accounts using email/password credentials with lockout protection.",
    }
]

SAMPLE_REVIEWED_STORIES = [
    {
        **SAMPLE_USER_STORIES[0],
        "qa_notes": [],
        "needs_review": False,
        "qa_confidence": 0.9,
    }
]

# Uses valid Literal priority: "Critical"|"High"|"Medium"|"Low"
SAMPLE_TEST_CASES = [
    {
        "tc_id": "TC-US-001-POS-001",
        "story_id": "US-001",
        "title": "Login with valid credentials",
        "type": "positive",
        "preconditions": ["User is registered"],
        "steps": [
            "Step 1: Navigate to /login",
            "Step 2: Enter valid email and password",
            "Step 3: Click Login button",
        ],
        "expected_result": "User is redirected to the dashboard",
        "priority": "High",
        "test_url": "*URL_of_the_application*",
    }
]

SAMPLE_EXECUTION_RESULTS_FAIL = [
    {
        "tc_id": "TC-001",
        "file": "tests/generated/test_us_001.py",
        "status": "failed",
        "duration": 1.5,
        "error_message": "Locator '#submit-btn' not found in DOM",
        "stdout": "",
        "traceback": "playwright._impl._errors.Error: Locator not found: #submit-btn",
    }
]

SAMPLE_EXECUTION_RESULTS_PASS = [
    {
        "tc_id": "TC-001",
        "file": "tests/generated/test_us_001.py",
        "status": "passed",
        "duration": 0.8,
        "error_message": "",
        "stdout": "PASSED",
        "traceback": "",
    }
]

VALID_PLAYWRIGHT_SCRIPT = """\
import pytest
from playwright.sync_api import Page, expect


def test_TC_001_login_happy_path(page: Page):
    \"\"\"Login with valid credentials\"\"\"
    page.goto("https://example.com/login")
    page.wait_for_selector("[data-testid='email']")
    page.fill("[data-testid='email']", "user@example.com")
    page.fill("[data-testid='password']", "ValidPass1!")
    page.click("[data-testid='submit']")
    page.wait_for_selector("[data-testid='dashboard']")
    assert page.title() != ""
"""

HEALED_PLAYWRIGHT_SCRIPT = """\
import pytest
from playwright.sync_api import Page, expect


def test_TC_001_login_happy_path(page: Page):
    \"\"\"Login with valid credentials (healed)\"\"\"
    page.goto("https://example.com/login")
    page.wait_for_selector("[data-testid='submit-btn']", timeout=10000)
    page.fill("[data-testid='email']", "user@example.com")
    page.fill("[data-testid='password']", "ValidPass1!")
    page.click("[data-testid='submit-btn']")
    page.wait_for_selector("[data-testid='dashboard']")
    assert page.title() != ""
"""


def _make_llm_response(content: str) -> MagicMock:
    """Return a mock LLM response with `.content = content`."""
    resp = MagicMock()
    resp.content = content
    return resp


def _make_llm_mock(content: str) -> MagicMock:
    """
    Return a MagicMock that behaves like a _FallbackChainLLM:
    .invoke() returns a mock response with .content = content.
    """
    llm = MagicMock()
    llm.invoke.return_value = _make_llm_response(content)
    llm.stream.return_value = iter([])
    return llm


# ═══════════════════════════════════════════════════════════════════════════════
# test_requirement_agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequirementAgent:
    def _mock_response(self) -> str:
        return json.dumps(SAMPLE_USER_STORIES)

    @patch("agents.requirement_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_returns_user_stories(self, mock_get_llm, mock_get_memory):
        mock_get_llm.return_value = _make_llm_mock(self._mock_response())
        mock_get_memory.return_value.retrieve_brd_cache.return_value = None
        mock_get_memory.return_value.store_brd_run = MagicMock()
        mock_get_memory.return_value.save = MagicMock()

        from agents.requirement_agent import requirement_agent

        state = initial_state(SAMPLE_BRD)
        result = requirement_agent(state)

        assert isinstance(result["user_stories"], list)
        assert len(result["user_stories"]) >= 1

    @patch("agents.requirement_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_story_id_format(self, mock_get_llm, mock_get_memory):
        mock_get_llm.return_value = _make_llm_mock(self._mock_response())
        mock_get_memory.return_value.retrieve_brd_cache.return_value = None
        mock_get_memory.return_value.store_brd_run = MagicMock()
        mock_get_memory.return_value.save = MagicMock()

        from agents.requirement_agent import requirement_agent

        state = initial_state(SAMPLE_BRD)
        result = requirement_agent(state)

        for story in result["user_stories"]:
            assert re.match(r"^US-\d{3}$", story["story_id"]), (
                f"story_id '{story['story_id']}' does not match US-XXX"
            )

    @patch("agents.requirement_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_required_fields_present(self, mock_get_llm, mock_get_memory):
        mock_get_llm.return_value = _make_llm_mock(self._mock_response())
        mock_get_memory.return_value.retrieve_brd_cache.return_value = None
        mock_get_memory.return_value.store_brd_run = MagicMock()
        mock_get_memory.return_value.save = MagicMock()

        from agents.requirement_agent import requirement_agent

        result = requirement_agent(initial_state(SAMPLE_BRD))

        for story in result["user_stories"]:
            assert "story_id" in story
            assert "story" in story
            assert "acceptance_criteria" in story
            assert isinstance(story["acceptance_criteria"], list)
            assert len(story["acceptance_criteria"]) >= 1

    @patch("agents.requirement_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_retries_on_bad_json(self, mock_get_llm, mock_get_memory):
        """Agent should retry and succeed on second attempt."""
        mock_get_memory.return_value.retrieve_brd_cache.return_value = None
        mock_get_memory.return_value.store_brd_run = MagicMock()
        mock_get_memory.return_value.save = MagicMock()

        llm_mock = MagicMock()
        llm_mock.invoke.side_effect = [
            _make_llm_response("not valid json at all"),
            _make_llm_response(self._mock_response()),
            _make_llm_response(self._mock_response()),  # extra safety
        ]
        mock_get_llm.return_value = llm_mock

        from agents.requirement_agent import requirement_agent

        result = requirement_agent(initial_state(SAMPLE_BRD))
        assert len(result["user_stories"]) >= 1

    @patch("agents.requirement_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_cache_hit_returns_without_llm_call(self, mock_get_llm, mock_get_memory):
        """When BRD cache has a hit, no LLM call should be made."""
        mock_get_memory.return_value.retrieve_brd_cache.return_value = SAMPLE_USER_STORIES

        from agents.requirement_agent import requirement_agent

        result = requirement_agent(initial_state(SAMPLE_BRD))

        mock_get_llm.assert_not_called()
        assert result["user_stories"] == SAMPLE_USER_STORIES


# ═══════════════════════════════════════════════════════════════════════════════
# test_qa_review_agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestQAReviewAgent:
    def _reviewed_story(self, needs_review: bool, confidence: float) -> dict:
        return {
            **SAMPLE_USER_STORIES[0],
            "qa_notes": ["Vague term 'easy' detected"] if needs_review else [],
            "needs_review": needs_review,
            "qa_confidence": confidence,
        }

    @patch("config.get_openrouter_llm")
    def test_confidence_is_float_in_range(self, mock_get_llm):
        mock_get_llm.return_value = _make_llm_mock(
            json.dumps(self._reviewed_story(False, 0.92))
        )
        from agents.qa_review_agent import qa_review_agent

        state = {**initial_state(SAMPLE_BRD), "user_stories": SAMPLE_USER_STORIES}
        result = qa_review_agent(state)

        for story in result["reviewed_stories"]:
            assert isinstance(story["qa_confidence"], float)
            assert 0.0 <= story["qa_confidence"] <= 1.0

    @patch("config.get_openrouter_llm")
    def test_needs_review_true_for_vague_stories(self, mock_get_llm):
        mock_get_llm.return_value = _make_llm_mock(
            json.dumps(self._reviewed_story(True, 0.55))
        )
        from agents.qa_review_agent import qa_review_agent

        vague_story = {
            **SAMPLE_USER_STORIES[0],
            "story": "As a user, I want an easy and fast login, so that it is simple.",
        }
        state = {**initial_state(SAMPLE_BRD), "user_stories": [vague_story]}
        result = qa_review_agent(state)

        assert any(s["needs_review"] for s in result["reviewed_stories"])

    @patch("config.get_openrouter_llm")
    def test_feedback_populated_when_needs_review(self, mock_get_llm):
        mock_get_llm.return_value = _make_llm_mock(
            json.dumps(self._reviewed_story(True, 0.50))
        )
        from agents.qa_review_agent import qa_review_agent

        state = {**initial_state(SAMPLE_BRD), "user_stories": SAMPLE_USER_STORIES}
        result = qa_review_agent(state)

        assert any("QA Review" in msg for msg in result["feedback"])


# ═══════════════════════════════════════════════════════════════════════════════
# test_coverage_agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoverageAgent:
    def _gap_response(self) -> str:
        return json.dumps({
            "gaps": [
                {
                    "gap_id": "GAP-001",
                    "story_id": "US-001",
                    "gap_type": "negative",
                    "description": "No test for login with incorrect password",
                    "recommendation": "Add TC: login fails with wrong password",
                    "severity": "High",
                }
            ],
            "derived_test_cases": [
                {
                    "tc_id": "TC-US-001-NEG-001",
                    "story_id": "US-001",
                    "title": "Login fails with wrong password",
                    "type": "negative",
                    "preconditions": ["User is registered"],
                    "steps": [
                        "Step 1: Navigate to /login",
                        "Step 2: Enter wrong password",
                        "Step 3: Click Login",
                    ],
                    "expected_result": "Error message displayed",
                    "priority": "High",
                    "test_url": "*URL_of_the_application*",
                }
            ],
        })

    @patch("config.get_openrouter_llm")
    def test_negative_gap_detected(self, mock_get_llm):
        mock_get_llm.return_value = _make_llm_mock(self._gap_response())

        from agents.coverage_agent import coverage_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "reviewed_stories": SAMPLE_REVIEWED_STORIES,
            "test_cases": SAMPLE_TEST_CASES,
        }
        result = coverage_agent(state)

        gap_strs = result["coverage_gaps"]
        assert len(gap_strs) >= 1
        assert any("negative" in g.lower() or "GAP-001" in g for g in gap_strs)

    @patch("config.get_openrouter_llm")
    def test_new_test_cases_added(self, mock_get_llm):
        mock_get_llm.return_value = _make_llm_mock(self._gap_response())

        from agents.coverage_agent import coverage_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "reviewed_stories": SAMPLE_REVIEWED_STORIES,
            "test_cases": SAMPLE_TEST_CASES,
        }
        result = coverage_agent(state)

        assert len(result["test_cases"]) > len(SAMPLE_TEST_CASES)

    @patch("config.get_openrouter_llm")
    def test_no_gaps_returns_empty(self, mock_get_llm):
        mock_get_llm.return_value = _make_llm_mock(
            json.dumps({"gaps": [], "derived_test_cases": []})
        )

        from agents.coverage_agent import coverage_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "reviewed_stories": SAMPLE_REVIEWED_STORIES,
            "test_cases": SAMPLE_TEST_CASES,
        }
        result = coverage_agent(state)

        assert result["coverage_gaps"] == []
        assert len(result["test_cases"]) == len(SAMPLE_TEST_CASES)


# ═══════════════════════════════════════════════════════════════════════════════
# test_failure_analysis_agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestFailureAnalysisAgent:
    def _analysis_response(self) -> str:
        return json.dumps({
            "tc_id": "TC-001",
            "error_type": "selector_changed",
            "root_cause": "The CSS selector #submit-btn no longer matches any element in the DOM.",
            "confidence": 0.92,
            "fix_suggestion": "Replace #submit-btn with page.get_by_test_id('submit-btn')",
            "is_healable": True,
        })

    @patch("agents.failure_analysis_agent.get_memory")
    @patch("config.get_openrouter_llm")
    def test_error_type_selector_changed(self, mock_get_llm, mock_get_memory):
        mock_get_llm.return_value = _make_llm_mock(self._analysis_response())
        mock_get_memory.return_value.retrieve_similar_failures.return_value = []
        mock_get_memory.return_value.store_failure = MagicMock()
        mock_get_memory.return_value.save = MagicMock()

        from agents.failure_analysis_agent import failure_analysis_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "execution_results": SAMPLE_EXECUTION_RESULTS_FAIL,
        }
        result = failure_analysis_agent(state)

        assert len(result["failure_analysis"]) == 1
        analysis = result["failure_analysis"][0]
        assert analysis["error_type"] == "selector_changed"

    @patch("agents.failure_analysis_agent.get_memory")
    @patch("config.get_openrouter_llm")
    def test_is_healable_true(self, mock_get_llm, mock_get_memory):
        mock_get_llm.return_value = _make_llm_mock(self._analysis_response())
        mock_get_memory.return_value.retrieve_similar_failures.return_value = []
        mock_get_memory.return_value.store_failure = MagicMock()
        mock_get_memory.return_value.save = MagicMock()

        from agents.failure_analysis_agent import failure_analysis_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "execution_results": SAMPLE_EXECUTION_RESULTS_FAIL,
        }
        result = failure_analysis_agent(state)

        assert result["failure_analysis"][0]["is_healable"] is True

    @patch("agents.failure_analysis_agent.get_memory")
    @patch("config.get_openrouter_llm")
    def test_no_failures_skipped(self, mock_get_llm, mock_get_memory):
        from agents.failure_analysis_agent import failure_analysis_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "execution_results": SAMPLE_EXECUTION_RESULTS_PASS,
        }
        result = failure_analysis_agent(state)

        assert result["failure_analysis"] == []
        mock_get_llm.return_value.invoke.assert_not_called()

    @patch("agents.failure_analysis_agent.get_memory")
    @patch("config.get_openrouter_llm")
    def test_store_failure_called(self, mock_get_llm, mock_get_memory):
        mock_get_llm.return_value = _make_llm_mock(self._analysis_response())
        mock_memory = MagicMock()
        mock_memory.retrieve_similar_failures.return_value = []
        mock_get_memory.return_value = mock_memory

        from agents.failure_analysis_agent import failure_analysis_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "execution_results": SAMPLE_EXECUTION_RESULTS_FAIL,
        }
        failure_analysis_agent(state)

        mock_memory.store_failure.assert_called_once()
        mock_memory.save.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# test_healing_agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealingAgent:
    FAILURE_ANALYSIS = [
        {
            "tc_id": "TC-001",
            "error_type": "selector_changed",
            "root_cause": "The CSS selector #submit-btn no longer matches any element in the DOM.",
            "confidence": 0.92,
            "fix_suggestion": "Replace #submit-btn with page.get_by_test_id('submit-btn')",
            "is_healable": True,
        }
    ]

    @patch("agents.healing_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_healed_script_is_valid_python(self, mock_get_llm, mock_get_memory, tmp_path):
        mock_get_llm.return_value = _make_llm_mock(HEALED_PLAYWRIGHT_SCRIPT)
        mock_memory = MagicMock()
        mock_memory.retrieve_similar_fixes.return_value = []
        mock_get_memory.return_value = mock_memory

        # Create a fake "original" script file so healing_agent can find it
        script_file = tmp_path / "test_us_001.py"
        script_file.write_text(VALID_PLAYWRIGHT_SCRIPT, encoding="utf-8")

        import agents.healing_agent as ha
        original_healed_dir = ha.HEALED_DIR
        ha.HEALED_DIR = tmp_path / "healed"
        ha.HEALED_DIR.mkdir()

        try:
            from agents.healing_agent import healing_agent

            state = {
                **initial_state(SAMPLE_BRD),
                "test_scripts": [str(script_file)],
                "failure_analysis": self.FAILURE_ANALYSIS,
            }
            result = healing_agent(state)
        finally:
            ha.HEALED_DIR = original_healed_dir

        assert len(result["healed_scripts"]) == 1
        healed_path = Path(result["healed_scripts"][0])
        healed_source = healed_path.read_text(encoding="utf-8")
        # Must parse without SyntaxError
        ast.parse(healed_source)

    @patch("agents.healing_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_store_fix_called_once(self, mock_get_llm, mock_get_memory, tmp_path):
        mock_get_llm.return_value = _make_llm_mock(HEALED_PLAYWRIGHT_SCRIPT)
        mock_memory = MagicMock()
        mock_memory.retrieve_similar_fixes.return_value = []
        mock_get_memory.return_value = mock_memory

        script_file = tmp_path / "test_us_001.py"
        script_file.write_text(VALID_PLAYWRIGHT_SCRIPT, encoding="utf-8")

        import agents.healing_agent as ha
        original_healed_dir = ha.HEALED_DIR
        ha.HEALED_DIR = tmp_path / "healed"
        ha.HEALED_DIR.mkdir()

        try:
            from agents.healing_agent import healing_agent

            state = {
                **initial_state(SAMPLE_BRD),
                "test_scripts": [str(script_file)],
                "failure_analysis": self.FAILURE_ANALYSIS,
            }
            healing_agent(state)
        finally:
            ha.HEALED_DIR = original_healed_dir

        mock_memory.store_fix.assert_called_once()

    @patch("agents.healing_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_feedback_appended(self, mock_get_llm, mock_get_memory, tmp_path):
        mock_get_llm.return_value = _make_llm_mock(HEALED_PLAYWRIGHT_SCRIPT)
        mock_memory = MagicMock()
        mock_memory.retrieve_similar_fixes.return_value = []
        mock_get_memory.return_value = mock_memory

        script_file = tmp_path / "test_us_001.py"
        script_file.write_text(VALID_PLAYWRIGHT_SCRIPT, encoding="utf-8")

        import agents.healing_agent as ha
        original_healed_dir = ha.HEALED_DIR
        ha.HEALED_DIR = tmp_path / "healed"
        ha.HEALED_DIR.mkdir()

        try:
            from agents.healing_agent import healing_agent

            state = {
                **initial_state(SAMPLE_BRD),
                "test_scripts": [str(script_file)],
                "failure_analysis": self.FAILURE_ANALYSIS,
                "feedback": [],
            }
            result = healing_agent(state)
        finally:
            ha.HEALED_DIR = original_healed_dir

        assert any("Healed TC-001" in msg for msg in result["feedback"])

    @patch("agents.healing_agent.get_memory")
    def test_no_healable_failures_returns_empty(self, mock_get_memory):
        from agents.healing_agent import healing_agent

        state = {
            **initial_state(SAMPLE_BRD),
            "test_scripts": [],
            "failure_analysis": [
                {**TestHealingAgent.FAILURE_ANALYSIS[0], "is_healable": False}
            ],
        }
        result = healing_agent(state)
        assert result["healed_scripts"] == []

    @patch("agents.healing_agent.get_memory")
    @patch("config.get_groq_llm")
    def test_stall_detection_skips_repeated_patch(self, mock_get_llm, mock_get_memory, tmp_path):
        """If the same patch hash is produced twice, agent skips and marks un-healable."""
        mock_get_llm.return_value = _make_llm_mock(HEALED_PLAYWRIGHT_SCRIPT)
        mock_memory = MagicMock()
        mock_memory.retrieve_similar_fixes.return_value = []
        mock_get_memory.return_value = mock_memory

        script_file = tmp_path / "test_us_001.py"
        script_file.write_text(VALID_PLAYWRIGHT_SCRIPT, encoding="utf-8")

        import agents.healing_agent as ha
        import hashlib, re as _re

        original_healed_dir = ha.HEALED_DIR
        ha.HEALED_DIR = tmp_path / "healed"
        ha.HEALED_DIR.mkdir()

        # Compute the hash the same way healing_agent does:
        # _strip_fences strips leading/trailing whitespace, so we must match that.
        stripped = HEALED_PLAYWRIGHT_SCRIPT.strip()
        existing_hash = hashlib.sha256(stripped.encode()).hexdigest()[:16]

        try:
            from agents.healing_agent import healing_agent

            state = {
                **initial_state(SAMPLE_BRD),
                "test_scripts": [str(script_file)],
                "failure_analysis": self.FAILURE_ANALYSIS,
                "healing_hashes": {"TC-001": [existing_hash]},
                "feedback": [],
            }
            result = healing_agent(state)
        finally:
            ha.HEALED_DIR = original_healed_dir

        # Stall detected → no scripts healed, feedback mentions stall
        assert result["healed_scripts"] == []
        assert any("stalled" in msg.lower() for msg in result["feedback"])



# ═══════════════════════════════════════════════════════════════════════════════
# test_feedback_loop  (integration-level with fully mocked agents)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeedbackLoop:
    """
    Validates the LangGraph conditional routing logic without real LLM calls.
    Each agent is replaced with a stub that returns a predictable state delta.
    """

    @staticmethod
    def _stub_requirement(state):
        return {**state, "user_stories": SAMPLE_USER_STORIES}

    @staticmethod
    def _stub_qa_review(state):
        return {**state, "reviewed_stories": SAMPLE_REVIEWED_STORIES}

    @staticmethod
    def _stub_test_case(state):
        return {**state, "test_cases": SAMPLE_TEST_CASES}

    @staticmethod
    def _stub_coverage(state):
        return {**state, "coverage_gaps": []}

    @staticmethod
    def _stub_script(state):
        return {**state, "test_scripts": []}

    @staticmethod
    def _stub_execution(state):
        # Always return a failure so the loop keeps going
        return {**state, "execution_results": SAMPLE_EXECUTION_RESULTS_FAIL}

    @staticmethod
    def _stub_analysis(state):
        return {
            **state,
            "failure_analysis": [
                {
                    "tc_id": "TC-001",
                    "error_type": "selector_changed",
                    "root_cause": "Selector not found in DOM because UI changed.",
                    "confidence": 0.9,
                    "fix_suggestion": "Use data-testid selector instead.",
                    "is_healable": True,
                }
            ],
        }

    @staticmethod
    def _stub_healing(state):
        return {
            **state,
            "healed_scripts": [],
            "iteration": state.get("iteration", 0) + 1,
        }

    def test_iteration_increments(self):
        from graph.workflow import should_continue

        state = {
            **initial_state(SAMPLE_BRD),
            "iteration": 0,
            "status": "running",
            "failure_analysis": [{"error_type": "timeout", "is_healable": True}],
            "reviewed_stories": [{"needs_review": False}],
        }

        # First pass: should loop back (not all_passed, iteration < 3)
        route = should_continue(state)
        assert route in ("script", "qa_review")

        # After 3 iterations: must stop
        state["iteration"] = 3
        assert should_continue(state) == "end"

    def test_stops_after_3_iterations(self):
        from graph.workflow import should_continue

        state = {
            **initial_state(SAMPLE_BRD),
            "iteration": 3,
            "status": "running",
            "failure_analysis": [{"error_type": "selector_changed", "is_healable": True}],
            "reviewed_stories": [{"needs_review": False}],
        }
        assert should_continue(state) == "end"

    def test_routes_to_end_on_all_passed(self):
        from graph.workflow import should_continue

        state = {**initial_state(SAMPLE_BRD), "iteration": 1, "status": "all_passed",
                 "failure_analysis": [], "reviewed_stories": []}
        assert should_continue(state) == "end"

    def test_routes_to_qa_review_on_logic_error(self):
        from graph.workflow import should_continue

        state = {
            **initial_state(SAMPLE_BRD),
            "iteration": 1,
            "status": "running",
            "failure_analysis": [{"error_type": "logic_error", "is_healable": True}],
            "reviewed_stories": [{"needs_review": False}],
        }
        assert should_continue(state) == "qa_review"

    def test_routes_to_qa_review_on_ambiguous_story(self):
        from graph.workflow import should_continue

        state = {
            **initial_state(SAMPLE_BRD),
            "iteration": 1,
            "status": "running",
            "failure_analysis": [{"error_type": "timeout", "is_healable": True}],
            "reviewed_stories": [{"needs_review": True}],
        }
        assert should_continue(state) == "qa_review"

    def test_routes_to_script_for_healable_non_logic(self):
        from graph.workflow import should_continue

        state = {
            **initial_state(SAMPLE_BRD),
            "iteration": 1,
            "status": "running",
            "failure_analysis": [{"error_type": "selector_changed", "is_healable": True}],
            "reviewed_stories": [{"needs_review": False}],
        }
        assert should_continue(state) == "script"

    def test_routes_to_test_case_on_design_errors(self):
        from graph.workflow import should_continue

        state = {
            **initial_state(SAMPLE_BRD),
            "iteration": 1,
            "status": "running",
            "failure_analysis": [{"error_type": "assertion_logic", "is_healable": True}],
            "reviewed_stories": [{"needs_review": False}],
        }
        assert should_continue(state) == "test_case"

    @patch("graph.workflow.healing_agent")
    @patch("graph.workflow.failure_analysis_agent")
    @patch("graph.workflow.execution_agent")
    @patch("graph.workflow.script_agent")
    @patch("graph.workflow.coverage_agent")
    @patch("graph.workflow.test_case_agent")
    @patch("graph.workflow.qa_review_agent")
    @patch("graph.workflow.requirement_agent")
    def test_full_loop_stops_at_max_iterations(
        self,
        mock_req, mock_qa, mock_tc, mock_cov,
        mock_script, mock_exec, mock_analysis, mock_healing,
    ):
        """
        Wire all agents to stubs and verify the compiled graph terminates
        at max iterations (3) even when tests keep failing.
        """
        mock_req.side_effect      = self._stub_requirement
        mock_qa.side_effect       = self._stub_qa_review
        mock_tc.side_effect       = self._stub_test_case
        mock_cov.side_effect      = self._stub_coverage
        mock_script.side_effect   = self._stub_script
        mock_exec.side_effect     = self._stub_execution
        mock_analysis.side_effect = self._stub_analysis
        mock_healing.side_effect  = self._stub_healing

        from graph.workflow import run_pipeline

        final = run_pipeline(SAMPLE_BRD)

        assert final["iteration"] <= 3
        assert final["status"] != "all_passed"   # stubs always fail
