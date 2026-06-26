"""
embedding.py — Custom Chroma EmbeddingFunction for gemini-embedding-2.

Why not use chromadb.utils.embedding_functions.GoogleGeminiEmbeddingFunction?
  The built-in wrapper only documents gemini-embedding-001 and uses the
  task_type= parameter (e.g. task_type="RETRIEVAL_DOCUMENT").
  gemini-embedding-2 dropped the task_type parameter entirely — task
  instructions go directly in the prompt text instead:
    Documents:  "title: {title} | text: {content}"
    Queries:    "task: question answering | query: {q}"
  Using the built-in wrapper with gemini-embedding-2 would silently ignore the
  task_type flag and skip the prompt formatting, hurting retrieval quality.

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

import os
from typing import List

from chromadb import EmbeddingFunction, Embeddings

from tutor.retrieval_config import EMBEDDING_DIMS, EMBEDDING_MODEL
from dotenv import load_dotenv

load_dotenv()

class GeminiEmbeddingFunction(EmbeddingFunction):
    """
    Chroma-compatible embedding function for gemini-embedding-2.

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

        resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Gemini API key not found. Set GEMINI_API_KEY or pass api_key=."
            )

        self._client = genai.Client(api_key=resolved_key)
        self._types = genai_types
        self._model = EMBEDDING_MODEL

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
        Called by Chroma for both .add() (role=document) and .query() (role=query).

        Each string is wrapped in its own Content object so gemini-embedding-2
        returns separate embeddings (not one aggregated embedding for the batch).
        """
        types = self._types

        formatted = [
            self._format_document(t) if self._role == "document" else self._format_query(t)
            for t in input
        ]

        contents = [
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in formatted
        ]

        result = self._client.models.embed_content(
            model=self._model,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=self._dims),
        )

        return [e.values for e in result.embeddings]