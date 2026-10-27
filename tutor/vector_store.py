"""
vector_store.py — per-lecture embedding store (replaces Chroma).

A lecture's tutor index holds a few hundred vectors at most (note sections,
transcript windows, screenshot captions). At that size an exact brute-force
cosine scan over one matrix is microseconds, so an ANN index buys nothing and
costs a lot: Chroma 0.6 preallocated a 3.1 MB HNSW file per collection
(~6.3 MB per lecture for ~30 vectors) and added ~90 MB of imports per process.

Layout (one directory per lecture, written atomically):
    <dir>/vectors.npy   float16 [n, dims], L2-normalised
    <dir>/docs.json     {"dims", "ids", "docs", "metas"} aligned with the rows

Every doc's metadata carries a "kind" ("notes" | "transcript" | "screenshot")
so the three logical collections share one file and one load.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from tutor.retrieval_config import EMBEDDING_DIMS

INDEX_DIRNAME = "index"
_VECTORS = "vectors.npy"
_DOCS = "docs.json"
_EMBED_BATCH = 100  # batchEmbedContents accepts up to 100 requests per call


def index_dir(lecture_dir: str | Path) -> Path:
    return Path(lecture_dir) / "tutor" / INDEX_DIRNAME


def has_tutor_index(lecture_dir: str | Path) -> bool:
    """Completion signal for a lecture's tutor stage. A legacy Chroma store
    counts too: those lectures get a real index built lazily on their first
    tutor query (retriever._get_store)."""
    lecture_dir = Path(lecture_dir)
    return VectorStore.exists(index_dir(lecture_dir)) or (
        lecture_dir / "tutor" / "chroma" / "chroma.sqlite3"
    ).is_file()


def _normalise(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class VectorStore:
    def __init__(self, root: str | Path, dims: int = EMBEDDING_DIMS) -> None:
        self.root = Path(root)
        self.dims = dims
        self.ids: list[str] = []
        self.docs: list[str] = []
        self.metas: list[dict] = []
        self.vectors = np.zeros((0, dims), dtype=np.float32)

    # ── persistence ───────────────────────────────────────────────────────────

    @classmethod
    def exists(cls, root: str | Path) -> bool:
        root = Path(root)
        return (root / _VECTORS).exists() and (root / _DOCS).exists()

    @classmethod
    def load(cls, root: str | Path) -> "VectorStore":
        root = Path(root)
        meta = json.loads((root / _DOCS).read_text(encoding="utf-8"))
        store = cls(root, dims=meta.get("dims", EMBEDDING_DIMS))
        store.ids = meta["ids"]
        store.docs = meta["docs"]
        store.metas = meta["metas"]
        vecs = np.load(root / _VECTORS)
        store.vectors = vecs.astype(np.float32).reshape(-1, store.dims)
        return store

    @classmethod
    def open(cls, root: str | Path) -> "VectorStore":
        """Load if present, else an empty store rooted at `root`."""
        return cls.load(root) if cls.exists(root) else cls(root)

    def save(self) -> None:
        """Atomic write: readers never see a half-written index."""
        self.root.mkdir(parents=True, exist_ok=True)
        tmp_vec = self.root / f".{_VECTORS}.tmp"
        tmp_docs = self.root / f".{_DOCS}.tmp"
        with open(tmp_vec, "wb") as fh:
            np.save(fh, self.vectors.astype(np.float16))
        tmp_docs.write_text(
            json.dumps({"dims": self.dims, "ids": self.ids, "docs": self.docs, "metas": self.metas},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_vec, self.root / _VECTORS)
        os.replace(tmp_docs, self.root / _DOCS)

    # ── writes ────────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.ids)

    def count(self, kind: Optional[str] = None) -> int:
        if kind is None:
            return len(self.ids)
        return sum(1 for m in self.metas if m.get("kind") == kind)

    def sync(
        self,
        kind: str,
        ids: list[str],
        docs: list[str],
        metas: list[dict],
        embed: Callable[[list[str]], list[list[float]]],
    ) -> tuple[int, int]:
        """Make the `kind` docs exactly (ids, docs, metas).

        Ids are content hashes, so unchanged docs keep their vectors and only
        new ones are embedded. Returns (added, removed).
        """
        wanted = dict(zip(ids, range(len(ids))))
        keep = [i for i, m in enumerate(self.metas)
                if m.get("kind") != kind or self.ids[i] in wanted]
        removed = len(self.ids) - len(keep)
        have = {self.ids[i] for i in keep}
        self.ids = [self.ids[i] for i in keep]
        self.docs = [self.docs[i] for i in keep]
        self.metas = [self.metas[i] for i in keep]
        self.vectors = self.vectors[keep] if keep else np.zeros((0, self.dims), dtype=np.float32)

        new = [j for _id, j in wanted.items() if _id not in have]
        if new:
            vecs: list[list[float]] = []
            for b in range(0, len(new), _EMBED_BATCH):
                vecs.extend(embed([docs[j] for j in new[b:b + _EMBED_BATCH]]))
            mat = _normalise(np.asarray(vecs, dtype=np.float32).reshape(-1, self.dims))
            self.vectors = np.vstack([self.vectors, mat])
            for j in new:
                self.ids.append(ids[j])
                self.docs.append(docs[j])
                self.metas.append({**metas[j], "kind": kind})
        return len(new), removed

    # ── reads ─────────────────────────────────────────────────────────────────

    def rows(self, kind: Optional[str] = None, chapter_id: Optional[int] = None) -> list[int]:
        return [
            i for i, m in enumerate(self.metas)
            if (kind is None or m.get("kind") == kind)
            and (chapter_id is None or m.get("chapter_id") == chapter_id)
        ]

    def query(
        self,
        query_vec: list[float] | np.ndarray,
        kind: Optional[str] = None,
        chapter_id: Optional[int] = None,
        n: int = 20,
    ) -> list[tuple[int, float]]:
        """Top-n (row, cosine distance) among rows matching kind/chapter."""
        rows = self.rows(kind, chapter_id)
        if not rows:
            return []
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        qn = np.linalg.norm(q)
        if qn:
            q = q / qn
        sims = self.vectors[rows] @ q
        order = np.argsort(-sims)[:n]
        return [(rows[o], float(1.0 - sims[o])) for o in order]


# ── process-wide cache of loaded stores ───────────────────────────────────────

_cache: dict[str, tuple[int, VectorStore]] = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 32


def load_cached(root: str | Path) -> VectorStore:
    """Load a store, reusing the in-memory copy until the file changes on disk
    (re-indexing replaces the file, so the mtime check picks it up)."""
    root = Path(root)
    mtime = (root / _DOCS).stat().st_mtime_ns
    key = str(root.resolve())
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
    store = VectorStore.load(root)
    with _cache_lock:
        _cache[key] = (mtime, store)
        while len(_cache) > _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
    return store
