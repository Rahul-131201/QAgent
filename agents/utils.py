"""
agents/utils.py — Shared utilities for all QAgent agents
=========================================================
Centralises repeated helpers that were previously copy-pasted into every
agent file.  Import from here instead of duplicating:

    from agents.utils import extract_json, run_parallel, retry_llm_call
"""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ── JSON extraction ───────────────────────────────────────────────────────────

def extract_json(text: str) -> str:
    """
    Strip markdown code fences and return the raw JSON string.

    Handles:
      - ```json ... ``` or ``` ... ``` wrappers
      - Leading/trailing whitespace
      - Nested triple-backtick inside a string (takes outermost fence only)
    """
    text = text.strip()

    # Fast path: no fences
    if not text.startswith("```"):
        return text

    # Match the outermost fence pair
    fence_re = re.compile(r"^```(?:\w+)?\s*\n(.*?)\n```\s*$", re.DOTALL)
    match = fence_re.match(text)
    if match:
        return match.group(1).strip()

    # Fallback: drop first line (opening fence) and last line (closing fence)
    lines = text.splitlines()
    inner = lines[1:]
    if inner and inner[-1].strip() == "```":
        inner = inner[:-1]
    return "\n".join(inner).strip()


# ── Retry wrapper for LLM calls ───────────────────────────────────────────────

def retry_llm_call(
    fn: Callable[[], T],
    *,
    max_retries: int = 2,
    retry_exceptions: tuple = (json.JSONDecodeError, ValueError),
    on_retry: Callable[[int, Exception], Any] | None = None,
) -> T:
    """
    Call *fn* up to (max_retries + 1) times, retrying on *retry_exceptions*.
    Any other exception type is re-raised immediately.

    Args:
        fn:               Zero-arg callable (a lambda that captures context).
        max_retries:      Maximum number of retries (total attempts = max_retries + 1).
        retry_exceptions: Tuple of exception types that trigger a retry.
        on_retry:         Optional callback(attempt_number, exc) called before each retry.

    Returns:
        Return value of *fn* on success.

    Raises:
        RuntimeError if all attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 2):
        try:
            return fn()
        except retry_exceptions as exc:
            last_exc = exc
            if attempt <= max_retries:
                if on_retry:
                    on_retry(attempt, exc)
            else:
                raise RuntimeError(
                    f"All {max_retries + 1} attempts failed. Last error: {exc}"
                ) from exc
        except Exception:
            raise   # Non-retryable — propagate immediately
    raise RuntimeError(f"retry_llm_call: unreachable. last_exc={last_exc}")


# ── Parallel story processor ──────────────────────────────────────────────────

def run_parallel(
    fn: Callable[[Any], T],
    items: list[Any],
    *,
    max_workers: int = 4,
    label: str = "item",
) -> list[T]:
    """
    Run *fn(item)* for every item in *items* using a ThreadPoolExecutor,
    preserving original order.

    LLM SDKs (langchain-groq, langchain-openai) are thread-safe at the
    call level, making this safe for concurrent LLM requests.

    Args:
        fn:          Function to call with each item.
        items:       List of inputs.
        max_workers: Thread pool size (capped at len(items)).
        label:       Human-readable name for log messages.

    Returns:
        List of results in the same order as *items*.
    """
    if not items:
        return []

    workers = min(max_workers, len(items))

    # Serial fast-path for single items
    if workers == 1:
        return [fn(item) for item in items]

    results: list[T | None] = [None] * len(items)
    errors: list[tuple[int, Exception]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {pool.submit(fn, item): idx for idx, item in enumerate(items)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
                logger.debug("run_parallel: %s[%d] completed", label, idx)
            except Exception as exc:
                logger.error("run_parallel: %s[%d] failed — %s", label, idx, exc)
                errors.append((idx, exc))

    if errors:
        first_idx, first_exc = errors[0]
        raise RuntimeError(
            f"run_parallel: {len(errors)} {label}(s) failed. "
            f"First failure at index {first_idx}: {type(first_exc).__name__}: {first_exc}"
        ) from first_exc

    return results  # type: ignore[return-value]


# ── Exponential back-off sleep ────────────────────────────────────────────────

def backoff_sleep(attempt: int, base: float = 1.0, cap: float = 30.0) -> None:
    """Sleep for min(base * 2^attempt, cap) seconds."""
    wait = min(base * (2 ** attempt), cap)
    logger.debug("backoff_sleep: sleeping %.1fs (attempt %d)", wait, attempt)
    time.sleep(wait)
