"""
agents/requirement_agent.py — Requirement Agent
================================================
Converts raw BRD text (Financial / Insurance domain) into complete,
professional user stories with Given-When-Then acceptance criteria,
Fibonacci estimation, and structured descriptions.

Upgraded to match the User Story Generator agent specification:
  - 7-field schema: story_id, title, story, acceptance_criteria (≥3, GWT),
    priority, estimation (Fibonacci), description
  - Domain-aware system prompt (Financial & Insurance)
  - Given-When-Then validator on each acceptance criterion
  - Self-healing retry logic on JSON / validation failures

Flow:
    state.brd  →  ChatGroq  →  JSON parse + Pydantic validation
                →  state.user_stories (list[dict])
"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

import config
from graph.state import QAgentState
from memory.faiss_store import get_memory

logger = logging.getLogger(__name__)

# ── Pydantic model ────────────────────────────────────────────────────────────

_FIBONACCI = {1, 2, 3, 5, 8, 13}
_GWT_PATTERN = re.compile(r"\bGiven\b", re.IGNORECASE)


class UserStory(BaseModel):
    story_id: str = Field(..., pattern=r"^US-\d{3}$")
    title: str = Field(
        ...,
        min_length=5,
        description="Brief, descriptive title (5–8 words)",
    )
    story: str = Field(
        ...,
        min_length=15,
        description="As a [role], I want [action] so that [benefit]",
    )
    acceptance_criteria: list[str] = Field(
        ...,
        min_length=3,
        description="At least 3 Given-When-Then criteria",
    )
    priority: Literal["High", "Medium", "Low"]
    estimation: int = Field(
        ...,
        description="Story points using Fibonacci scale: 1, 2, 3, 5, 8, or 13",
    )
    description: str = Field(
        ...,
        min_length=20,
        description="2–3 sentence business context and implementation considerations",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("estimation")
    @classmethod
    def must_be_fibonacci(cls, v: int) -> int:
        if v not in _FIBONACCI:
            raise ValueError(
                f"Estimation {v} is not a valid Fibonacci value. "
                f"Use one of: {sorted(_FIBONACCI)}"
            )
        return v

    @field_validator("acceptance_criteria")
    @classmethod
    def must_use_given_when_then(cls, criteria: list[str]) -> list[str]:
        non_gwt = [c for c in criteria if not _GWT_PATTERN.search(c)]
        if non_gwt:
            raise ValueError(
                f"{len(non_gwt)} acceptance criterion/criteria missing 'Given' keyword "
                f"(Given-When-Then format required): {non_gwt[:2]}"
            )
        return criteria

    @field_validator("story")
    @classmethod
    def must_follow_user_story_format(cls, v: str) -> str:
        lower = v.lower()
        if "as a" not in lower and "as an" not in lower:
            raise ValueError("Story must start with 'As a' or 'As an'")
        if "i want" not in lower:
            raise ValueError("Story must contain 'I want'")
        if "so that" not in lower:
            raise ValueError("Story must contain 'so that'")
        return v


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Professional User Story Generator specialized in Financial and Insurance \
domain requirements documentation.

Your role is to analyze Business Requirement Documents (BRDs) and generate complete, \
professional functional user stories that development teams can implement and QA teams \
can test.

Core rules:
1. Generate ONLY functional, user-facing user stories — no technical, infrastructure, \
   or non-functional stories unless explicitly requested.
2. One user story represents ONE complete feature or functional module.
3. Use exact role names found in the BRD (e.g. Policyholder, Loan Officer, Account Holder).
4. Every acceptance criterion MUST use Given-When-Then format and be specific and testable.
5. Estimation follows the Fibonacci scale: 1, 2, 3, 5, 8, or 13 story points only.
6. Priorities are: High (critical functionality), Medium (important), Low (nice-to-have).

Financial & Insurance domain context — common roles include:
  Account Holder, Customer, Banking Agent, Loan Officer, Compliance Officer,
  Policyholder, Insurance Agent, Claims Adjuster, Underwriter, Risk Analyst.

Common features include: account management, transaction processing, payment workflows, \
loan origination, credit assessment, policy issuance, premium calculation, claims \
processing, underwriting, policy renewal, coverage management.
"""

