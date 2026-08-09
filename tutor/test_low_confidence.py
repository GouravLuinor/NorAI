"""Standalone tests for P3.7 graceful low-context handling.

Run directly:  venv/bin/python tutor/test_low_confidence.py
Retrieve-node tests mock tutor.nodes_retrieval.retrieve (no Chroma/network);
context-block tests are pure string checks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor.prompts import (
    _CONTEXT_HEADER,
    _LOW_CONFIDENCE_NOTE,
    _NO_CONTEXT_NOTE,
    _RETRIEVAL_ERROR_NOTE,
    build_context_block,
)
from tutor.nodes_retrieval import retrieve_node


def _chunks(*distances):
    return [
        {"chunk_id": f"c{i}", "heading": f"H{i}", "text": f"text {i}", "distance": d}
        for i, d in enumerate(distances)
    ]


# ── build_context_block statuses ──────────────────────────────────────────────

def test_ok_chunks_use_standard_header():
    block = build_context_block(_chunks(0.1, 0.2))
    assert _CONTEXT_HEADER in block
    assert _LOW_CONFIDENCE_NOTE not in block
    assert _RETRIEVAL_ERROR_NOTE not in block


def test_low_confidence_uses_disclaimer():
    block = build_context_block(_chunks(0.9, 0.8), low_confidence=True)
    assert _LOW_CONFIDENCE_NOTE in block


def test_empty_uses_no_context_note():
    block = build_context_block([], status="ok")
    assert _NO_CONTEXT_NOTE in block
    assert _RETRIEVAL_ERROR_NOTE not in block


def test_error_empty_uses_error_note_not_no_context():
    block = build_context_block([], status="error")
    assert _RETRIEVAL_ERROR_NOTE in block
    assert _NO_CONTEXT_NOTE not in block


def test_error_with_chunks_uses_error_note():
    block = build_context_block(_chunks(0.1, 0.2), status="error")
    assert _RETRIEVAL_ERROR_NOTE in block
    assert _CONTEXT_HEADER not in block


# ── retrieve_node status + confidence tags (mocked retriever) ─────────────────

def _mock_retrieve(chunks):
    import tutor.nodes_retrieval as nr
    original = nr.retrieve
    nr.retrieve = lambda query, chapter_id=None, k=4, output_dir=None: chunks
    return original


def test_retrieve_ok_tags_strong_and_weak():
    original = _mock_retrieve(_chunks(0.2, 0.6))
    import tutor.nodes_retrieval as nr
    try:
        out = retrieve_node(
            {"user_question": "q", "search_query": "q"}, {"configurable": {}}
        )
    finally:
        nr.retrieve = original
    assert out["retrieval_status"] == "ok"
    tags = [c["confidence_tag"] for c in out["retrieved_chunks"]]
    assert tags == ["strong", "weak"]


def test_retrieve_empty_status():
    original = _mock_retrieve([])
    import tutor.nodes_retrieval as nr
    try:
        out = retrieve_node(
            {"user_question": "q", "search_query": "q"}, {"configurable": {}}
        )
    finally:
        nr.retrieve = original
    assert out["retrieval_status"] == "empty"
    assert out["retrieved_chunks"] == []


def test_retrieve_error_status():
    import tutor.nodes_retrieval as nr
    original = nr.retrieve

    def boom(query, chapter_id=None, k=4, output_dir=None):
        raise nr.IndexNotBuiltError("no index")
    nr.retrieve = boom
    try:
        out = retrieve_node(
            {"user_question": "q", "search_query": "q"}, {"configurable": {}}
        )
    finally:
        nr.retrieve = original
    assert out["retrieval_status"] == "error"
    assert out["retrieved_chunks"] == []


def test_retrieve_missing_question_is_empty():
    out = retrieve_node({"user_question": ""}, {"configurable": {}})
    assert out["retrieval_status"] == "empty"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    sys.exit(main())
