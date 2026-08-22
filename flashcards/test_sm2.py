"""
test_sm2.py — Unit tests for the SM-2 spaced-repetition scheduler (P6.2).

Covers every rating path, the easiness-factor recurrence and its 1.3 floor,
the 1 → 6 → EF interval ladder, due-date arithmetic, and the on-disk
round-trip through the same `flashcard_ratings` schema the backend uses.

Run:
    python flashcards/test_sm2.py
"""

from __future__ import annotations

import datetime
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flashcards.sm2 import (  # noqa: E402
    apply_sm2,
    due_in_days,
    is_due,
    new_state,
    rating_to_quality,
    DEFAULT_EASINESS,
    MIN_EASINESS,
)

TODAY = datetime.date(2026, 8, 12)


def test_rating_to_quality_mapping():
    assert rating_to_quality("Again") == 1
    assert rating_to_quality("Hard") == 3
    assert rating_to_quality("Good") == 4
    assert rating_to_quality("Easy") == 5
    try:
        rating_to_quality("Fast")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown rating should raise ValueError")
    print("PASS test_rating_to_quality_mapping")


def test_new_state_defaults():
    s = new_state()
    assert s["easiness"] == DEFAULT_EASINESS
    assert s["reps"] == 0
    assert s["interval_days"] == 0
    assert s["due_at"] == ""
    print("PASS test_new_state_defaults")


def test_again_resets_to_learning():
    built = {
        "easiness": 2.5, "reps": 4, "interval_days": 15,
        "due_at": "2026-08-27", "last_reviewed_at": "",
    }
    s = apply_sm2("Again", state=built, today=TODAY, reviewed_at="2026-08-12T00:00:00Z")
    assert s["reps"] == 0
    assert s["interval_days"] == 1
    assert s["due_at"] == "2026-08-13"
    assert s["easiness"] == 2.5  # EF untouched on failure
    print("PASS test_again_resets_to_learning")


def test_first_good_schedules_tomorrow():
    s = apply_sm2("Good", state=None, today=TODAY)
    assert s["reps"] == 1
    assert s["interval_days"] == 1
    assert s["due_at"] == "2026-08-13"
    assert s["easiness"] == DEFAULT_EASINESS  # q=4 leaves EF unchanged
    print("PASS test_first_good_schedules_tomorrow")


def test_interval_ladder_1_6_then_ef():
    # Good × 3: 1 day, then 6 days, then round(6 * 2.5) = 15
    s = apply_sm2("Good", today=TODAY)
    s = apply_sm2("Good", state=s, today=TODAY + datetime.timedelta(days=1))
    assert s["reps"] == 2 and s["interval_days"] == 6
    s = apply_sm2("Good", state=s, today=TODAY + datetime.timedelta(days=7))
    assert s["reps"] == 3 and s["interval_days"] == 15
    assert s["due_at"] == "2026-09-03"  # reviewed 08-19 (+7d), interval 15
    print("PASS test_interval_ladder_1_6_then_ef")


def test_easy_raises_easiness():
    s = apply_sm2("Easy", today=TODAY)
    assert s["easiness"] == round(DEFAULT_EASINESS + 0.1, 4)  # 2.6
    s = apply_sm2("Easy", state=s, today=TODAY + datetime.timedelta(days=1))
    assert s["reps"] == 2 and s["interval_days"] == 6
    assert s["easiness"] == round(2.7, 4)
    s = apply_sm2("Easy", state=s, today=TODAY + datetime.timedelta(days=7))
    assert s["reps"] == 3 and s["interval_days"] == round(6 * 2.8)  # 17 (uses updated EF)
    assert s["easiness"] == 2.8
    print("PASS test_easy_raises_easiness")


def test_hard_lowers_easiness():
    s = apply_sm2("Hard", today=TODAY)
    assert s["easiness"] == round(DEFAULT_EASINESS - 0.14, 4)  # 2.36
    print("PASS test_hard_lowers_easiness")


def test_easiness_floor():
    base = {"easiness": MIN_EASINESS, "reps": 5, "interval_days": 100, "due_at": "2026-12-01", "last_reviewed_at": ""}
    s = apply_sm2("Hard", state=base, today=TODAY)
    assert s["easiness"] == MIN_EASINESS  # floor clamps 1.16 → 1.3
    print("PASS test_easiness_floor")


def test_is_due_and_due_in_days():
    empty = new_state()
    assert is_due(empty, today=TODAY) is True
    assert due_in_days(empty, today=TODAY) == 0

    due_today = {"due_at": "2026-08-12"}
    assert is_due(due_today, today=TODAY) is True
    assert due_in_days(due_today, today=TODAY) == 0

    due_future = {"due_at": "2026-08-15"}
    assert is_due(due_future, today=TODAY) is False
    assert due_in_days(due_future, today=TODAY) == 3

    due_past = {"due_at": "2026-08-01"}
    assert is_due(due_past, today=TODAY) is True
    assert due_in_days(due_past, today=TODAY) == -11

    assert is_due({"due_at": "garbage"}, today=TODAY) is True
    print("PASS test_is_due_and_due_in_days")


def test_apply_sm2_does_not_mutate_input():
    before = {"easiness": 2.5, "reps": 2, "interval_days": 6, "due_at": "2026-08-18", "last_reviewed_at": ""}
    snapshot = dict(before)
    apply_sm2("Good", state=before, today=TODAY)
    assert before == snapshot
    print("PASS test_apply_sm2_does_not_mutate_input")


def test_db_round_trip_through_real_schema():
    """Persist SM-2 state through the exact backend DDL (incl. lazy ALTER)."""
    from backend.lecture_db import _ensure_flashcard_ratings_table

    with tempfile.TemporaryDirectory() as tmp:
        conn = sqlite3.connect(Path(tmp) / "ck.sqlite")
        _ensure_flashcard_ratings_table(conn)  # create + lazy schedule columns
        _ensure_flashcard_ratings_table(conn)  # idempotent (2nd run skips ALTER)

        key, lecture, chapter = "abcd1234", "lect-A", 1
        s = apply_sm2("Good", state=None, today=TODAY, reviewed_at="2026-08-12T00:00:00Z")
        conn.execute(
            "INSERT INTO flashcard_ratings (lecture_id, chapter_id, card_key, rating, updated_at, "
            " easiness, reps, interval_days, due_at, last_reviewed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lecture, chapter, key, "Good", "2026-08-12T00:00:00Z",
             s["easiness"], s["reps"], s["interval_days"], s["due_at"], s["last_reviewed_at"]),
        )
        conn.commit()

        row = conn.execute(
            "SELECT easiness, reps, interval_days, due_at, last_reviewed_at "
            "FROM flashcard_ratings WHERE lecture_id=? AND card_key=?",
            (lecture, key),
        ).fetchone()
        assert row == (2.5, 1, 1, "2026-08-13", "2026-08-12T00:00:00Z")
        conn.close()
    print("PASS test_db_round_trip_through_real_schema")


if __name__ == "__main__":
    test_rating_to_quality_mapping()
    test_new_state_defaults()
    test_again_resets_to_learning()
    test_first_good_schedules_tomorrow()
    test_interval_ladder_1_6_then_ef()
    test_easy_raises_easiness()
    test_hard_lowers_easiness()
    test_easiness_floor()
    test_is_due_and_due_in_days()
    test_apply_sm2_does_not_mutate_input()
    test_db_round_trip_through_real_schema()
    print("\nAll tests passed.")