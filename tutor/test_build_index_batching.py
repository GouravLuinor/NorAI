"""
test_build_index_batching.py — Unit tests for tutor/build_index.py batching
primitives (ROADMAP P1.2): deterministic chunk ids + batched upsert pacing.

No Chroma server, no API calls. Run:
    python tutor/test_build_index_batching.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.build_index import _make_chroma_id, upsert_batched  # noqa: E402


class FakeCollection:
    def __init__(self):
        self.upserts = []

    def upsert(self, ids=None, documents=None, metadatas=None):
        self.upserts.append(
            (list(ids), list(documents), list(metadatas) if metadatas else None)
        )


def test_make_chroma_id_deterministic_and_sanitised():
    chunk = {
        "chapter_id": 3,
        "heading_path": "Intro > Key Concepts",
        "heading": "Key Concepts",
        "text": "...",
    }
    assert _make_chroma_id(chunk, 0) == _make_chroma_id(chunk, 0)
    first = _make_chroma_id(chunk, 0)
    assert " " not in first
    assert " > " not in first
    assert first.startswith("ch3__")
    print("PASS test_make_chroma_id_deterministic_and_sanitised")


def test_upsert_batched_batches_by_size():
    col = FakeCollection()
    ids = [f"id{i}" for i in range(55)]
    docs = [f"doc{i}" for i in range(55)]
    metas = [{"i": i} for i in range(55)]
    n = upsert_batched(col, ids, docs, metas, batch_size=20, sleep_seconds=0)
    assert n == 55
    assert len(col.upserts) == 3  # 20 + 20 + 15
    assert col.upserts[0][0] == ids[:20]
    assert col.upserts[1][0] == ids[20:40]
    assert col.upserts[2][0] == ids[40:]
    assert col.upserts[2][1] == docs[40:]
    assert col.upserts[2][2] == metas[40:]
    print("PASS test_upsert_batched_batches_by_size")


def test_upsert_batched_sleeps_between_batches():
    col = FakeCollection()
    sleeps = []
    orig = time.sleep
    try:
        time.sleep = lambda s: sleeps.append(s)  # noqa: E731
        upsert_batched(
            col,
            [f"id{i}" for i in range(25)],
            [f"d{i}" for i in range(25)],
            batch_size=20,
            sleep_seconds=0.7,
        )
    finally:
        time.sleep = orig
    assert sleeps == [0.7], sleeps
    print("PASS test_upsert_batched_sleeps_between_batches")


def test_upsert_batched_empty_is_noop():
    col = FakeCollection()
    n = upsert_batched(col, [], [], [], batch_size=20, sleep_seconds=0)
    assert n == 0 and col.upserts == []
    print("PASS test_upsert_batched_empty_is_noop")


if __name__ == "__main__":
    test_make_chroma_id_deterministic_and_sanitised()
    test_upsert_batched_batches_by_size()
    test_upsert_batched_sleeps_between_batches()
    test_upsert_batched_empty_is_noop()
    print("\nAll tests passed.")
