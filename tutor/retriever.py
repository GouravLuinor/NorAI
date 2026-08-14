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

RetrievedChunk schema (study notes, P3.2 hybrid):
    {
        "text":         str,
        "heading":      str,
        "heading_path": str,
        "chapter_id":   int | None,
        "source":       str,
        "distance":     float,    # cosine distance (lower = more similar); None
                                  # if the chunk only matched via BM25
        "chunk_id":     str,      # stable Chroma id (used for verified citations, P3.3)
        "relevant":     bool,     # distance <= CONFIDENCE_THRESHOLD (P3.8 gating)
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
from pathlib import Path
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
    ADAPTIVE_TOP_K_CANDIDATES,
    ADAPTIVE_SCORE_DROPOFF_RATIO,
    MIN_RESULTS,
    RRF_K,
    CONFIDENCE_THRESHOLD,
)
from tutor.bm25 import BM25Okapi, tokenize, reciprocal_rank_fusion, reciprocal_rank_fusion_scored


class IndexNotBuiltError(RuntimeError):
    """Raised when the Chroma index hasn't been built yet."""


# ── Singleton Chroma client (shared per chroma_dir) ───────────────────────────

@lru_cache(maxsize=10)
def _get_client(chroma_dir: Optional[str] = None):
    """Cached PersistentClient per chroma_dir path — avoids Chroma 1.x multi-client Rust bug."""
    path = Path(chroma_dir) if chroma_dir else CHROMA_DIR
    if not path.exists():
        raise IndexNotBuiltError(
            f"Chroma index directory not found at {path}. "
            "Run indexing scripts first (e.g. python -m tutor.build_index)."
        )
    return chromadb.PersistentClient(path=str(path))


@lru_cache(maxsize=20)
def _get_collection_by_name(collection_name: str, role: str = "query", chroma_dir: Optional[str] = None):
    """
    Module-level singleton cache: reuses the shared PersistentClient per chroma_dir.
    lru_cache ensures each unique (name, role, chroma_dir) pair is built once per process.
    """
    client = _get_client(chroma_dir)
    target_path = Path(chroma_dir) if chroma_dir else CHROMA_DIR

    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=GeminiEmbeddingFunction(role=role),
        )
    except Exception as exc:
        raise IndexNotBuiltError(
            f"Collection '{collection_name}' not found in {target_path}. "
            "Run the appropriate indexing script."
        ) from exc

    return collection


def _get_notes_collection(chroma_dir: Optional[str] = None):
    """Get or create the study notes collection (query role)."""
    return _get_collection_by_name(NOTES_COLLECTION, role="query", chroma_dir=chroma_dir)


def _get_screenshot_collection(chroma_dir: Optional[str] = None):
    """Get or create the screenshot captions collection (query role)."""
    return _get_collection_by_name(SCREENSHOT_COLLECTION_NAME, role="query", chroma_dir=chroma_dir)


# ── Hybrid lexical index (BM25) ───────────────────────────────────────────────

@lru_cache(maxsize=10)
def _get_bm25_corpus(chroma_dir: Optional[str] = None):
    """
    Lazy BM25 corpus over every document in the notes collection, cached per
    chroma_dir. Built once per process — cheap relative to the embed cost.
    Returns {"ids", "docs", "texts", "metadatas"} aligned index-wise.
    """
    collection = _get_notes_collection(chroma_dir=chroma_dir)
    got = collection.get(include=["documents", "metadatas"])
    ids = list(got.get("ids", []))
    documents = got.get("documents", []) or []
    metadatas = got.get("metadatas", []) or []
    docs = [tokenize(d) for d in documents]
    bm25 = BM25Okapi(docs) if docs else None
    return {"ids": ids, "docs": docs, "texts": documents, "metadatas": metadatas, "bm25": bm25}


def _chunk_from_doc(doc_id: str, text: str, meta: dict, distance: Optional[float]) -> dict:
    """Build a RetrievedChunk dict, computing the P3.8 `relevant` flag."""
    return {
        "text": text,
        "heading": meta.get("heading", ""),
        "heading_path": meta.get("heading_path", ""),
        "chapter_id": meta.get("chapter_id") or None,
        "source": meta.get("source", ""),
        "distance": distance,
        "chunk_id": doc_id,
        "relevant": distance is not None and distance <= CONFIDENCE_THRESHOLD,
        "context": "",
    }


def _attach_context(chunks: list[dict]) -> list[dict]:
    """P3.4: attach parent/sibling section context from the source .md file.
    Best-effort: unreadable/missing files leave context empty."""
    from tutor.context_expand import expand_context

    for c in chunks:
        try:
            c["context"] = expand_context(c)
        except Exception:
            c["context"] = ""
    return chunks


