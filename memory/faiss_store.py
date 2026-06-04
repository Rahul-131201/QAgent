"""
memory/faiss_store.py — QAgent FAISS Vector Memory
====================================================
Stores and retrieves past test cases, failures, and fixes using FAISS
with local HuggingFace embeddings (all-MiniLM-L6-v2 — no API key needed).

Three logical namespaces are maintained as separate FAISS indexes:
  • test_cases  — indexed test case dicts
  • failures    — indexed failure records
  • fixes       — indexed healing/fix records

Usage:
    from memory.faiss_store import QAgentMemory
    mem = QAgentMemory()          # auto-loads persisted index if present
    mem.store_failure({...})
    similar = mem.retrieve_similar_failures("ElementNotFound on #submit", k=3)
    mem.save()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:  # pragma: no cover — older installs without langchain-huggingface
    from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore[no-redef]
from langchain_core.documents import Document

import config

logger = logging.getLogger(__name__)

# ── Embedding model (local, free) ─────────────────────────────────────────────
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# ── Namespace sub-directories ─────────────────────────────────────────────────
NS_TEST_CASES = "test_cases"
NS_FAILURES   = "failures"
NS_FIXES      = "fixes"
NS_BRD_CACHE  = "brd_cache"   # BRD text → cached user_stories

# L2 distance threshold for cosine ≥ 0.97 with normalised embeddings:
# cosine = 1 − d²/2  ⟹  d < sqrt(2*(1−0.97)) ≈ 0.245
_BRD_CACHE_L2_THRESHOLD: float = 0.245

_NS_TEST_CASES = NS_TEST_CASES   # keep old private aliases for backward compat
_NS_FAILURES   = NS_FAILURES
_NS_FIXES      = NS_FIXES


def _make_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=_EMBED_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


class QAgentMemory:
    """FAISS-backed long-term memory for the QAgent pipeline."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else config.FAISS_INDEX_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._embeddings = _make_embeddings()

        # Each namespace has its own FAISS index (or None until first write)
        self._indexes: dict[str, FAISS | None] = {
            _NS_TEST_CASES: None,
            _NS_FAILURES:   None,
            _NS_FIXES:      None,
            NS_BRD_CACHE:   None,
        }

        self._load_all()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ns_path(self, namespace: str) -> Path:
        return self._base_dir / namespace

    def _load_namespace(self, namespace: str) -> None:
        ns_path = self._ns_path(namespace)
        if ns_path.exists():
            try:
                self._indexes[namespace] = FAISS.load_local(
                    str(ns_path),
                    self._embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.debug("QAgentMemory: loaded namespace '%s'", namespace)
            except Exception as exc:
                logger.warning(
                    "QAgentMemory: could not load namespace '%s': %s — starting fresh.",
                    namespace, exc,
                )

    def _load_all(self) -> None:
        for ns in self._indexes:
            self._load_namespace(ns)

    def _upsert(self, namespace: str, text: str, metadata: dict) -> None:
        """Add a document to a namespace index; create index on first insert."""
        doc = Document(page_content=text, metadata=metadata)
        if self._indexes[namespace] is None:
            self._indexes[namespace] = FAISS.from_documents(
                [doc], self._embeddings
            )
        else:
            self._indexes[namespace].add_documents([doc])

    def _retrieve(self, namespace: str, query: str, k: int) -> list[dict]:
        """Return up to k metadata dicts most similar to query; [] on miss."""
        index = self._indexes[namespace]
        if index is None:
            return []
        try:
            results = index.similarity_search(query, k=k)
            return [doc.metadata for doc in results]
        except Exception as exc:
            logger.warning(
                "QAgentMemory: retrieval failed in namespace '%s': %s",
                namespace, exc,
            )
            return []

    @staticmethod
    def _dict_to_text(data: dict) -> str:
        """Flatten a dict to a searchable string for embedding."""
        return " | ".join(f"{k}: {v}" for k, v in data.items() if v)

    # ── Public store methods ──────────────────────────────────────────────────

    def store_test_case(self, tc: dict) -> None:
        """Embed and store a test case dict."""
        text = self._dict_to_text(tc)
        self._upsert(_NS_TEST_CASES, text, metadata=tc)
        logger.debug("QAgentMemory: stored test case %s", tc.get("tc_id", "?"))

    def store_failure(self, failure: dict) -> None:
        """Embed and store a failure record dict.

        Expected keys: tc_id, script, error, output (any subset is fine).
        """
        text = self._dict_to_text(failure)
        self._upsert(_NS_FAILURES, text, metadata=failure)
        logger.debug("QAgentMemory: stored failure %s", failure.get("tc_id", "?"))

    def store_fix(self, fix: dict) -> None:
        """Embed and store a healing/fix record dict.

        Expected keys: tc_id, original_error, healed_script, strategy (any subset).
        """
        text = self._dict_to_text(fix)
        self._upsert(_NS_FIXES, text, metadata=fix)
        logger.debug("QAgentMemory: stored fix %s", fix.get("tc_id", "?"))

    # ── Public retrieve methods ───────────────────────────────────────────────

    def retrieve_similar_failures(
        self, error_msg: str, k: int = 3
    ) -> list[dict]:
        """Return up to k past failure records similar to error_msg."""
        results = self._retrieve(_NS_FAILURES, error_msg, k)
        logger.debug(
            "QAgentMemory: retrieved %d similar failure(s) for query: %.80s",
            len(results), error_msg,
        )
        return results

    def retrieve_similar_fixes(
        self, error_msg: str, k: int = 3
    ) -> list[dict]:
        """Return up to k past fix records relevant to error_msg."""
        results = self._retrieve(_NS_FIXES, error_msg, k)
        logger.debug(
            "QAgentMemory: retrieved %d similar fix(es) for query: %.80s",
            len(results), error_msg,
        )
        return results

    def retrieve_similar_test_cases(
        self, query: str, k: int = 3
    ) -> list[dict]:
        """Return up to k past test cases semantically similar to query."""
        return self._retrieve(_NS_TEST_CASES, query, k)
    # ── BRD semantic cache ───────────────────────────────────────────────────────────

    def store_brd_run(
        self, brd_text: str, user_stories: list[dict]
    ) -> None:
        """Embed the full BRD text and cache the resulting user_stories."""
        metadata = {"user_stories_json": json.dumps(user_stories, ensure_ascii=False)}
        self._upsert(NS_BRD_CACHE, brd_text, metadata)
        logger.debug("QAgentMemory: cached BRD run (%.60s…)", brd_text)

    def retrieve_brd_cache(
        self,
        brd_text: str,
        threshold: float = _BRD_CACHE_L2_THRESHOLD,
    ) -> list[dict] | None:
        """Return cached user_stories when a near-identical BRD was seen before.

        Uses cosine similarity ≥ 0.97 (L2 distance < *threshold* with
        normalised embeddings).  Returns None on cache miss.
        """
        index = self._indexes.get(NS_BRD_CACHE)
        if index is None:
            return None
        try:
            results = index.similarity_search_with_score(brd_text, k=1)
        except Exception as exc:
            logger.warning("QAgentMemory: BRD cache search failed: %s", exc)
            return None
        if not results:
            return None
        doc, score = results[0]
        if score <= threshold:
            cosine = round(1.0 - score ** 2 / 2.0, 4)
            logger.info(
                "QAgentMemory: BRD cache HIT (cosine≈%.4f, L2=%.4f) %.60s…",
                cosine, score, brd_text,
            )
            try:
                return json.loads(doc.metadata.get("user_stories_json", "[]"))
            except json.JSONDecodeError:
                return None
        return None
    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path | None = None) -> None:
        """Persist all namespace indexes to disk."""
        base = Path(path) if path else self._base_dir
        base.mkdir(parents=True, exist_ok=True)
        for ns, index in self._indexes.items():
            if index is not None:
                ns_path = base / ns
                index.save_local(str(ns_path))
                logger.info("QAgentMemory: saved namespace '%s' → %s", ns, ns_path)

    def load(self, path: str | Path | None = None) -> None:
        """Reload all namespace indexes from disk (replaces current state)."""
        if path:
            self._base_dir = Path(path)
        self._indexes = {ns: None for ns in self._indexes}
        self._load_all()


# ── Module-level singleton ────────────────────────────────────────────────────
# Agents import this directly so they share one in-process memory instance.

_memory: QAgentMemory | None = None


def get_memory() -> QAgentMemory:
    """Return the shared QAgentMemory singleton, initialising it on first call."""
    global _memory
    if _memory is None:
        _memory = QAgentMemory()
        logger.info("QAgentMemory: singleton initialised at %s", config.FAISS_INDEX_DIR)
    return _memory
