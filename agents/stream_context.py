"""
agents/stream_context.py — Thread-local LLM streaming callback
==============================================================
Provides a per-thread callback that receives individual LLM token strings
as they are streamed.  The API layer sets this callback before running
each agent step; the LLM wrapper in config.py consults it during invoke.

Usage (API layer):
    from agents.stream_context import set_token_callback, clear_token_callback
    set_token_callback(my_callback, agent_name="requirement_agent")
    try:
        result = agent_fn(state)
    finally:
        clear_token_callback()

Usage (config._FallbackChainLLM):
    from agents.stream_context import get_token_callback
    cb, agent_name = get_token_callback()
    if cb:
        for chunk in llm.stream(messages):
            cb(agent_name, chunk.content or "")
"""

from __future__ import annotations

import threading
from typing import Callable

_local = threading.local()


def set_token_callback(
    fn: Callable[[str, str], None] | None,
    agent_name: str = "",
) -> None:
    """Register *fn* as the streaming callback for the current thread.

    Args:
        fn:         Called as fn(agent_name, token) for each streamed token.
                    Pass None to disable streaming for this thread.
        agent_name: Label attached to every emitted token (e.g. "requirement_agent").
    """
    _local.callback = fn
    _local.agent_name = agent_name


def set_agent_name(name: str) -> None:
    """Update the agent label without changing the callback."""
    _local.agent_name = name


def get_token_callback() -> tuple[Callable[[str, str], None] | None, str]:
    """Return (callback, agent_name) for the current thread.

    Returns (None, "") when no callback is registered.
    """
    return getattr(_local, "callback", None), getattr(_local, "agent_name", "")


def clear_token_callback() -> None:
    """Remove the streaming callback for the current thread."""
    _local.callback = None
    _local.agent_name = ""
