"""
test_quiz_missed.py — Unit tests for the deterministic "Review Missed"
logic (backend.main._compute_missed_ids).

No API calls, no DB. Fully runnable offline.

Run:
    python -m pytest backend/test_quiz_missed.py -v
    # or without pytest:
    python backend/test_quiz_missed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.routers.quiz import _compute_missed_ids  # noqa: E402


def _q(qid, qtype, answer, user_answer=""):
    return {
        "id": qid,
        "type": qtype,
        "question": "q",
        "answer": answer,
        "user_answer": user_answer,
    }


def _ans(qid, user_answer):
    return {"id": qid, "user_answer": user_answer}


def _fb(number, remark):
    return {"question_number": number, "remark": remark}


# ── MCQ / True-False: authoritative equality ─────────────────────────────────

def test_mcq_equality():
    questions = [_q(1, "MCQ", "Paris"), _q(2, "MCQ", "Paris")]
    answers = [_ans(1, "Paris"), _ans(2, "london")]
    missed = _compute_missed_ids(questions, answers, {})
    assert missed == ["2"]  # case-insensitive, so "london" vs "London" matches


def test_mcq_empty_answer_is_missed():
    questions = [_q(1, "MCQ", "Paris")]
    answers = [_ans(1, "")]
    assert _compute_missed_ids(questions, answers, {}) == ["1"]


# ── Free-text: remark-driven, no false positives from "correct answer is" ────

def test_free_text_incorrect_remark_is_missed():
    """The old bug: 'Incorrect. The correct answer is X' contains 'correct'."""
    questions = [_q(1, "Short Answer", "X")]
    answers = [_ans(1, "Y")]
    evaluation = {"per_question_feedback": [_fb(1, "Incorrect. The correct answer is X.")]}
    assert _compute_missed_ids(questions, answers, evaluation) == ["1"]


def test_free_text_wrong_remark_is_missed():
    questions = [_q(1, "Conceptual", "X")]
    answers = [_ans(1, "Y")]
    evaluation = {"per_question_feedback": [_fb(1, "Your answer is wrong. The correct answer is X.")]}
    assert _compute_missed_ids(questions, answers, evaluation) == ["1"]


def test_free_text_qualifier_remark_is_missed():
    """'Good effort, though the correct answer is X' — positive word + qualifier."""
    questions = [_q(1, "Short Answer", "X")]
    answers = [_ans(1, "Y")]
    evaluation = {"per_question_feedback": [_fb(1, "Good effort, though the correct answer is X.")]}
    assert _compute_missed_ids(questions, answers, evaluation) == ["1"]


def test_free_text_positive_remark_is_correct():
    questions = [_q(1, "Short Answer", "X")]
    answers = [_ans(1, "X")]
    evaluation = {"per_question_feedback": [_fb(1, "Correct! You clearly understand this.")]}
    assert _compute_missed_ids(questions, answers, evaluation) == []


def test_free_text_missing_remark_defaults_to_missed():
    """No feedback for the question → default to including it in review."""
    questions = [_q(1, "Short Answer", "X"), _q(2, "Short Answer", "X")]
    answers = [_ans(1, "X"), _ans(2, "Y")]
    evaluation = {"per_question_feedback": []}
    assert _compute_missed_ids(questions, answers, evaluation) == ["1", "2"]


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
