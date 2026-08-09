"""
test_hybrid.py — Offline tests for P3.2 hybrid retrieval (BM25 + RRF) and the
P3.8 `relevant` flag. No Chroma queries, no embedding calls.

Run:
    venv/bin/python tutor/test_hybrid.py
"""

import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.bm25 import BM25Okapi, tokenize, reciprocal_rank_fusion  # noqa: E402
from tutor.retriever import _chunk_from_doc, _rrf_merge, retrieve  # noqa: E402
from tutor.retrieval_config import CONFIDENCE_THRESHOLD  # noqa: E402


def _c(doc_id: str, dist, heading="Section") -> dict:
    return {
        "text": f"text of {doc_id}",
        "heading": heading,
        "heading_path": f"Ch > {heading}",
        "chapter_id": 1,
        "source": f"outputs/x/notes/chapter_1.md",
        "distance": dist,
        "chunk_id": doc_id,
        "relevant": dist is not None and dist <= CONFIDENCE_THRESHOLD,
    }


# ── BM25 ──────────────────────────────────────────────────────────────────────

def test_tokenize_lowercases_and_splits():
    assert tokenize("Hello, WORLD 2.0!") == ["hello", "world", "2", "0"]


def test_bm25_orders_relevant_doc_first():
    corpus = [
        tokenize("Segment trees support range queries and point updates"),
        tokenize("The weather in the city is sunny today"),
    ]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(tokenize("What is a segment tree range query?"))
    assert scores[0] > scores[1]


def test_bm25_empty_corpus_does_not_crash():
    bm25 = BM25Okapi([])
    assert bm25.get_scores(tokenize("anything")) == []


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def test_rrf_fuses_and_promotes_shared():
    cosine = ["a", "b", "c", "d"]
    bm25 = ["e", "c", "a"]
    fused = reciprocal_rank_fusion([cosine, bm25])
    # 'a' and 'c' appear in both → rank above one-system-only ids
    assert fused.index("a") < fused.index("d")
    assert fused.index("c") < fused.index("d")
    assert fused.index("a") < fused.index("e")
    # All ids present exactly once
    assert len(fused) == len(set(fused)) == 5


def test_rrf_respects_k_constant():
    a = ["a", "b"]
    b = ["c", "d"]
    fused_10 = reciprocal_rank_fusion([a, b], k=10)
    fused_1 = reciprocal_rank_fusion([a, b], k=1)
    # With k=1, ranks of unshared ids dominate differently than k=10
    assert fused_1[0] == "a" == fused_10[0]  # both lists rank 'a' first overall


# ── _rrf_merge / adaptive top-k / P3.8 relevant flag ─────────────────────────

def test_merge_keeps_strong_and_drops_weak():
    by_id = {
        "s1": _c("s1", 0.20),  # strong
        "s2": _c("s2", 0.25),  # strong
        "w1": _c("w1", 0.40),  # weak
        "w2": _c("w2", 0.50),  # weak
    }
    merged = _rrf_merge(["s1", "s2", "w1", "w2"], ["w2", "s2", "s1", "w1"], by_id, k=60)
    # 2 strong results >= MIN_RESULTS → weak dropped entirely
    assert [c["chunk_id"] for c in merged] == ["s1", "s2"]
    assert all(c["relevant"] for c in merged)


def test_merge_keeps_min_results_weak_as_context():
    by_id = {"w1": _c("w1", 0.45), "w2": _c("w2", 0.50), "w3": _c("w3", 0.60)}
    merged = _rrf_merge(["w1", "w2", "w3"], ["w3", "w1", "w2"], by_id, k=60)
    assert len(merged) == 2  # MIN_RESULTS weak leftovers, never surface as refs
    assert all(c["relevant"] is False for c in merged)


def test_chunk_relevant_boundary():
    assert _chunk_from_doc("a", "t", {"heading": "H", "heading_path": "H", "chapter_id": 1, "source": "s"}, 0.35)["relevant"] is True
    assert _chunk_from_doc("a", "t", {"heading": "H", "heading_path": "H", "chapter_id": 1, "source": "s"}, 0.36)["relevant"] is False
    assert _chunk_from_doc("a", "t", {"heading": "H", "heading_path": "H", "chapter_id": 1, "source": "s"}, None)["relevant"] is False


def test_retrieve_keeps_hybrid_knobs():
    sig = inspect.signature(retrieve)
    params = sig.parameters
    assert "hybrid" in params and params["hybrid"].default is True
    assert "candidates" in params


if __name__ == "__main__":
    import traceback

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if failures else 0)
