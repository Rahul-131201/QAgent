"""
agents/coverage_agent.py -- Coverage Agent
===========================================
Analyses the full multi-level test coverage hierarchy and surfaces gaps:

  Level 1 -- User Stories -> Test Cases   (ACs not covered by TCs)
  Level 2 -- Test Cases   -> Test Scripts (TCs with no automated script)
  Level 3 -- Cross-cutting gaps: boundary, security, negative, integration,
             performance, accessibility discovered by LLM reasoning

Upgraded to match the test-coverage-analyzer agent specification:
  - Expanded gap_type: uncovered_story, uncovered_scenario, missing_script
    plus boundary, security, negative, integration, performance, accessibility
  - DerivedTestCase uses TC-US-NNN-{POS|NEG|EDG}-NNN ID and
    Critical/High/Medium/Low priority (aligned with test_case_agent)
  - Coverage metrics (stories/TCs/scripts) printed at end of node
  - Script-level gap detection from state.test_scripts

Flow:
    state.reviewed_stories + state.test_cases + state.test_scripts
        ->  LLM via OpenRouter (per story, concurrent)
        ->  state.coverage_gaps  (list[str] -- human-readable with metrics)
        ->  state.test_cases     (extended with gap-derived test cases)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

import config
from agents.utils import extract_json, run_parallel
from graph.state import QAgentState

_TC_ID_PATTERN = re.compile(r"^TC-US-\d{3,}-(?:POS|NEG|EDG)-\d{3}$")
_STEP_NUMBER_PATTERN = re.compile(r"^Step\s+\d+\s*:", re.IGNORECASE)

logger = logging.getLogger(__name__)

# ── Pydantic models ───────────────────────────────────────────────────────────

class CoverageGap(BaseModel):
    gap_id: str = Field(..., pattern=r"^GAP-\d{3,}$")
    story_id: str = Field(..., pattern=r"^US-\d{3,}$")
    gap_type: Literal[
        # Cross-cutting quality gaps (LLM-detected)
        "boundary", "security", "negative", "integration",
        "performance", "accessibility",
        # Hierarchy coverage gaps
        "uncovered_story",    # story has no test cases at all
        "uncovered_scenario", # scenario not linked to any test case
        "missing_script",     # test case has no automated script
    ]
    description: str = Field(..., min_length=10)
    recommendation: str = Field(..., min_length=10)
    severity: Literal["Critical", "High", "Medium", "Low"]


class DerivedTestCase(BaseModel):
    """
    Test case derived from a coverage gap.
    Uses the same ID format and priority scale as test_case_agent:
      ID:       TC-US-NNN-{POS|NEG|EDG}-NNN
      Priority: Critical | High | Medium | Low
    """
    tc_id: str = Field(
        ...,
        description="Format: TC-US-NNN-{POS|NEG|EDG}-NNN  e.g. TC-US-123-NEG-001",
    )
    story_id: str = Field(..., pattern=r"^US-\d{3,}$")
    title: str = Field(..., min_length=5)
    type: Literal["positive", "negative", "edge"]
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(..., min_length=2)
    expected_result: str = Field(..., min_length=10)
    priority: Literal["Critical", "High", "Medium", "Low"]
    test_url: str = Field(default="*URL_of_the_application*")

    @field_validator("tc_id")
    @classmethod
    def tc_id_format(cls, v: str) -> str:
        if not _TC_ID_PATTERN.match(v):
            raise ValueError(
                f"tc_id '{v}' must match TC-US-NNN-{{POS|NEG|EDG}}-NNN "
                "(e.g. TC-US-123-NEG-001)"
            )
        return v

    @field_validator("steps")
    @classmethod
    def steps_must_be_numbered(cls, steps: list[str]) -> list[str]:
        bad = [s for s in steps if not _STEP_NUMBER_PATTERN.match(s.strip())]
        if bad:
            raise ValueError(
                f"{len(bad)} step(s) missing 'Step N:' prefix. "
                "Each step must start with 'Step 1:', 'Step 2:', etc."
            )
        return steps


# ── Prompts ───────────────────────────────────────────────────────────────────

_MAX_GAPS_PER_STORY = 5   # hard cap — keeps token usage within Groq free-tier TPD

_SYSTEM_PROMPT = """\
You are a Senior QA Architect specialising in multi-level test coverage analysis.

Your job is to analyse the complete coverage hierarchy:
  Level 1 — User Stories  → Test Cases  (are all ACs covered?)
  Level 2 — Test Cases    → Test Scripts (does each TC have automation?)
  Level 3 — Cross-cutting gaps (boundary, security, negative, integration,
             performance, accessibility) not yet tested

For each user story, identify the MOST IMPORTANT coverage gaps (maximum 5).

Gap types you may report:
  boundary        — min/max values, overflow, empty input, length limits
  security        — SQL injection, XSS, auth bypass, privilege escalation
  negative        — invalid input paths not covered by existing TCs
  integration     — third-party failures, network errors, partial data
  performance     — load limits, timeout behaviour, concurrent requests
  accessibility   — keyboard navigation, screen-reader labels, WCAG rules
  uncovered_story    — story has zero test cases at all
  uncovered_scenario — acceptance criterion not linked to any test case
  missing_script     — test case exists but has no automated script

