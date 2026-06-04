"""
agents/test_case_agent.py — Test Case Agent
============================================
Generates structured manual test cases (positive, negative, edge)
from QA-reviewed user stories using Groq (LLaMA3-70b).

Upgraded to match the Test Case Generator agent specification:
  - Rich TC-ID format:  TC-US-123-POS-001 / TC-US-123-NEG-001 / TC-US-123-EDG-001
  - Priority scale:     Critical / High / Medium / Low
  - test_url field:     placeholder URL for non-BDD (manual) test cases
  - 1–3 variations per story; each variation MUST have unique steps + expected result
  - Uniqueness validator: rejects batches where any two TCs share identical step lists
  - Numbered step format enforced: "Step N: <action>"
  - Minimum 3 TCs per story; min 3 steps per TC
  - Retry messages list all specific broken rules

Flow:
    state.reviewed_stories  →  ChatGroq (per story)
                            →  state.test_cases (list[dict])
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

import config
from agents.utils import extract_json, run_parallel
from graph.state import QAgentState
from memory.faiss_store import get_memory

logger = logging.getLogger(__name__)

# ── Pydantic model ────────────────────────────────────────────────────────────

# TC ID:  TC-US-123-POS-001  |  TC-US-123-NEG-002  |  TC-US-123-EDG-001
_TC_ID_PATTERN = re.compile(r"^TC-US-\d{3,}-(?:POS|NEG|EDG)-\d{3}$")
_STEP_NUMBER_PATTERN = re.compile(r"^Step\s+\d+\s*:", re.IGNORECASE)


class TestCase(BaseModel):
    tc_id: str = Field(
        ...,
        description="Format: TC-US-NNN-{POS|NEG|EDG}-NNN  e.g. TC-US-123-POS-001",
    )
    story_id: str = Field(..., pattern=r"^US-\d{3,}$")
    title: str = Field(..., min_length=5)
    type: Literal["positive", "negative", "edge"]
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(..., min_length=3)
    expected_result: str = Field(..., min_length=10)
    priority: Literal["Critical", "High", "Medium", "Low"]
    test_url: str = Field(
        default="*URL_of_the_application*",
        description="Target URL for this test case (placeholder if not yet known)",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("tc_id")
    @classmethod
    def tc_id_format(cls, v: str) -> str:
        if not _TC_ID_PATTERN.match(v):
            raise ValueError(
                f"tc_id '{v}' must match TC-US-NNN-{{POS|NEG|EDG}}-NNN "
                "(e.g. TC-US-123-POS-001)"
            )
        return v

    @field_validator("steps")
    @classmethod
    def steps_must_be_numbered(cls, steps: list[str]) -> list[str]:
        bad = [s for s in steps if not _STEP_NUMBER_PATTERN.match(s.strip())]
        if bad:
            raise ValueError(
                f"{len(bad)} step(s) not numbered. "
                "Each step must start with 'Step N:' (e.g. 'Step 1: Navigate to ...')."
            )
        non_empty = [s for s in steps if s.strip()]
        if len(non_empty) < 3:
            raise ValueError("Each test case must have at least 3 non-empty steps.")
        return steps


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Senior QA Automation Engineer generating structured manual test cases \
for Financial and Insurance domain applications.

Core generation rules:
1. Generate 1–3 test cases per user story — one per distinct testing need.
2. EVERY variation MUST have DIFFERENT steps and a DIFFERENT expected result.
   Do NOT copy-paste steps between variations — this is a critical quality rule.
3. Create variations that verify genuinely different things:
   - Positive (POS): happy-path flows using typical valid inputs
   - Negative (NEG): invalid inputs, boundary violations, unauthorized access
   - Edge (EDG): boundary values (min/max), empty inputs, extreme limits,
     unusual-but-valid data (e.g. "O'Brien", ZIP "00001" vs "99999")
4. Minimum 3 test cases per story (at least 1 POS, 1 NEG, 1 EDG).
5. Minimum 3 numbered steps per test case ("Step 1: ...", "Step 2: ...", ...).
6. Derive edge cases directly from the acceptance criteria values and constraints.
7. Include specific data values in steps (e.g. "Enter ZIP code '12345'").
8. Priorities: Critical = system-breaking, High = critical feature, \
   Medium = important, Low = nice-to-have.

TC ID format: TC-US-{NNN}-{POS|NEG|EDG}-{NNN}
  Example: TC-US-123-POS-001, TC-US-123-NEG-001, TC-US-123-EDG-001

Financial & Insurance domain context — test for:
  - Data validation (account numbers, policy IDs, ZIP codes, dates)
  - Monetary boundary conditions (zero, negative, over-limit amounts)
  - Workflow states (submitted → under review → approved → paid)
  - Role-based access (Agent vs Policyholder vs Underwriter)
  - Regulatory constraints (coverage limits, compliance rules)
"""

