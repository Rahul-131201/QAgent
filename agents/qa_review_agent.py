"""
agents/qa_review_agent.py — QA Review Agent
============================================
Validates and enriches user stories produced by the Requirement Agent.
Uses Google Gemini to spot ambiguity, add edge-case acceptance criteria,
and score each story's clarity.

Flow:
    state.user_stories  →  ChatGoogleGenerativeAI (per-story)
                        →  state.reviewed_stories (list[dict])
                        →  state.feedback         (if any story needs review)
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

logger = logging.getLogger(__name__)

# ── Pydantic models ───────────────────────────────────────────────────────────

class ReviewedStory(BaseModel):
    # ── Original UserStory fields ────────────────────────────────────────────
    story_id: str = Field(..., pattern=r"^US-\d{3}$")
    title: str = Field(..., min_length=3)
    story: str = Field(..., min_length=10)
    acceptance_criteria: list[str] = Field(..., min_length=1)
    priority: Literal["High", "Medium", "Low"]

    # ── QA-enriched fields ───────────────────────────────────────────────────
    qa_notes: list[str] = Field(default_factory=list)
    needs_review: bool = False
    qa_confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("qa_confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a Senior QA Engineer reviewing user stories before test case generation.
Your job is to:
  1. Detect ambiguous language (e.g. "fast", "easy", "should work", "simple").
  2. Add missing acceptance criteria — especially edge cases, negative paths,
     and boundary conditions.
  3. Normalize the "story" field to strict "As a [role], I want [feature], so that [benefit]" format.
  4. Assign a qa_confidence score (0.0–1.0) reflecting story clarity and completeness.
  5. Set needs_review=true when qa_confidence < 0.7.
"""

_USER_PROMPT_TEMPLATE = """\
Review this user story and return an enriched version.

Return ONLY a single valid JSON object — no markdown fences, no explanation.
The object must match this schema exactly:
{{
  "story_id":            "<same as input>",
  "title":               "<normalized title>",
  "story":               "As a [role], I want [feature], so that [benefit]",
  "acceptance_criteria": ["<existing or improved criteria>", "..."],
  "priority":            "High" | "Medium" | "Low",
  "qa_notes":            ["<observation 1>", "..."],
  "needs_review":        true | false,
  "qa_confidence":       0.0–1.0
}}

User Story to review:
{story_json}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    return extract_json(text)


def _review_story(
    llm,
    story: dict,
    max_retries: int = 2,
) -> dict:
    """Send one story to Gemini, parse & validate the enriched result."""
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(
            content=_USER_PROMPT_TEMPLATE.format(
                story_json=json.dumps(story, indent=2)
            )
        ),
    ]

    last_error: Exception | None = None
    response = None

    for attempt in range(1, max_retries + 2):
        try:
            # 1.6: json_mode ensures the provider returns valid JSON
            response = llm.invoke(messages, json_mode=True)
            validated = ReviewedStory.model_validate(
                json.loads(_extract_json(response.content))
            )
            return validated.model_dump()

        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "QA Review Agent attempt %d/%d for %s — %s: %s",
                attempt, max_retries + 1,
                story.get("story_id", "?"),
                type(exc).__name__, exc,
            )
            if attempt <= max_retries and response is not None:
                messages.append(response)
                messages.append(
                    HumanMessage(
                        content=(
                            f"Your previous response caused a parse error: {exc}\n"
                            "Return ONLY a valid JSON object matching the schema above."
                        )
                    )
                )

    raise RuntimeError(
        f"QA Review Agent failed for story {story.get('story_id')} "
        f"after {max_retries + 1} attempts. Last error: {last_error}"
    )


# ── Agent node ────────────────────────────────────────────────────────────────

def qa_review_agent(state: QAgentState) -> QAgentState:
    """
    LangGraph node: user_stories → reviewed_stories.

    Runs all story reviews concurrently (one LLM call per story in parallel)
    which cuts latency from O(N stories) down to roughly O(1) wall-clock time.
    """
    llm = config.get_openrouter_llm(temperature=0.2)
    stories = state["user_stories"]

    print(f"  ⚡ QA Review Agent: reviewing {len(stories)} stories in parallel …")

    reviewed: list[dict] = run_parallel(
        lambda story: _review_story(llm, story),
        stories,
        max_workers=4,
        label="story-review",
    )

    new_feedback: list[str] = list(state.get("feedback", []))

    for enriched in reviewed:
        sid   = enriched["story_id"]
        score = enriched["qa_confidence"]
        logger.info(
            "QA Review — %s | confidence: %.2f | needs_review: %s",
            sid, score, enriched["needs_review"],
        )
        print(
            f"  📋 {sid} | qa_confidence: {score:.2f} | "
            f"needs_review: {enriched['needs_review']}"
        )
        if enriched["needs_review"]:
            note = (
                f"[QA Review] {sid} flagged for review "
                f"(confidence {score:.2f}): {'; '.join(enriched['qa_notes'])}"
            )
            new_feedback.append(note)
            logger.warning(note)

    flagged = sum(1 for s in reviewed if s["needs_review"])
    print(
        f"✅ QA Review Agent: Reviewed {len(reviewed)} stories — "
        f"{flagged} flagged for review"
    )
    logger.info(
        "✅ QA Review Agent: Reviewed %d stories, %d flagged",
        len(reviewed), flagged,
    )
    return {**state, "reviewed_stories": reviewed, "feedback": new_feedback}
