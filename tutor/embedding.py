"""
embedding.py — embedding functions for the tutor index: get_embedder() picks
the local model (tutor/local_embedding.py) or gemini-embedding-2.

gemini-embedding-2 has no task_type= parameter — task instructions go
directly in the prompt text instead:
    Documents:  "title: {title} | text: {content}"
    Queries:    "task: question answering | query: {q}"
  This wrapper handles both roles cleanly via the `role` argument.

API shape (google-genai SDK):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=...)
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=[
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in texts
        ],
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    vectors = [e.values for e in result.embeddings]

  Each Content object → one separate embedding (not aggregated).
  Batching: there is no official per-call limit stated, but keep batches ≤ 50
  to stay comfortable. The indexer handles batching; this class embeds whatever
  list it's given in a single call.

Usage:
    from tutor.embedding import GeminiEmbeddingFunction

    doc_ef  = GeminiEmbeddingFunction(role="document")
    query_ef = GeminiEmbeddingFunction(role="query")
"""

from __future__ import annotations

from typing import List

Embeddings = list[list[float]]

from tutor.retrieval_config import (
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    GEMINI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
)
from backend.usage_ledger import record_embed_usage
from backend.gemini_client import get_client, invoke_with_policy

# P1.8: monotonically increasing count of embedding batch calls (each __call__
# is one batchEmbedContents request). Snapshot before/after a pipeline run to
# calibrate backend/estimator.py's embed-batch estimate.
TOTAL_EMBED_BATCHES = 0


def reset_embed_counter() -> None:
    """Reset the embedding batch counter (used by tests)."""
    global TOTAL_EMBED_BATCHES
    TOTAL_EMBED_BATCHES = 0


def snapshot_embed_batches() -> int:
    return TOTAL_EMBED_BATCHES

# Retry attempts for one embed batch (pre-existing local cap, now routed
# through the shared policy in backend.gemini_client).
_EMBED_MAX_RETRIES = 5

def get_embedder(role: str = "document", model: str | None = None):
    """Embedding function for `model` (default: EMBEDDING_MODEL). Both kinds
    are callables list[str] -> vectors with a `.model` attribute."""
    model = model or EMBEDDING_MODEL
    if model == LOCAL_EMBEDDING_MODEL:
        from tutor.local_embedding import LocalEmbeddingFunction
        return LocalEmbeddingFunction(role=role)
    if model == GEMINI_EMBEDDING_MODEL:
        return GeminiEmbeddingFunction(role=role)
    raise ValueError(f"unknown embedding model {model!r}")


class GeminiEmbeddingFunction:
    """
    Callable embedding function for gemini-embedding-2: list[str] -> vectors.

    Args:
        role: "document" (indexing) or "query" (retrieval).
              Controls how the text is formatted before embedding.
        api_key: Gemini API key. Defaults to env var GEMINI_API_KEY — the same
                 variable used everywhere else in NorAI.
        dims:    Output dimensionality (128–3072). Default: EMBEDDING_DIMS.
    """

    def __init__(
        self,
        role: str = "document",
        api_key: str | None = None,
        dims: int = EMBEDDING_DIMS,
    ) -> None:
        if role not in ("document", "query"):
            raise ValueError(f"role must be 'document' or 'query', got {role!r}")
        self._role = role
        self._dims = dims

        # Lazy import so the module is importable even if google-genai isn't
        # installed yet (e.g. during unit-test scaffolding with mocks).
        try:
            from google import genai  # type: ignore
            from google.genai import types as genai_types  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "google-genai is required for GeminiEmbeddingFunction. "
                "Install it with: pip install google-genai"
            ) from exc

        resolved_key = api_key
        if not resolved_key:
            # Shared factory: config.get_api_key() (env + .env + validation).
            self._client = get_client()
        else:
            self._client = genai.Client(api_key=resolved_key)
        self._types = genai_types
        self._model = GEMINI_EMBEDDING_MODEL

    model = GEMINI_EMBEDDING_MODEL

    # ── Prompt formatting ─────────────────────────────────────────────────────

    def _format_document(self, text: str, title: str | None = None) -> str:
        """
        Asymmetric document format for gemini-embedding-2 retrieval tasks.
        Per Google's docs:  "title: {title} | text: {content}"
        If there is no title, use "title: none".
        """
        t = title if title else "none"
        return f"title: {t} | text: {text}"

    def _format_query(self, text: str) -> str:
        """
        Asymmetric query format for gemini-embedding-2 QA retrieval.
        Per Google's docs: "task: question answering | query: {content}"
        """
        return f"task: question answering | query: {text}"

    # ── Core ──────────────────────────────────────────────────────────────────

    def __call__(self, input: List[str]) -> Embeddings:  # noqa: A002
        """
        Embed a batch: role=document for indexing, role=query for retrieval.

        Each string is wrapped in its own Content object so gemini-embedding-2
        returns separate embeddings (not one aggregated embedding for the batch).
        """
        types = self._types
        global TOTAL_EMBED_BATCHES
        TOTAL_EMBED_BATCHES += 1

        formatted = [
            self._format_document(t) if self._role == "document" else self._format_query(t)
            for t in input
        ]

        contents = [
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in formatted
        ]

        def _embed_once() -> Embeddings:
            result = self._client.models.embed_content(
                model=self._model,
                contents=contents,
                config=types.EmbedContentConfig(output_dimensionality=self._dims),
            )
            billable = None
            try:
                meta = result.metadata
                billable = getattr(meta, "billable_character_count", None)
            except Exception:  # noqa: BLE001
                billable = None
            if not billable:
                billable = sum(len(t) for t in formatted)
            record_embed_usage("embed", self._model, billable)
            return [e.values for e in result.embeddings]

        # Shared retry policy; embeddings draw on a separate quota, so they
        # were never RPM-gated (rate_limited=False preserves that).
        return invoke_with_policy(
            _embed_once,
            node="embed",
            max_retries=_EMBED_MAX_RETRIES,
            rate_limited=False,
        )