_USER_PROMPT_TEMPLATE = """\
Generate test cases for the following user story.

Return ONLY a valid JSON array — no markdown fences, no explanation.
Each element MUST match this exact schema:

{{
  "tc_id":           "TC-US-{story_num}-POS-001",
  "story_id":        "{story_id}",
  "title":           "<short descriptive title — what is being tested>",
  "type":            "positive" | "negative" | "edge",
  "preconditions":   ["<prerequisite 1>", "<prerequisite 2>"],
  "steps":           [
    "Step 1: <specific action with exact data value>",
    "Step 2: <specific action>",
    "Step 3: <observe or verify>"
  ],
  "expected_result": "<specific, measurable outcome — what the tester should observe>",
  "priority":        "Critical" | "High" | "Medium" | "Low",
  "test_url":        "*URL_of_the_application*"
}}

STRICT rules:
- tc_id MUST be TC-US-{story_num}-{{POS|NEG|EDG}}-NNN
- Generate at least 3 test cases (at least 1 positive, 1 negative, 1 edge)
- Every variation MUST have COMPLETELY DIFFERENT steps and expected_result
  (do NOT copy-paste steps — each TC must test something distinct)
- Each "steps" list must have at least 3 items
- Every step must start with "Step N:" (e.g. "Step 1: Navigate to ...")
- Edge cases MUST use specific boundary values from the acceptance criteria
- "priority" must be one of: Critical, High, Medium, Low

User Story:
{story_json}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    return extract_json(text)


def _steps_fingerprint(steps: list[str]) -> str:
    """Normalised fingerprint of a step list for duplicate detection."""
    return "|".join(s.strip().lower() for s in steps)


def _parse_and_validate(raw: str, story_id: str) -> list[dict]:
    """
    Parse the LLM response, validate every TestCase schema, and reject the
    entire batch if any two test cases share identical step lists (copy-paste
    violation per the quality standard).
    """
    data = json.loads(_extract_json(raw))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")
    if len(data) < 3:
        raise ValueError(
            f"Only {len(data)} test case(s) returned for {story_id}; minimum is 3."
        )

    validated: list[dict] = []
    seen_fingerprints: dict[str, str] = {}  # fingerprint → tc_id

    for item in data:
        tc = TestCase.model_validate(item)
        fp = _steps_fingerprint(tc.steps)
        if fp in seen_fingerprints:
            raise ValueError(
                f"Duplicate steps detected: {tc.tc_id} and {seen_fingerprints[fp]} "
                "have identical step lists. Every test case variation MUST have "
                "completely different steps and a different expected result."
            )
        seen_fingerprints[fp] = tc.tc_id
        validated.append(tc.model_dump())

    return validated


def _story_num(story_id: str) -> str:
    """Extract the numeric portion from 'US-123' → '123'."""
    return story_id.split("-")[-1]


def _generate_for_story(
    llm,
    story: dict,
    max_retries: int = 2,
) -> list[dict]:
    """Run the LLM for a single story with retry on parse/validation errors."""
    sid = story.get("story_id", "US-000")
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_USER_PROMPT_TEMPLATE.format(
                story_json=json.dumps(story, indent=2),
                story_id=sid,
                story_num=_story_num(sid),
            )
        ),
    ]

    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):
        try:
            response = llm.invoke(messages, json_mode=True)
            return _parse_and_validate(response.content, sid)

        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Test Case Agent attempt %d/%d for %s — %s: %s",
                attempt, max_retries + 1, sid, type(exc).__name__, exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"Your previous response caused a validation error: {exc}\n\n"
                            "Fix ALL issues and return ONLY a valid JSON array.\n"
                            "Reminder of STRICT rules:\n"
                            f"- tc_id MUST be TC-US-{_story_num(sid)}-{{POS|NEG|EDG}}-NNN\n"
                            "- At least 3 test cases (1 positive, 1 negative, 1 edge)\n"
                            "- Each variation MUST have COMPLETELY DIFFERENT steps\n"
                            "- Each 'steps' list must have at least 3 items\n"
                            "- Every step must start with 'Step N:'\n"
                            "- 'priority' must be: Critical, High, Medium, or Low"
                        )
                    )
                )

    raise RuntimeError(
        f"Test Case Agent failed for story {sid} "
        f"after {max_retries + 1} attempts. Last error: {last_error}"
    )


# ── Agent node ───────────────────────────────────────────────────────────────────────

def test_case_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: reviewed_stories → test_cases.

    Runs all story analyses concurrently (one LLM call per story in parallel)
    then deduplicates and persists to FAISS.

    For each story:
      1. Query FAISS for similar existing test cases (context for the LLM).
      2. Generate new test cases via LLM using story-scoped TC IDs:
           TC-US-NNN-POS-001  /  TC-US-NNN-NEG-001  /  TC-US-NNN-EDG-001
      3. Validate that all variations have unique step lists (no copy-paste).
      4. Deduplicate against already-known tc_ids.
      5. Store every new test case in FAISS for future runs.
    """
    llm    = config.get_groq_llm(temperature=0.2)
    memory = get_memory()

    # Build initial existing-ID set (may be non-empty on re-runs)
    existing_ids_init: set[str] = {tc["tc_id"] for tc in state.get("test_cases") or []}
    base_test_cases: list[dict] = list(state.get("test_cases") or [])

    stories = state["reviewed_stories"]

    print(f"  ⚡ Test Case Agent: generating for {len(stories)} stories in parallel …")

    def _generate_one(story: dict) -> list[dict]:
        """Worker: FAISS lookup + LLM call for a single story."""
        sid = story["story_id"]
        similar = memory.retrieve_similar_test_cases(
            query=f"{sid} {story.get('title', '')} {' '.join(story.get('acceptance_criteria', []))}",
            k=3,
        )
        if similar:
            logger.info(
                "Test Case Agent: %s — %d similar TC(s) found in memory", sid, len(similar)
            )
        return _generate_for_story(llm, story)

    all_cases_per_story: list[list[dict]] = run_parallel(
        _generate_one,
        stories,
        max_workers=4,
        label="test-case-story",
    )

    # Deduplicate and accumulate — use a lock because run_parallel already
    # completed sequentially here, but we keep the pattern consistent.
    _lock = threading.Lock()
    existing_ids: set[str] = set(existing_ids_init)
    all_test_cases: list[dict] = list(base_test_cases)

    for story, cases in zip(stories, all_cases_per_story):
        sid = story["story_id"]
        new_cases: list[dict] = []
        with _lock:
            for tc in cases:
                if tc["tc_id"] in existing_ids:
                    logger.debug("Test Case Agent: skipping duplicate %s", tc["tc_id"])
                    continue
                existing_ids.add(tc["tc_id"])
                new_cases.append(tc)
            all_test_cases.extend(new_cases)

        # Persist each new test case to FAISS
        for tc in new_cases:
            try:
                memory.store_test_case(tc)
            except Exception as exc:
                logger.warning("Test Case Agent: FAISS store_test_case failed — %s", exc)

        # ── Priority breakdown log ───────────────────────────────────────────
        by_priority = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for tc in new_cases:
            by_priority[tc.get("priority", "Low")] = (
                by_priority.get(tc.get("priority", "Low"), 0) + 1
            )
        logger.info(
            "Test Case Agent: %s → %d TCs (POS=%d NEG=%d EDG=%d) "
            "[Critical=%d High=%d Medium=%d Low=%d] (%d dupes skipped)",
            sid,
            len(new_cases),
            sum(1 for c in new_cases if c["type"] == "positive"),
            sum(1 for c in new_cases if c["type"] == "negative"),
            sum(1 for c in new_cases if c["type"] == "edge"),
            by_priority["Critical"], by_priority["High"],
            by_priority["Medium"], by_priority["Low"],
            len(cases) - len(new_cases),
        )
        print(
            f"  🧪 {sid} → {len(new_cases)} test cases  "
            f"[POS={sum(1 for c in new_cases if c['type']=='positive')} "
            f"NEG={sum(1 for c in new_cases if c['type']=='negative')} "
            f"EDG={sum(1 for c in new_cases if c['type']=='edge')}]"
        )

    # Persist memory to disk after all stories processed
    try:
        memory.save()
    except Exception as exc:
        logger.warning("Test Case Agent: FAISS save() failed — %s", exc)

    total = len(all_test_cases)
    stories_count = len(stories)
    print(
        f"✅ Test Case Agent: Generated {total} test cases "
        f"across {stories_count} stories"
    )
    logger.info(
        "✅ Test Case Agent: %d total test cases from %d stories",
        total, stories_count,
    )
    return {**state, "test_cases": all_test_cases}
