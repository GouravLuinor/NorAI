"""Pure SM-2 spaced-repetition scheduler for flashcard decks (P6.2).

Zero LLM calls, deterministic, fully offline — given a card's previous
scheduling state and the user's rating (Again/Hard/Good/Easy), `apply_sm2`
returns the next state: easiness factor (EF), repetition count, interval in
days and the next due date.

Follows the classic SM-2 recurrence with the 4-grade Anki-style encoding:

    Again→1 (reps reset, 1 day)   Hard→3   Good→4   Easy→5

    EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))   (floor 1.3, q >= 3)
    I(1) = 1, I(2) = 6, I(n) = round(I(n-1) * EF')

State lives per (lecture, chapter, card_key) in the per-lecture SQLite DB
(see backend.main `_ensure_flashcard_ratings_table`). All functions are pure
so the scheduler is unit-testable without any API/DB.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

#: Anki-style quality encoding of the UI's four rating buttons.
QUALITY_BY_RATING = {
    "Again": 1,
    "Hard": 3,
    "Good": 4,
    "Easy": 5,
}

DEFAULT_EASINESS = 2.5
MIN_EASINESS = 1.3
RESET_INTERVAL_DAYS = 1
FIRST_SUCCESS_INTERVAL_DAYS = 1
SECOND_SUCCESS_INTERVAL_DAYS = 6

#: Serialized columns on the flashcard_ratings row, in insertion order.
SCHEDULE_COLUMNS = (
    "easiness",
    "reps",
    "interval_days",
    "due_at",
    "last_reviewed_at",
)


def new_state() -> dict:
    """Default scheduling state for a never-reviewed card."""
    return {
        "easiness": DEFAULT_EASINESS,
        "reps": 0,
        "interval_days": 0,
        "due_at": "",
        "last_reviewed_at": "",
    }


def rating_to_quality(rating: str) -> int:
    """Map a UI rating label to its SM-2 quality score (1..5)."""
    try:
        return QUALITY_BY_RATING[rating]
    except KeyError:
        raise ValueError(f"Unknown flashcard rating: {rating!r}") from None

def round_review_interval(prev_interval_days: int, easiness: float, reps: int) -> int:
    """Next review interval after a success: fixed first two ladders, then EF-scaled.

    ``reps`` is the *new* repetition count (successes incl. the one just rated):
    1st success → 1 day, 2nd → 6 days, later → round(prev * EF).
    """
    if reps <= 1:
        return FIRST_SUCCESS_INTERVAL_DAYS
    if reps == 2:
        return SECOND_SUCCESS_INTERVAL_DAYS
    return max(FIRST_SUCCESS_INTERVAL_DAYS, round(prev_interval_days * easiness))


def updated_easiness(easiness: float, quality: int) -> float:
    """SM-2 easiness-factor update (called only for q >= 3)."""
    if quality < 3:
        return max(MIN_EASINESS, easiness)
    nf = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return max(MIN_EASINESS, nf)


def _date_str(d: _dt.date) -> str:
    return d.isoformat()


def apply_sm2(
    rating: str,
    state: Optional[dict] = None,
    today: Optional[_dt.date] = None,
    reviewed_at: Optional[str] = None,
) -> dict:
    """Return the new scheduling state for a card reviewed with ``rating``.

    ``state`` is the previous state (defaults to a fresh new card). ``today``
    pins the reference date for deterministic tests. ``reviewed_at`` is
    optional; defaults to ``today`` as an ISO date-time in UTC.
    """
    quality = rating_to_quality(rating)
    cur = dict(state or new_state())
    easiness = float(cur.get("easiness") or DEFAULT_EASINESS)
    reps = int(cur.get("reps") or 0)
    prev_interval = int(cur.get("interval_days") or 0)
    today = today or _dt.date.today()

    if quality < 3:
        # Again: back to learning, review tomorrow, EF untouched.
        next_state = {
            "easiness": easiness,
            "reps": 0,
            "interval_days": RESET_INTERVAL_DAYS,
            "due_at": _date_str(today + _dt.timedelta(days=RESET_INTERVAL_DAYS)),
        }
    else:
        new_ef = updated_easiness(easiness, quality)
        new_reps = reps + 1
        interval = round_review_interval(prev_interval, new_ef, new_reps)
        next_state = {
            "easiness": round(new_ef, 4),
            "reps": new_reps,
            "interval_days": interval,
            "due_at": _date_str(today + _dt.timedelta(days=interval)),
        }

    if reviewed_at is None:
        reviewed_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    next_state["last_reviewed_at"] = reviewed_at
    return next_state


def is_due(state: dict, today: Optional[_dt.date] = None) -> bool:
    """True when the card's due date has arrived (or it was never reviewed)."""
    today = today or _dt.date.today()
    due_raw = (state or {}).get("due_at") or ""
    if not due_raw:
        return True  # brand-new card
    try:
        due = _dt.date.fromisoformat(due_raw)
    except ValueError:
        return True
    return due <= today


def due_in_days(state: dict, today: Optional[_dt.date] = None) -> int:
    """Signed day offset to the next review (<=0 → overdue/due now)."""
    today = today or _dt.date.today()
    due_raw = (state or {}).get("due_at") or ""
    if not due_raw:
        return 0
    try:
        due = _dt.date.fromisoformat(due_raw)
    except ValueError:
        return 0
    return (due - today).days