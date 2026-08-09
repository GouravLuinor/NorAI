"""Standalone tests for P3.5 cross-turn chapter state (detect_chapter_node).

Run directly:  venv/bin/python tutor/test_chapter_tracking.py
No LLM calls, no network. Pure logic tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor.nodes_retrieval import detect_chapter_node, _extract_chapter_id, _is_anaphoric


def _run(question: str, last_chapter_id=None):
    state = {"user_question": question}
    if last_chapter_id is not None:
        state["last_chapter_id"] = last_chapter_id
    return detect_chapter_node(state, {})


def test_extract_chapter_explicit():
    assert _extract_chapter_id("Explain chapter 3 again") == 3
    assert _extract_chapter_id("What was in ch5?") == 5
    assert _extract_chapter_id("Tell me about the second chapter") == 2
    assert _extract_chapter_id("What is a stack?") is None


def test_explicit_sets_both_and_remembers():
    r = _run("Explain chapter 3")
    assert r["chapter_id"] == 3
    assert r["last_chapter_id"] == 3


def test_anaphoric_followup_reuses_last_chapter():
    # After ch3 was mentioned, a follow-up stays scoped to ch3.
    r = _run("what about that?", last_chapter_id=3)
    assert r["chapter_id"] == 3
    # last_chapter_id must NOT be overwritten by the follow-up turn
    assert "last_chapter_id" not in r


def test_fresh_question_goes_full_index():
    # A new topical question without anaphora must not inherit the chapter.
    r = _run("What is a red-black tree?", last_chapter_id=3)
    assert r["chapter_id"] is None
    assert "last_chapter_id" not in r


def test_new_question_after_explicit_ref_pivots_chapter():
    # User moves to a new chapter explicitly: chapter_id switches, last updates.
    r = _run("Now chapter 7 please", last_chapter_id=3)
    assert r["chapter_id"] == 7
    assert r["last_chapter_id"] == 7


def test_anaphora_classifier():
    for q in [
        "what about that?",
        "how about this?",
        "explain that",
        "why is that?",
        "can you clarify that?",
        "tell me more",
        "what does it mean?",
    ]:
        assert _is_anaphoric(q), f"expected anaphoric: {q!r}"
    for q in [
        "What is a red-black tree?",
        "Define NP-hard problems.",
        "hi",
        "thanks",
        "Give me a summary.",
    ]:
        assert not _is_anaphoric(q), f"expected NOT anaphoric: {q!r}"


def test_quiz_command_with_remembered_chapter():
    # "quiz" is not anaphoric → full-lecture quiz unless chapter named explicitly.
    r = _run("give me a quiz", last_chapter_id=3)
    assert r["is_command"] is True
    assert r["command_type"] == "quiz"
    assert r["chapter_id"] is None


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
