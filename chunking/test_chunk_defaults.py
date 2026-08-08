"""
test_chunk_defaults.py — Unit tests for the chunk-size default (ROADMAP P1.1).

Guards against the regression where a local constant of 5 silently overrode
config's DEFAULT_SEGMENTS_PER_CHUNK (15), tripling extraction LLM calls.

Run:
    python chunking/test_chunk_defaults.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from chunking.chunk import DEFAULT_SEGMENTS_PER_CHUNK, create_chunks  # noqa: E402


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


def test_module_default_equals_config():
    assert DEFAULT_SEGMENTS_PER_CHUNK == config.DEFAULT_SEGMENTS_PER_CHUNK == 15
    print("PASS test_module_default_equals_config")


def test_default_grouping_is_15_per_chunk():
    chunks = create_chunks(_segments(40))
    assert len(chunks) == 3  # 15 + 15 + 10
    assert [c["num_segments"] for c in chunks] == [15, 15, 10]
    print("PASS test_default_grouping_is_15_per_chunk")


def test_override_still_supported():
    chunks = create_chunks(_segments(40), segments_per_chunk=5)
    assert len(chunks) == 8
    assert [c["num_segments"] for c in chunks] == [5] * 8
    print("PASS test_override_still_supported")


if __name__ == "__main__":
    test_module_default_equals_config()
    test_default_grouping_is_15_per_chunk()
    test_override_still_supported()
    print("\nAll tests passed.")
