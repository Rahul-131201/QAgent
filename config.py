"""
config.py — QAgent Central Configuration
=========================================
Loads environment variables from .env and exposes all settings
as module-level constants. Import from anywhere in the project:

    from config import GROQ_MODEL, GEMINI_MODEL, GROQ_API_KEY, GOOGLE_API_KEY
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, dotenv_values as _read_dotenv

logger = logging.getLogger(__name__)

# ── Locate and load .env ────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _PROJECT_ROOT / ".env"

# Read .env values into a plain dict so we can consult them directly
# (os.getenv can be polluted by stale system-level env vars)
_env_file_cfg: dict[str, str | None] = _read_dotenv(_ENV_FILE) if _ENV_FILE.exists() else {}

if not _ENV_FILE.exists():
    print(
        "[WARN] [QAgent Config] .env not found. "
        "Copy .env.example -> .env and fill in your API keys.",
        file=sys.stderr,
    )
else:
    load_dotenv(dotenv_path=_ENV_FILE, override=False)

# ── LLM Model Names ─────────────────────────────────────────────────────────
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
HF_MODEL: str = os.getenv("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── API Keys ────────────────────────────────────────────────────────────────
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
USE_GEMINI: bool = os.getenv("USE_GEMINI", "true").strip().lower() not in ("false", "0", "no")
HUGGINGFACE_API_KEY: str | None = os.getenv("HUGGINGFACE_API_KEY")
USE_HUGGINGFACE: bool = os.getenv("USE_HUGGINGFACE", "false").strip().lower() not in ("false", "0", "no")
OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
# GPT_API_KEY is the variable name used in .env; also accept standard OPENAI_API_KEY
OPENAI_API_KEY: str | None = os.getenv("GPT_API_KEY") or os.getenv("OPENAI_API_KEY")

# ── FAISS / Memory ──────────────────────────────────────────────────────────
FAISS_INDEX_DIR: Path = _PROJECT_ROOT / "memory" / "faiss_index"
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# ── Generated Test Scripts ───────────────────────────────────────────────────
GENERATED_TESTS_DIR: Path = _PROJECT_ROOT / "tests" / "generated"
GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)

HEALED_TESTS_DIR: Path = GENERATED_TESTS_DIR / "healed"
HEALED_TESTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Pipeline Settings ────────────────────────────────────────────────────────
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))   # feedback loop max
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))

# ── Per-provider quota flags (reset on process restart) ─────────────────────
_gemini_quota_exhausted: bool = False
_groq_quota_exhausted: bool = False
_hf_quota_exhausted: bool = False
_openrouter_quota_exhausted: bool = False

# ── Rate-limit error detection ────────────────────────────────────────────────

def _is_rate_limit(exc: Exception) -> bool:
    """Return True if the exception should trigger fallback to the next provider."""
    msg = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    return any(k in msg for k in (
        # Rate limit / quota
        "429", "rate_limit", "rate limit", "quota",
        "resource_exhausted", "too many requests",
        "tokens per day", "tpd",
        # Invalid / expired / missing API key — fall through to next provider
        "api_key_invalid", "api key invalid", "api key expired",
        "key expired", "invalid_argument", "invalid argument",
        "unauthenticated", "permission_denied", "forbidden",
        # Context / model not found / bad endpoint
        "context_length_exceeded", "404", "notfound", "not found",
        "cannot post", "cannot get", "service unavailable",
    )) or any(k in exc_type for k in (
        "notfound", "notfounderror",
        "authentication", "authenticationerror",
        "permission", "permissiondenied",
        "ratelimit", "ratelimiterror",
        "overloaderror",
    ))


# ── Per-provider LLM constructors ─────────────────────────────────────────────

def _make_groq(temperature: float = 0.2):
    from langchain_groq import ChatGroq
    return ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=temperature)


def _make_gemini(temperature: float = 0.2):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL, google_api_key=GOOGLE_API_KEY, temperature=temperature
    )


def _make_huggingface(temperature: float = 0.2):
    """HuggingFace Serverless Inference API via OpenAI-compatible endpoint."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        base_url="https://api-inference.huggingface.co/v1",
        api_key=HUGGINGFACE_API_KEY,
        model=HF_MODEL,
        temperature=temperature,
    )