Prioritisation:
  - uncovered_story / uncovered_scenario → Critical severity
  - missing_script → High severity
  - boundary / security → High severity
  - integration / performance → Medium severity
  - accessibility → Medium severity

CRITICAL OUTPUT RULES:
  - Return at most 5 gaps and exactly one derived_test_case per gap
  - derived_test_cases array length MUST equal gaps array length
  - If gaps is empty, derived_test_cases must also be []
  - DerivedTestCase tc_id MUST be TC-US-NNN-{POS|NEG|EDG}-NNN format
  - Every step must start with 'Step N:'
  - priority must be: Critical, High, Medium, or Low
"""

_USER_PROMPT_TEMPLATE = """\
Analyse the following user story across the full coverage hierarchy.
Identify the most important coverage gaps (maximum 5, Critical/High-severity first)
and provide exactly one derived test case per gap.

Return ONLY a valid JSON object — no markdown fences, no explanation.
Schema:
{{
  "gaps": [
    {{
      "gap_id":         "GAP-001",
      "story_id":       "<same as story story_id>",
      "gap_type":       "boundary" | "security" | "negative" | "integration" |
                         "performance" | "accessibility" |
                         "uncovered_story" | "uncovered_scenario" | "missing_script",
      "description":    "<specific description of what is missing>",
      "recommendation": "<concrete test action to close the gap>",
      "severity":       "Critical" | "High" | "Medium" | "Low"
    }}
  ],
  "derived_test_cases": [
    {{
      "tc_id":           "TC-US-{story_num}-NEG-{tc_seq}",
      "story_id":        "{story_id}",
      "title":           "<short descriptive title>",
      "type":            "positive" | "negative" | "edge",
      "preconditions":   ["<prerequisite>"],
      "steps":           ["Step 1: <action>", "Step 2: <action>", "Step 3: <verify>"],
      "expected_result": "<specific measurable outcome>",
      "priority":        "Critical" | "High" | "Medium" | "Low",
      "test_url":        "*URL_of_the_application*"
    }}
  ]
}}

STRICT rules:
  - Return at most 5 gaps and at most 5 derived_test_cases
  - derived_test_cases array length MUST equal gaps array length
  - If no gaps found, return {{"gaps": [], "derived_test_cases": []}}
  - tc_id MUST be TC-US-{story_num}-{{POS|NEG|EDG}}-NNN (3-digit suffix)
  - Every step MUST start with 'Step N:'
  - Check test_scripts_paths: any TC not represented in that list is a missing_script gap

gap_id starting counter  : {gap_counter}
tc_id  story num         : {story_num}

User Story:
{story_json}

Existing Test Cases for this story:
{test_cases_json}

Automated Script Paths (empty = no scripts at all):
{scripts_json}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    return extract_json(text)


def _parse_response(raw: str) -> tuple[list[dict], list[dict]]:
    """Parse and validate the LLM response; return (gaps, derived_test_cases)."""
    data = json.loads(_extract_json(raw))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

    validated_gaps: list[dict] = [
        CoverageGap.model_validate(g).model_dump() for g in data.get("gaps", [])
    ][:_MAX_GAPS_PER_STORY]
    validated_tcs: list[dict] = [
        DerivedTestCase.model_validate(tc).model_dump()
        for tc in data.get("derived_test_cases", [])
    ][:_MAX_GAPS_PER_STORY]

    # 1.7: Guarantee one TC per gap — trigger retry if the LLM skipped any
    if validated_gaps and len(validated_tcs) < len(validated_gaps):
        raise ValueError(
            f"Requires exactly one derived_test_case per gap: "
            f"got {len(validated_tcs)} TCs for {len(validated_gaps)} gap(s). "
            "Add the missing test cases."
        )

    return validated_gaps, validated_tcs


def _story_num(story_id: str) -> str:
    """Extract numeric portion from 'US-123' → '123'."""
    return story_id.split("-")[-1]


def _analyse_story(
    llm,
    story: dict,
    existing_tcs: list[dict],
    script_paths: list[str],
    gap_counter: int,
    max_retries: int = 2,
) -> tuple[list[dict], list[dict]]:
    """Run the LLM for one story; return (gaps, new_test_cases) with retry."""
    sid = story.get("story_id", "US-000")
    snum = _story_num(sid)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_USER_PROMPT_TEMPLATE.format(
                story_json=json.dumps(story, indent=2),
                test_cases_json=json.dumps(existing_tcs, indent=2),
                scripts_json=json.dumps(script_paths, indent=2),
                gap_counter=f"GAP-{gap_counter:03d}",
                story_id=sid,
                story_num=snum,
                tc_seq="001",
            )
        ),
    ]

    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):
        try:
            response = llm.invoke(messages, json_mode=True)
            return _parse_response(response.content)

        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Coverage Agent attempt %d/%d for %s — %s: %s",
                attempt, max_retries + 1, sid, type(exc).__name__, exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"Your previous response caused a validation error: {exc}\n\n"
                            "Fix ALL issues and return ONLY a valid JSON object.\n"
                            "Reminder of STRICT rules:\n"
                            f"- tc_id MUST be TC-US-{snum}-{{POS|NEG|EDG}}-NNN\n"
                            "- Every step must start with 'Step N:'\n"
                            "- priority must be: Critical, High, Medium, or Low\n"
                            "- severity must be: Critical, High, Medium, or Low\n"
                            "- derived_test_cases length MUST equal gaps length"
                        )
                    )
                )

    raise RuntimeError(
        f"Coverage Agent failed for story {sid} "
        f"after {max_retries + 1} attempts. Last error: {last_error}"
    )


