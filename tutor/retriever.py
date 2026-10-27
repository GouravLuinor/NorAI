"""
retriever.py — Query interface over a lecture's tutor index (vector_store.py).

Design:
  • Public functions: retrieve(query, ...) and retrieve_images(query, ...).
  • Returns lists of dicts — same shape whether called from a LangGraph node or a test.
  • Does NOT call the LLM. Just retrieval.
  • One query embedding per question: the text and image lookups run in
    parallel graph branches and share it through _embed_query's cache.
  • If a lecture has no index yet but has its artifacts (lectures processed
    before the index existed), it is built once on first use.

RetrievedChunk schema (P3.2 hybrid, per kind):
    {
        "kind":         "transcript" | "notes",
        "text":         str,
        "heading":      str,      # "Transcript 3:42" for transcript windows
        "heading_path": str,      # "Transcript 3:42–4:11" / note breadcrumb
        "chapter_id":   int | None,
        "source":       str,      # notes .md path ("" for transcript)
        "start", "end": float | None  # seconds (transcript windows only)
        "distance":     float | None, # cosine distance; None if BM25-only
        "chunk_id":     str,
        "relevant":     bool,     # distance <= CONFIDENCE_THRESHOLD (P3.8)
    }

RetrievedImage schema:
    {"path", "section", "caption", "importance", "chapter_id", "distance"}
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from tutor.bm25 import BM25Okapi, reciprocal_rank_fusion_scored, tokenize
from tutor.retrieval_config import (
    ADAPTIVE_SCORE_DROPOFF_RATIO,
    ADAPTIVE_TOP_K_CANDIDATES,
    CONFIDENCE_THRESHOLD,
    IMAGE_MAX_DISTANCE,
    MIN_RESULTS,
    RRF_K,
    TOP_K,
    TOP_K_IMAGES,
    TOP_K_NOTES,
    TOP_K_TRANSCRIPT,
)
from tutor.vector_store import VectorStore, index_dir, load_cached

DEFAULT_INDEX_ROOT = Path("outputs")


class IndexNotBuiltError(RuntimeError):
    """Raised when a lecture has no tutor index and nothing to build one from."""


# ── index access ──────────────────────────────────────────────────────────────

_build_locks: dict[str, threading.Lock] = {}
_build_locks_guard = threading.Lock()


def _lecture_root(output_dir: Optional[str]) -> Path:
    return Path(output_dir) if output_dir else DEFAULT_INDEX_ROOT


def _get_store(output_dir: Optional[str] = None) -> VectorStore:
    root = _lecture_root(output_dir)
    idx = index_dir(root)
    if VectorStore.exists(idx):
        return load_cached(idx)
    if not any((root / "notes").glob("chapter_*.md")) and not any((root / "transcripts").glob("*.json")):
        raise IndexNotBuiltError(
            f"No tutor index at {idx} and no notes/transcript to build one from."
        )
    with _build_locks_guard:
        lock = _build_locks.setdefault(str(root.resolve()), threading.Lock())
    with lock:
        if not VectorStore.exists(idx):
            from tutor.indexing import build_lecture_index
            build_lecture_index(root)
    return load_cached(idx)


# ── shared query embedding ────────────────────────────────────────────────────

_qcache: dict[str, list[float]] = {}
_qlocks: dict[str, threading.Lock] = {}
_qguard = threading.Lock()
_QCACHE_MAX = 512


def _embed_query(query: str) -> list[float]:
    """Embed a query once even when two graph branches ask concurrently."""
    with _qguard:
        if query in _qcache:
            return _qcache[query]
        lock = _qlocks.setdefault(query, threading.Lock())
    with lock:
        with _qguard:
            if query in _qcache:
                return _qcache[query]
        from tutor.embedding import GeminiEmbeddingFunction
        vec = list(GeminiEmbeddingFunction(role="query")([query])[0])
        with _qguard:
            _qcache[query] = vec
            _qlocks.pop(query, None)
            while len(_qcache) > _QCACHE_MAX:
                _qcache.pop(next(iter(_qcache)))
        return vec


# ── BM25 (per store version, per kind) ────────────────────────────────────────

_bm25_cache: dict[tuple[int, str], dict] = {}
_bm25_guard = threading.Lock()


def _get_bm25(store: VectorStore, kind: str) -> dict:
    key = (id(store), kind)
    with _bm25_guard:
        hit = _bm25_cache.get(key)
    if hit is not None:
        return hit
    rows = store.rows(kind)
    docs = [tokenize(store.docs[r]) for r in rows]
    entry = {"rows": rows, "bm25": BM25Okapi(docs) if docs else None}
    with _bm25_guard:
        if len(_bm25_cache) > 64:
            _bm25_cache.clear()
        _bm25_cache[key] = entry
    return entry


# ── result shaping ────────────────────────────────────────────────────────────

def _unmap_chapter_id(value) -> Optional[int]:
    """P2.5: index metadata stores the sentinel -1 for 'no chapter'. Map it —
    and any other negative/garbage value — back to None so chunks/citations/
    frontend never see -1."""
    if value is None or value == "":
        return None
    try:
        cid = int(value)
    except (TypeError, ValueError):
        return None
    return cid if cid >= 0 else None


def _chunk_from_doc(doc_id: str, text: str, meta: dict, distance: Optional[float]) -> dict:
    """Build a RetrievedChunk dict, computing the P3.8 `relevant` flag."""
    return {
        "kind": meta.get("kind", "notes"),
        "text": text,
        "heading": meta.get("heading", ""),
        "heading_path": meta.get("heading_path", ""),
        "chapter_id": _unmap_chapter_id(meta.get("chapter_id")),
        "source": meta.get("source", ""),
        "start": meta.get("start"),
        "end": meta.get("end"),
        "distance": distance,
        "chunk_id": doc_id,
        "relevant": distance is not None and distance <= CONFIDENCE_THRESHOLD,
        "context": "",
    }


def _attach_context(chunks: list[dict]) -> list[dict]:
    """P3.4: attach parent/sibling section context for note chunks.
    Best-effort: unreadable/missing files leave context empty."""
    from tutor.context_expand import expand_context

    for c in chunks:
        if c.get("kind") != "notes":
            continue
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


def _hybrid(store: VectorStore, qvec, query: str, kind: str,
            chapter_id: Optional[int], k: int, candidates: int) -> list[dict]:
    """Cosine + BM25 candidates for one doc kind, fused with RRF.

    No distance-threshold trimming here: measured on real lectures, questions
    the lecture never covers still land at cosine 0.22–0.31, inside any useful
    threshold, so "is this covered?" is decided by the answer model reading
    the passages, not by a distance cutoff.
    """
    by_id: dict = {}
    cosine_ids: list[str] = []
    for row, dist in store.query(qvec, kind=kind, chapter_id=chapter_id, n=candidates):
        _id = store.ids[row]
        cosine_ids.append(_id)
        by_id[_id] = _chunk_from_doc(_id, store.docs[row], store.metas[row], dist)

    bm = _get_bm25(store, kind)
    bm25_ids: list[str] = []
    if bm["bm25"] is not None:
        scores = bm["bm25"].get_scores(tokenize(query))
        for i in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:candidates]:
            if scores[i] <= 0:
                break
            row = bm["rows"][i]
            meta = store.metas[row]
            if chapter_id is not None and meta.get("chapter_id") != chapter_id:
                continue
            _id = store.ids[row]
            bm25_ids.append(_id)
            if _id not in by_id:
                by_id[_id] = _chunk_from_doc(_id, store.docs[row], meta, None)

    fused = reciprocal_rank_fusion_scored([cosine_ids, bm25_ids], k=RRF_K)
    return [by_id[_id] for _id, _ in fused if _id in by_id][:k]


# ── public API ────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    chapter_id: Optional[int] = None,
    k: int = TOP_K,
    output_dir: Optional[str] = None,
    hybrid: bool = True,
    candidates: int = ADAPTIVE_TOP_K_CANDIDATES,
    kinds: tuple[str, ...] = ("transcript", "notes"),
) -> list[dict]:
    """
    Retrieve lecture passages for a question: transcript windows first (what
    the lecturer said), then study-note sections (the summary).

    `k` caps the total; the split defaults to TOP_K_TRANSCRIPT transcript
    windows + TOP_K_NOTES note sections. Pass kinds=("notes",) for the legacy
    notes-only behaviour (quiz source lookup).
    """
    store = _get_store(output_dir)
    qvec = _embed_query(query)
    quota = {"transcript": TOP_K_TRANSCRIPT, "notes": TOP_K_NOTES}
    if len(kinds) == 1:
        quota[kinds[0]] = k

    out: list[dict] = []
    for kind in kinds:
        if not store.count(kind):
            continue
        n = quota.get(kind, k)
        if hybrid:
            hits = _hybrid(store, qvec, query, kind, chapter_id, n, candidates)
        else:
            hits = [
                _chunk_from_doc(store.ids[r], store.docs[r], store.metas[r], d)
                for r, d in store.query(qvec, kind=kind, chapter_id=chapter_id, n=n)
            ]
        out.extend(hits)
    return _attach_context(out[:max(k, 1)] if len(kinds) == 1 else out)


def retrieve_images(
    query: str,
    chapter_id: Optional[int] = None,
    k: int = TOP_K_IMAGES,
    output_dir: Optional[str] = None,
    max_distance: float = IMAGE_MAX_DISTANCE,
) -> list[dict]:
    """
    Screenshots whose caption/OCR is close to the question. Only matches within
    `max_distance` are returned: an unrelated slide in the prompt invites the
    model to describe it as if it answered the question.
    """
    store = _get_store(output_dir)
    if not store.count("screenshot"):
        return []
    qvec = _embed_query(query)
    images: list[dict] = []
    for row, dist in store.query(qvec, kind="screenshot", chapter_id=chapter_id, n=k):
        if dist > max_distance:
            continue
        meta = store.metas[row]
        images.append({
            "path": meta["path"],
            "section": meta.get("section", ""),
            "caption": store.docs[row],
            "importance": meta.get("importance", 0),
            "chapter_id": _unmap_chapter_id(meta.get("chapter_id")),
            "distance": dist,
        })
    images.sort(key=lambda x: (x["distance"], -x["importance"]))
    return images[:k]
