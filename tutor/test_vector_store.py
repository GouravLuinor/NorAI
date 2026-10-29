"""
test_vector_store.py — Offline tests for the per-lecture tutor index
(vector_store.py), transcript windowing (indexing.py), and the retriever on
top of them. Embeddings are faked (deterministic bag-of-words vectors); no
API calls.

Run:
    venv/bin/python tutor/test_vector_store.py
"""

import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor import retriever  # noqa: E402
from tutor.indexing import build_lecture_index, transcript_windows  # noqa: E402
from tutor.retrieval_config import EMBEDDING_DIMS  # noqa: E402
from tutor.vector_store import VectorStore, has_tutor_index, index_dir, load_cached  # noqa: E402


def _vec(text: str) -> list[float]:
    """Deterministic fake embedding: hashed bag of words."""
    v = np.zeros(EMBEDDING_DIMS, dtype=np.float32)
    for w in text.lower().split():
        v[hash(w.strip(".,?!")) % EMBEDDING_DIMS] += 1.0
    return v.tolist()


class FakeEmbed:
    def __init__(self):
        self.calls = 0
        self.texts = 0

    def __call__(self, texts):
        self.calls += 1
        self.texts += len(texts)
        return [_vec(t) for t in texts]


# ── VectorStore ───────────────────────────────────────────────────────────────

def test_sync_embeds_only_new_and_removes_stale():
    with tempfile.TemporaryDirectory() as tmp:
        emb = FakeEmbed()
        store = VectorStore(Path(tmp) / "idx")
        added, removed = store.sync("notes", ["a", "b"], ["alpha text", "beta text"], [{}, {}], emb)
        assert (added, removed) == (2, 0) and emb.texts == 2
        added, removed = store.sync("notes", ["b", "c"], ["beta text", "gamma text"], [{}, {}], emb)
        assert (added, removed) == (1, 1)
        assert emb.texts == 3, "unchanged doc 'b' must not be re-embedded"
        assert sorted(store.ids) == ["b", "c"]


def test_sync_is_per_kind():
    with tempfile.TemporaryDirectory() as tmp:
        emb = FakeEmbed()
        store = VectorStore(Path(tmp) / "idx")
        store.sync("notes", ["n1"], ["note"], [{}], emb)
        store.sync("transcript", ["t1"], ["said"], [{}], emb)
        store.sync("notes", [], [], [], emb)
        assert store.ids == ["t1"], "syncing notes must not touch transcript docs"


def test_query_orders_by_cosine_and_filters():
    with tempfile.TemporaryDirectory() as tmp:
        store = VectorStore(Path(tmp) / "idx")
        store.sync("notes", ["a", "b", "c"],
                   ["dynamic programming table", "binary tree depth", "dynamic programming memo"],
                   [{"chapter_id": 1}, {"chapter_id": 1}, {"chapter_id": 2}], FakeEmbed())
        hits = store.query(_vec("dynamic programming"), kind="notes", n=3)
        assert {store.ids[r] for r, _ in hits[:2]} == {"a", "c"}
        assert hits[0][1] <= hits[-1][1], "distances ascend"
        only_ch2 = store.query(_vec("dynamic programming"), kind="notes", chapter_id=2, n=3)
        assert [store.ids[r] for r, _ in only_ch2] == ["c"]
        assert store.query(_vec("x"), kind="screenshot") == []


def test_save_load_roundtrip_and_cache_invalidation():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "idx"
        store = VectorStore(root)
        store.sync("notes", ["a"], ["alpha"], [{"heading": "H"}], FakeEmbed())
        store.save()
        loaded = load_cached(root)
        assert loaded.ids == ["a"] and loaded.metas[0]["kind"] == "notes"
        assert np.allclose(loaded.vectors, store.vectors, atol=1e-3), "float16 on disk"
        assert load_cached(root) is loaded, "unchanged file served from cache"
        time.sleep(0.01)
        store.sync("notes", ["a", "b"], ["alpha", "beta"], [{}, {}], FakeEmbed())
        store.save()
        assert load_cached(root).ids == ["a", "b"], "rewrite invalidates the cache"


def test_has_tutor_index_accepts_new_and_legacy_stores():
    with tempfile.TemporaryDirectory() as tmp:
        lec = Path(tmp) / "lec"
        assert not has_tutor_index(lec)
        legacy = lec / "tutor" / "chroma"
        legacy.mkdir(parents=True)
        (legacy / "chroma.sqlite3").write_bytes(b"")
        assert has_tutor_index(lec), "pre-migration lectures still count as complete"
        other = Path(tmp) / "other"
        store = VectorStore(index_dir(other))
        store.sync("notes", ["a"], ["alpha"], [{}], FakeEmbed())
        store.save()
        assert has_tutor_index(other)


# ── transcript windows ────────────────────────────────────────────────────────

def _segs(n: int, words: int = 10, dur: float = 4.0):
    return [{"start": i * dur, "end": (i + 1) * dur,
             "text": " ".join(f"w{i}_{j}" for j in range(words))} for i in range(n)]