def _make_openrouter(temperature: float = 0.2):
    """OpenRouter via OpenAI-compatible endpoint."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        model=OPENROUTER_MODEL,
        temperature=temperature,
    )


def _make_openai(temperature: float = 0.2):
    """OpenAI GPT-4o mini — primary provider for all agents."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL,
        temperature=temperature,
    )


# ── Unified fallback-chain LLM wrapper ────────────────────────────────────────

class _FallbackChainLLM:
    """
    Wraps a prioritised list of LLM providers.
    On a 429 / quota error the next provider in the chain is tried.
    On any other error the exception is re-raised immediately.
    """

    def __init__(self, providers: list[tuple[str, object]], temperature: float = 0.2):
        # providers: [(name, factory_fn), ...]
        self._providers = providers
        self._temperature = temperature
        self._cache: dict[str, object] = {}

    def _get(self, name: str, factory_fn):
        if name not in self._cache:
            self._cache[name] = factory_fn(self._temperature)
        return self._cache[name]

    def invoke(self, messages, **kwargs):
        # ── 1.6: json_mode → bind response_format on supported providers ──────
        json_mode: bool = kwargs.pop("json_mode", False)
        _JSON_PROVIDERS = {"GPT-4o-mini", "Groq", "OpenRouter"}

        # ── 1.2: check for a per-thread streaming callback ───────────────────
        try:
            from agents.stream_context import get_token_callback
            token_cb, agent_name = get_token_callback()
        except Exception:
            token_cb, agent_name = None, ""

        last_exc: Exception | None = None
        for name, factory_fn in self._providers:
            try:
                llm = self._get(name, factory_fn)

                # Apply json_mode: bind response_format for supported providers
                actual_llm = llm
                if json_mode and name in _JSON_PROVIDERS:
                    try:
                        actual_llm = llm.bind(
                            response_format={"type": "json_object"}
                        )
                    except Exception:
                        actual_llm = llm  # provider doesn't support bind

                if token_cb:
                    # ── Streaming path ────────────────────────────────────────
                    from langchain_core.messages import AIMessage
                    parts: list[str] = []
                    stream_failed = False
                    try:
                        for chunk in actual_llm.stream(messages, **kwargs):
                            t = getattr(chunk, "content", "") or ""
                            if t:
                                parts.append(t)
                                token_cb(agent_name, t)
                    except Exception as stream_exc:
                        if _is_rate_limit(stream_exc):
                            print(
                                f"[WARN] [{name}] rate-limit hit -> trying next provider. "
                                f"({type(stream_exc).__name__})"
                            )
                            last_exc = stream_exc
                            continue
                        # Streaming not supported by this provider → fallback to invoke
                        logger.debug(
                            "Streaming unavailable for [%s]: %s — falling back to invoke",
                            name, stream_exc,
                        )
                        stream_failed = True

                    if stream_failed:
                        result = actual_llm.invoke(messages, **kwargs)
                        return result
                    # Return a real AIMessage so agents can safely append it to messages
                    return AIMessage(content="".join(parts))

                # ── Normal (non-streaming) path ───────────────────────────────
                result = actual_llm.invoke(messages, **kwargs)
                return result

            except Exception as exc:
                if _is_rate_limit(exc):
                    print(f"[WARN] [{name}] rate-limit hit -> trying next provider. ({type(exc).__name__})")
                    last_exc = exc
                    continue
                raise
        raise RuntimeError(
            f"All LLM providers exhausted (chain: {[n for n, _ in self._providers]}). "
            f"Last error: {last_exc}"
        )

    def __getattr__(self, name: str):
        """Proxy attribute access to the first available provider."""
        for pname, factory_fn in self._providers:
            try:
                return getattr(self._get(pname, factory_fn), name)
            except Exception:
                continue
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


# ── LLM Factories ─────────────────────────────────────────────────────────────

