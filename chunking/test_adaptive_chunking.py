"""
test_adaptive_chunking.py — Unit tests for adaptive chunk sizing (ROADMAP P1.8).

Long lectures grow the chunk size so extraction LLM calls stay bounded
(≤ TARGET_MAX_CHUNKS chunks, capped at MAX_SEGMENTS_PER_CHUNK). Short lectures
keep the default 15-segment chunks.

Run:
    python chunking/test_adaptive_chunking.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from chunking.chunk import (  # noqa: E402
    adaptive_segments_per_chunk,
    create_chunks,
    chunk_transcript,
)


def _segments(n):
    return [
        {
            "segment_id": i,
            "start": i * 10.0,
            "end": i * 10.0 + 9.0,
            "text": f"segment {i}",
        }
        for i in range(n)
    ]


def _write_transcript(n, path):
    data = {"source": {"video_id": "t", "title": "t", "source_type": "youtube", "duration": n * 10}, "segments": _segments(n)}
    path.write_text(__import__("json").dumps(data), encoding="utf-8")
    return path


def test_short_lecture_keeps_default():
    assert adaptive_segments_per_chunk(88) == config.DEFAULT_SEGMENTS_PER_CHUNK == 15
    assert adaptive_segments_per_chunk(config.TARGET_MAX_CHUNKS * 15) == 15
    print("PASS test_short_lecture_keeps_default")


def test_long_lecture_grows_chunk_size():
    # 3-hour lecture ≈ 1900 segments → spc = min(ceil(1900/24), 60) = 60
    spc = adaptive_segments_per_chunk(1900)
    assert spc == 60
    import math
    assert math.ceil(1900 / spc) <= 32  # bounded chunk count
    print("PASS test_long_lecture_grows_chunk_size")


def test_spc_respects_target_max_chunks():
    # At the cap, chunks must stay near TARGET_MAX_CHUNKS (24) for any size.
    import math
    for n in (500, 900, 1500, 2500, 4000):
        spc = adaptive_segments_per_chunk(n)
        assert spc <= config.MAX_SEGMENTS_PER_CHUNK
        # Default-sized chunks would have blown past the target; adaptive keeps
        # the count bounded (upper bound ~ n / min_spc + 1).
        assert math.ceil(n / spc) <= config.TARGET_MAX_CHUNKS or spc == config.MAX_SEGMENTS_PER_CHUNK
    print("PASS test_spc_respects_target_max_chunks")


def test_create_chunks_uses_adaptive_spc():
    segments = _segments(1000)  # would be 67 chunks at 15/chunk
    spc = adaptive_segments_per_chunk(len(segments))
    chunks = create_chunks(segments, segments_per_chunk=spc)
    assert len(chunks) < 50
    print(f"PASS test_create_chunks_uses_adaptive_spc (spc={spc}, {len(chunks)} chunks)")


def test_chunk_transcript_returns_spc(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        t = _write_transcript(1000, Path(tmp) / "t.json")
        res = chunk_transcript(str(t), output_dir=tmp)
        assert res["segments_per_chunk"] == adaptive_segments_per_chunk(1000)
        assert res["num_chunks"] < 50
    print("PASS test_chunk_transcript_returns_spc")


if __name__ == "__main__":
    test_short_lecture_keeps_default()
    test_long_lecture_grows_chunk_size()
    test_spc_respects_target_max_chunks()
    test_create_chunks_uses_adaptive_spc()
    test_chunk_transcript_returns_spc()
    print("\nAll tests passed.")