def test_windows_overlap_by_one_segment_and_cover_all():
    segs = _segs(40)
    wins = transcript_windows(segs, [(1, 0.0, 80.0), (2, 80.0, 160.0)])
    assert wins[0]["start"] == 0.0 and wins[-1]["end"] == 160.0
    for prev, nxt in zip(wins, wins[1:]):
        assert nxt["start"] == prev["end"] - 4.0, "one-segment overlap"
    assert {w["chapter_id"] for w in wins} == {1, 2}
    all_text = " ".join(w["text"] for w in wins)
    assert all(s["text"].split()[0] in all_text for s in segs), "no segment dropped"


def test_windows_bounded_by_time_and_words():
    wins = transcript_windows(_segs(30, words=5, dur=10.0), [])
    assert all(w["end"] - w["start"] <= 50.0 for w in wins)
    assert all(w["chapter_id"] == -1 for w in wins)


# ── retriever on a built lecture index ────────────────────────────────────────

def _make_lecture(root: Path) -> None:
    (root / "notes").mkdir(parents=True)
    (root / "transcripts").mkdir()
    (root / "merged_objects").mkdir()
    (root / "screenshots" / "selected").mkdir(parents=True)
    (root / "notes" / "chapter_1.md").write_text(
        "# Dynamic Programming\n\n## Overview\n\nDynamic programming solves problems by reusing subproblems.\n",
        encoding="utf-8")
    (root / "notes" / "lecture_outline.json").write_text(json.dumps(
        {"chapters": [{"chapter_id": 1, "title": "DP", "chunk_ids": [0]}]}), encoding="utf-8")
    (root / "merged_objects" / "chunk_0.json").write_text(json.dumps({"chunk_id": 0, "start": 0.0, "end": 100.0}))
    segs = [
        {"start": 0.0, "end": 5.0, "text": "Hi, my name is Sahil and I have solved 554 problems on LeetCode."},
        {"start": 5.0, "end": 10.0, "text": "Dynamic programming is the hardest topic in coding interviews."},
    ]
    (root / "transcripts" / "x.json").write_text(json.dumps({"segments": segs}), encoding="utf-8")
    (root / "screenshots" / "selected" / "chapter_1_screenshots.json").write_text(json.dumps({
        "chapter_id": 1,
        "screenshots": [{"path": "frames/frame_8.jpg", "reason": "Table of LIS lengths per index",
                         "section": "LIS", "importance": 9}],
    }), encoding="utf-8")


def test_build_index_and_retrieve_transcript_detail():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "lec"
        _make_lecture(root)
        emb = FakeEmbed()
        report = build_lecture_index(root, embed=emb)
        assert report["transcript"][0] >= 1 and report["notes"][0] == 1 and report["screenshot"][0] == 1
        again = build_lecture_index(root, embed=emb)
        assert all(a == 0 and r == 0 for a, r in again.values()), "re-index of unchanged content is a no-op"

        # Lean notes JSON gives each section a start time; re-indexing picks
        # it up for already-embedded docs without embedding them again.
        (root / "notes" / "chapter_1.json").write_text(json.dumps(
            {"chapter_id": 1, "sections": [{"title": "Overview", "start_sec": 3.0}]}), encoding="utf-8")
        calls = emb.calls
        build_lecture_index(root, embed=emb)
        assert emb.calls == calls, "metadata backfill embeds nothing"

        original = retriever._embed_query
        retriever._embed_query = _vec
        try:
            hits = retriever.retrieve("how many LeetCode problems has Sahil solved", output_dir=str(root))
            kinds = [h["kind"] for h in hits]
            assert kinds[0] == "transcript", "transcript windows come first"
            assert "notes" in kinds
            tx = hits[0]
            assert "554" in tx["text"] and tx["start"] == 0.0 and tx["chapter_id"] == 1
            notes_only = retriever.retrieve("dynamic programming", k=1, output_dir=str(root), kinds=("notes",))
            assert len(notes_only) == 1 and notes_only[0]["kind"] == "notes"
            assert notes_only[0]["start"] == 3.0, notes_only[0]

            imgs = retriever.retrieve_images("table of LIS lengths per index", output_dir=str(root), max_distance=0.5)
            assert imgs and imgs[0]["caption"].startswith("Table of LIS")
            assert retriever.retrieve_images("Sahil LeetCode", output_dir=str(root), max_distance=0.3) == [], \
                "unrelated screenshots are gated out"
        finally:
            retriever._embed_query = original


def test_missing_index_with_no_artifacts_raises():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            retriever.retrieve("q", output_dir=tmp)
        except retriever.IndexNotBuiltError:
            return
        raise AssertionError("expected IndexNotBuiltError")


def test_query_embedding_shared_between_lookups():
    calls = []
    original = retriever._qcache.copy()
    try:
        import tutor.embedding as emb_mod

        class _E:
            def __init__(self, role):
                pass

            def __call__(self, texts):
                calls.append(texts)
                return [_vec(t) for t in texts]

        real = emb_mod.GeminiEmbeddingFunction
        emb_mod.GeminiEmbeddingFunction = _E
        try:
            retriever._qcache.clear()
            retriever._embed_query("same question")
            retriever._embed_query("same question")
        finally:
            emb_mod.GeminiEmbeddingFunction = real
        assert len(calls) == 1
    finally:
        retriever._qcache.clear()
        retriever._qcache.update(original)


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
