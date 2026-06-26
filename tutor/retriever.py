"""
retriever.py — Query interface over the persisted Chroma indexes.

Design:
  • Two public functions: retrieve(query, ...) and retrieve_images(query, ...)
  • Returns lists of dicts — same shape whether called from a LangGraph node or a test.
  • Does NOT call the LLM. Just retrieval.
  • Chroma client is created once per process (module-level singletons) with
    role="query" embedding function. This avoids re-constructing the google-genai
    client on every invocation.
  • If an index doesn't exist yet (build scripts haven't been run), raises
    a clear IndexNotBuiltError rather than a cryptic Chroma exception.

RetrievedChunk schema (study notes):
    {
        "text":         str,
        "heading":      str,
        "heading_path": str,
        "chapter_id":   int | None,
        "source":       str,
        "distance":     float,   # cosine distance (lower = more similar)
    }

RetrievedImage schema (screenshots):
    {
        "path":         str,
        "section":      str,
        "importance":   int,
        "chapter_id":   int | None,
        "distance":     float,
    }
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

import chromadb

from tutor.embedding import GeminiEmbeddingFunction
from tutor.retrieval_config import (
    CHROMA_DIR,
    NOTES_COLLECTION,
    TOP_K,
    SCREENSHOT_COLLECTION_NAME,
    TOP_K_IMAGES,
)


class IndexNotBuiltError(RuntimeError):
    """Raised when the Chroma index hasn't been built yet."""


# ── Singleton Chroma client (shared across all collections) ────────────────────

@lru_cache(maxsize=1)
def _get_client():
    """One PersistentClient per process — avoids Chroma 1.x multi-client Rust bug."""
    if not CHROMA_DIR.exists():
        raise IndexNotBuiltError(
            f"Chroma index directory not found at {CHROMA_DIR}. "
            "Run indexing scripts first (e.g. python -m tutor.build_index)."
        )
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


@lru_cache(maxsize=2)
def _get_collection_by_name(collection_name: str, role: str = "query"):
    """
    Module-level singleton cache: reuses the shared PersistentClient.
    lru_cache ensures each unique (name, role) pair is built once per process.
    """
    client = _get_client()

    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=GeminiEmbeddingFunction(role=role),
        )
    except Exception as exc:
        raise IndexNotBuiltError(
            f"Collection '{collection_name}' not found in {CHROMA_DIR}. "
            "Run the appropriate indexing script."
        ) from exc

    return collection


def _get_notes_collection():
    """Get or create the study notes collection (query role)."""
    return _get_collection_by_name(NOTES_COLLECTION, role="query")


def _get_screenshot_collection():
    """Get or create the screenshot captions collection (query role)."""
    return _get_collection_by_name(SCREENSHOT_COLLECTION_NAME, role="query")


# ── Public API ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    chapter_id: Optional[int] = None,
    k: int = TOP_K,
) -> list[dict]:
    """
    Query the study-notes index and return the top-k most relevant chunks.

    Args:
        query:      The user's question (or rewritten query).
        chapter_id: If set, restrict results to this chapter.
        k:          Number of results to return.

    Returns:
        List of RetrievedChunk dicts, ordered by ascending cosine distance.

    Raises:
        IndexNotBuiltError: if the notes index hasn't been built yet.
    """
    collection = _get_notes_collection()

    where: dict | None = None
    if chapter_id is not None:
        where = {"chapter_id": {"$eq": chapter_id}}

    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append(
            {
                "text": doc,
                "heading": meta.get("heading", ""),
                "heading_path": meta.get("heading_path", ""),
                "chapter_id": meta.get("chapter_id") or None,
                "source": meta.get("source", ""),
                "distance": dist,
            }
        )

    return chunks


def retrieve_images(
    query: str,
    chapter_id: Optional[int] = None,
    k: int = TOP_K_IMAGES,
) -> list[dict]:
    """
    Query the screenshot captions index and return the top-k most relevant images.

    Args:
        query:      The user's question (or rewritten query).
        chapter_id: If set, restrict results to screenshots from this chapter.
        k:          Number of images to return.

    Returns:
        List of RetrievedImage dicts, sorted by (distance ascending, importance descending).

    Raises:
        IndexNotBuiltError: if the screenshot index hasn't been built yet.
    """
    collection = _get_screenshot_collection()

    where: dict | None = None
    if chapter_id is not None:
        where = {"chapter_id": {"$eq": chapter_id}}

    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=where,
        include=["metadatas", "distances"],
    )

    images: list[dict] = []
    if results["ids"] and results["ids"][0]:
        for idx, shot_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][idx]
            dist = results["distances"][0][idx]
            images.append({
                "path": meta["path"],
                "section": meta.get("section", ""),
                "importance": meta.get("importance", 0),
                "chapter_id": meta.get("chapter_id"),
                "distance": dist,
            })

    # Sort by distance (ascending), then importance (descending) as tiebreaker
    images.sort(key=lambda x: (x["distance"], -x["importance"]))
    return images[:k]