def _rrf_merge(
    cosine_ids: list[str],
    bm25_ids: list[str],
    by_id: dict,
    k: int,
    min_results: int = MIN_RESULTS,
    dropoff_ratio: float = ADAPTIVE_SCORE_DROPOFF_RATIO,
    max_k: int = TOP_K,
) -> list[dict]:
    """
    Fuse cosine + BM25 rankings with Reciprocal Rank Fusion, then adaptively trim:
    1. Drop results above CONFIDENCE_THRESHOLD unless fewer than min_results remain.
    2. P3.2: Dynamically size top-k based on score drop-off curve (elbow cutoff):
       if score drops below `dropoff_ratio` of the top result, truncate after
       at least `min_results`.
    """
    scored = reciprocal_rank_fusion_scored([cosine_ids, bm25_ids], k=k)
    fused_entries = [(did, score) for did, score in scored if did in by_id]

    if not fused_entries:
        return []

    chunks_with_score = [(by_id[did], score) for did, score in fused_entries]
    strong_with_score = [(c, score) for c, score in chunks_with_score if c["relevant"]]

    if len(strong_with_score) >= min_results:
        top_score = strong_with_score[0][1]
        adaptive_strong: list[dict] = []
        for i, (c, score) in enumerate(strong_with_score):
            if i < min_results:
                adaptive_strong.append(c)
            elif score >= top_score * dropoff_ratio and len(adaptive_strong) < max_k:
                adaptive_strong.append(c)
            else:
                break
        return adaptive_strong

    # Not enough strong matches: keep the best few as weak context
    return [c for c, _ in chunks_with_score[:min_results]]


# ── Public API ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    chapter_id: Optional[int] = None,
    k: int = TOP_K,
    output_dir: Optional[str] = None,
    hybrid: bool = True,
    candidates: int = ADAPTIVE_TOP_K_CANDIDATES,
) -> list[dict]:
    """
    Query the study-notes index and return the top-k most relevant chunks.

    P3.2 hybrid: cosine (Chroma) candidates and BM25 candidates are fused with
    Reciprocal Rank Fusion; results are then confidence-trimmed (P3.8).

    Args:
        query:      The user's question (or rewritten query).
        chapter_id: If set, restrict results to this chapter.
        k:          Number of results to return (upper bound).
        output_dir: If set, use this directory's Chroma index instead of default.
        hybrid:     Enable BM25 + RRF fusion (default True).
        candidates: Candidate pool size per system for fusion.

    Returns:
        List of RetrievedChunk dicts (with chunk_id + relevant), ordered by
        descending fused relevance. Length is between MIN_RESULTS and k.

    Raises:
        IndexNotBuiltError: if the notes index hasn't been built yet.
    """
    chroma_dir = str(Path(output_dir) / "tutor" / "chroma") if output_dir else None
    collection = _get_notes_collection(chroma_dir=chroma_dir)

    where: dict | None = None
    if chapter_id is not None:
        where = {"chapter_id": {"$eq": chapter_id}}

    n_results = candidates if hybrid else max(k, candidates)
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    cosine_ids = list(results["ids"][0])
    by_id: dict = {}
    for doc_id, doc, meta, dist in zip(
        cosine_ids,
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        by_id[doc_id] = _chunk_from_doc(doc_id, doc, meta, dist)

    if not hybrid:
        return _attach_context([by_id[did] for did in cosine_ids if did in by_id][:k])

    # BM25 candidates (optionally chapter-filtered to mirror the cosine where)
    bm25_corpus = _get_bm25_corpus(chroma_dir=chroma_dir)
    bm25_ids: list[str] = []
    if bm25_corpus["bm25"] is not None:
        q_tokens = tokenize(query)
        scores = bm25_corpus["bm25"].get_scores(q_tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for i in ranked:
            if scores[i] <= 0:
                continue
            meta = bm25_corpus["metadatas"][i] or {}
            if chapter_id is not None and (meta.get("chapter_id") or None) != chapter_id:
                continue
            doc_id = bm25_corpus["ids"][i]
            bm25_ids.append(doc_id)
            if doc_id not in by_id:
                by_id[doc_id] = _chunk_from_doc(
                    doc_id,
                    bm25_corpus["texts"][i],
                    meta,
                    None,
                )

    merged = _rrf_merge(cosine_ids, bm25_ids, by_id, k=RRF_K)
    return _attach_context(merged[:k])


def retrieve_images(
    query: str,
    chapter_id: Optional[int] = None,
    k: int = TOP_K_IMAGES,
    output_dir: Optional[str] = None,
) -> list[dict]:
    """
    Query the screenshot captions index and return the top-k most relevant images.

    Args:
        query:      The user's question (or rewritten query).
        chapter_id: If set, restrict results to screenshots from this chapter.
        k:          Number of images to return.
        output_dir: If set, use this directory's Chroma index instead of default.

    Returns:
        List of RetrievedImage dicts, sorted by (distance ascending, importance descending).

    Raises:
        IndexNotBuiltError: if the screenshot index hasn't been built yet.
    """
    chroma_dir = str(Path(output_dir) / "tutor" / "chroma") if output_dir else None
    collection = _get_screenshot_collection(chroma_dir=chroma_dir)

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