_USER_PROMPT_TEMPLATE = """\
Extract ALL functional user stories from the following Business Requirement Document.

Return ONLY a valid JSON array — no markdown fences, no explanation, no commentary.
Each element MUST match this exact schema:

{{
  "story_id":            "US-001",
  "title":               "<Brief descriptive title, 5–8 words>",
  "story":               "As a [role], I want [action] so that [benefit]",
  "acceptance_criteria": [
    "Given <context>, When <action>, Then <outcome>",
    "Given <context>, When <action>, Then <outcome>",
    "Given <context>, When <action>, Then <outcome>"
  ],
  "priority":    "High" | "Medium" | "Low",
  "estimation":  <integer: 1 | 2 | 3 | 5 | 8 | 13>,
  "description": "<2–3 sentences: what the feature does, why it matters, key business rules>"
}}

Strict constraints:
- "story" MUST contain "As a", "I want", and "so that"
- "acceptance_criteria" MUST have at least 3 items, each starting with "Given"
- "estimation" MUST be one of: 1, 2, 3, 5, 8, 13
- Cover ALL functional areas in the BRD
- Do NOT include security, performance, infrastructure, or non-functional stories

BRD:
\"\"\"
{brd}
\"\"\"
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """Strip any accidental markdown code fences around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        inner = lines[1:] if lines[-1].strip() == "```" else lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return text


def _parse_and_validate(raw: str) -> list[dict]:
    """Parse JSON and validate every element against UserStory."""
    data = json.loads(_extract_json(raw))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")
    stories: list[dict] = []
    for item in data:
        validated = UserStory.model_validate(item)
        stories.append(validated.model_dump())
    return stories


# ── Agent node ────────────────────────────────────────────────────────────────

def requirement_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: BRD → structured user stories (Financial / Insurance domain).

    1. Checks the FAISS BRD semantic cache — returns instantly on a near-hit
       (cosine ≥ 0.97) without any LLM call.
    2. Calls Groq with json_mode=True for reliable structured output.
    3. Validates each story against UserStory (7 fields, GWT criteria, Fibonacci
       estimation, As-a/I-want/so-that format).
    4. Retries up to 2 times on JSON / validation errors with error feedback.
    5. Persists the BRD → stories mapping to the cache for future runs.
    """
    memory = get_memory()
    cached = memory.retrieve_brd_cache(state["brd"])
    if cached is not None:
        print(
            f"✅ Requirement Agent: Cache HIT — "
            f"returning {len(cached)} cached user stories (zero LLM cost)"
        )
        logger.info("Requirement Agent: BRD cache HIT (%d stories)", len(cached))
        return {**state, "user_stories": cached}

    llm = config.get_groq_llm(temperature=0.2)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_USER_PROMPT_TEMPLATE.format(brd=state["brd"])),
    ]

    max_retries = 2
    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):          # attempts: 1, 2, 3
        try:
            response = llm.invoke(messages, json_mode=True)
            stories = _parse_and_validate(response.content)

            # ── Log quality summary ──────────────────────────────────────────
            high = sum(1 for s in stories if s.get("priority") == "High")
            med  = sum(1 for s in stories if s.get("priority") == "Medium")
            low  = sum(1 for s in stories if s.get("priority") == "Low")
            logger.info(
                "✅ Requirement Agent: Generated %d user stories "
                "(High=%d, Medium=%d, Low=%d)",
                len(stories), high, med, low,
            )
            print(
                f"✅ Requirement Agent: Generated {len(stories)} user stories "
                f"(High={high}, Medium={med}, Low={low})"
            )

            # ── Cache for future runs ────────────────────────────────────────
            try:
                memory.store_brd_run(state["brd"], stories)
                memory.save()
                logger.debug("Requirement Agent: BRD run cached.")
            except Exception as cache_exc:
                logger.warning("Requirement Agent: failed to cache BRD run: %s", cache_exc)

            return {**state, "user_stories": stories}

        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Requirement Agent attempt %d/%d failed — %s: %s",
                attempt, max_retries + 1, type(exc).__name__, exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"Your previous response caused a validation error: {exc}\n\n"
                            "Fix ALL issues and return ONLY a valid JSON array.\n"
                            "Reminder:\n"
                            "- Each 'story' must contain 'As a', 'I want', and 'so that'\n"
                            "- Each acceptance criterion must start with 'Given'\n"
                            "- 'estimation' must be one of: 1, 2, 3, 5, 8, 13\n"
                            "- Each story needs at least 3 acceptance_criteria"
                        )
                    )
                )

    raise RuntimeError(
        f"Requirement Agent failed after {max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