def _build_fallback_chain(temperature: float) -> "_FallbackChainLLM":
    """
    Unified fallback chain used by all agents.
    Priority: Groq → Gemini (if USE_GEMINI) → OpenRouter → GPT-4o-mini → HuggingFace.
    All get_*_llm() factory functions delegate here so that:
      1. Provider priority is controlled from a single place.
      2. Tests can mock a single target (config.get_groq_llm, etc.).
    """
    providers: list[tuple[str, object]] = []
    if GROQ_API_KEY:
        providers.append(("Groq", _make_groq))
    if GOOGLE_API_KEY and USE_GEMINI:
        providers.append(("Gemini", _make_gemini))
    if OPENROUTER_API_KEY:
        providers.append(("OpenRouter", _make_openrouter))
    if OPENAI_API_KEY:
        providers.append(("GPT-4o-mini", _make_openai))
    if HUGGINGFACE_API_KEY and USE_HUGGINGFACE:
        providers.append(("HuggingFace", _make_huggingface))
    if not providers:
        raise RuntimeError(
            "No LLM API keys configured. "
            "Set at least one of: GROQ_API_KEY, GOOGLE_API_KEY, "
            "OPENROUTER_API_KEY, GPT_API_KEY in .env."
        )
    return _FallbackChainLLM(providers, temperature)


# Keep _gemini_first_chain as an alias for backward compatibility
_gemini_first_chain = _build_fallback_chain


def get_groq_llm(temperature: float = 0.2) -> "_FallbackChainLLM":
    """Return the prioritised LLM fallback chain (Groq-first)."""
    return _build_fallback_chain(temperature)


def get_gemini_llm(temperature: float = 0.2) -> "_FallbackChainLLM":
    """Return the prioritised LLM fallback chain."""
    return _build_fallback_chain(temperature)


def get_openrouter_llm(temperature: float = 0.2) -> "_FallbackChainLLM":
    """Return the prioritised LLM fallback chain."""
    return _build_fallback_chain(temperature)


def get_huggingface_llm(temperature: float = 0.2) -> "_FallbackChainLLM":
    """Return the prioritised LLM fallback chain."""
    return _build_fallback_chain(temperature)


def get_openai_llm(temperature: float = 0.2) -> "_FallbackChainLLM":
    """Return the prioritised LLM fallback chain."""
    return _build_fallback_chain(temperature)


# ── Startup diagnostics (suppressed when QAGENT_QUIET is set) ─────────────────

_QUIET: bool = bool(os.getenv("QAGENT_QUIET", ""))

_missing_keys: list[str] = []
if not GOOGLE_API_KEY and not GROQ_API_KEY and not OPENROUTER_API_KEY and not OPENAI_API_KEY:
    _missing_keys.append("GROQ_API_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY / GPT_API_KEY")

if _missing_keys and not _QUIET:
    print(
        f"[WARN] [QAgent Config] Missing required API keys in .env: {', '.join(_missing_keys)}.",
        file=sys.stderr,
    )

_active_providers: list[str] = []
if GROQ_API_KEY:
    _active_providers.append("Groq (primary)")
if GOOGLE_API_KEY and USE_GEMINI:
    _active_providers.append("Gemini (fallback)")
if OPENROUTER_API_KEY:
    _active_providers.append("OpenRouter (fallback)")
if OPENAI_API_KEY:
    _active_providers.append("GPT-4o-mini (fallback)")
if HUGGINGFACE_API_KEY and USE_HUGGINGFACE:
    _active_providers.append("HuggingFace (fallback)")

if not _QUIET:
    print(
        "[OK] [QAgent Config] Loaded successfully.\n"
        f"   Primary model     : {GROQ_MODEL}\n"
        f"   OpenRouter model  : {OPENROUTER_MODEL}\n"
        f"   Active providers  : {', '.join(_active_providers) or 'NONE — set API keys!'}\n"
        f"   FAISS index       : {FAISS_INDEX_DIR}\n"
        f"   Max iterations    : {MAX_ITERATIONS}"
    )