# ── Agent node ────────────────────────────────────────────────────────────────

def coverage_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: (reviewed_stories + test_cases + test_scripts)
        -> (coverage_gaps, test_cases).

    Analyses all stories concurrently across three coverage levels:
      1. Story/AC coverage  -- acceptance criteria vs existing test cases
      2. Script coverage    -- existing test cases vs automated script paths
      3. Cross-cutting gaps -- boundary, security, negative, integration, etc.
    """
    llm = config.get_openrouter_llm(temperature=0.1)
    stories = state["reviewed_stories"]

    # Index existing TCs by story_id
    existing_tcs_by_story: dict[str, list[dict]] = {}
    for tc in state["test_cases"]:
        existing_tcs_by_story.setdefault(tc["story_id"], []).append(tc)

    # Collect automated script paths from state (may be empty)
    script_paths: list[str] = state.get("test_scripts", []) or []

    # Pre-assign deterministic gap counter offsets per story
    base_gap = 1
    story_args: list[tuple[dict, list[dict], list[str], int]] = []
    for story in stories:
        sid = story["story_id"]
        story_tcs = existing_tcs_by_story.get(sid, [])
        story_args.append((story, story_tcs, script_paths, base_gap))
        base_gap += _MAX_GAPS_PER_STORY

    print(f"  Coverage Agent: analysing {len(stories)} stories in parallel ...")

    def _analyse_one(args: tuple) -> tuple[list[dict], list[dict]]:
        story, story_tcs, scripts, gap_ctr = args
        return _analyse_story(llm, story, story_tcs, scripts, gap_ctr)

    results: list[tuple[list[dict], list[dict]]] = run_parallel(
        _analyse_one,
        story_args,
        max_workers=4,
        label="coverage-story",
    )

    all_gaps:       list[dict] = []
    new_test_cases: list[dict] = []

    for (story, _, _, _), (gaps, derived) in zip(story_args, results):
        all_gaps.extend(gaps)
        new_test_cases.extend(derived)
        logger.info(
            "Coverage Agent: %s -- %d gap(s), %d new TC(s)",
            story["story_id"], len(gaps), len(derived),
        )
        sev_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for g in gaps:
            sev_counts[g["severity"]] = sev_counts.get(g["severity"], 0) + 1
        print(
            f"  {story['story_id']} -> {len(gaps)} gap(s) "
            f"[C:{sev_counts['Critical']} H:{sev_counts['High']} "
            f"M:{sev_counts['Medium']} L:{sev_counts['Low']}], "
            f"{len(derived)} new TC(s)"
        )

    # Coverage metrics summary
    total_stories   = len(stories)
    covered_stories = sum(
        1 for s in stories
        if existing_tcs_by_story.get(s["story_id"])
    )
    total_tcs    = len(state["test_cases"])
    scripted_tcs = len(script_paths)

    print(
        f"\n  Coverage Metrics:"
        f"\n     Stories with TCs      : {covered_stories}/{total_stories}"
        f"\n     TCs with scripts      : {scripted_tcs}/{total_tcs}"
        f"\n     Gaps found (all types): {len(all_gaps)}"
    )

    # Build human-readable gap_descriptions (include gap_type for hierarchy visibility)
    gap_descriptions: list[str] = [
        f"[{g['gap_id']}][{g['severity']}][{g['gap_type']}] "
        f"{g['story_id']}: {g['description']}"
        for g in all_gaps
    ]
    updated_test_cases = state["test_cases"] + new_test_cases

    # Summary severity breakdown
    total_sev = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for g in all_gaps:
        total_sev[g["severity"]] = total_sev.get(g["severity"], 0) + 1

    print(
        f"Coverage Agent: Found {len(all_gaps)} gap(s) "
        f"[Critical:{total_sev['Critical']} High:{total_sev['High']} "
        f"Medium:{total_sev['Medium']} Low:{total_sev['Low']}], "
        f"added {len(new_test_cases)} new test case(s) "
        f"(total: {len(updated_test_cases)})"
    )
    logger.info(
        "Coverage Agent: %d gaps (C:%d H:%d M:%d L:%d), %d new TCs, %d total TCs",
        len(all_gaps),
        total_sev["Critical"], total_sev["High"],
        total_sev["Medium"],   total_sev["Low"],
        len(new_test_cases), len(updated_test_cases),
    )
    return {
        **state,
        "coverage_gaps": gap_descriptions,
        "test_cases": updated_test_cases,
    }