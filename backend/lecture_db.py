"""
backend/lecture_db.py — lecture-scoped SQLite access for app-owned study state.

P5.1: extracted from main.py so domain routers (quiz, flashcards, threads,
content) share one connection helper and one set of lazy DDL migrations.
Lecture-scoped: quiz/flashcard persistence lands in the same DB as that
lecture's tutor checkpoints (outputs/{lecture_id}/tutor/). The global
'default' lecture keeps using the root CHECKPOINT_DB_PATH for backward
compatibility with the default tutor graph.
"""

import sqlite3
from contextlib import contextmanager

from tutor.config import CHECKPOINT_DB_PATH
from backend.dependencies import get_lecture_db_path


@contextmanager
def _db(lecture_id: str = "default"):
    """Yield a short-lived SQLite connection and commit/close on exit.

    Lecture-scoped: quiz/flashcard persistence lands in the same DB as that
    lecture's tutor checkpoints (outputs/{lecture_id}/tutor/). The global
    'default' lecture keeps using the root CHECKPOINT_DB_PATH for backward
    compatibility with the default tutor graph.
    """
    db_path = CHECKPOINT_DB_PATH if (not lecture_id or lecture_id == "default") else get_lecture_db_path(lecture_id)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_user_threads_table(conn: sqlite3.Connection) -> None:
    """Create the app-owned user_threads table if it doesn't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_threads "
        "(thread_id TEXT PRIMARY KEY, created_at INTEGER DEFAULT (strftime('%s','now')))"
    )


def _ensure_quiz_attempts_table(conn: sqlite3.Connection) -> None:
    """Create the quiz_attempts table if it doesn't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS quiz_attempts ("
        "id TEXT PRIMARY KEY, "
        "user_id TEXT, "
        "lecture_id TEXT, "
        "chapter_id INTEGER, "
        "difficulty TEXT, "
        "started_at TEXT, "
        "finished_at TEXT, "
        "questions_json TEXT, "
        "answers_json TEXT, "
        "confidences_json TEXT, "
        "evaluation_json TEXT, "
        "score REAL, "
        "total INTEGER"
        ")"
    )
    _ensure_quiz_attempts_user_id(conn)


def _ensure_quiz_attempts_user_id(conn: sqlite3.Connection) -> None:
    """P1.7: add the user_id column lazily (pre-existing DBs).

    Rows created before this migration keep user_id NULL and become
    read-invisible under strict scoping — accepted tradeoff (regenerable
    study state).
    """
    try:
        conn.execute("ALTER TABLE quiz_attempts ADD COLUMN user_id TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists


def _ensure_quiz_attempts_correct_ids(conn: sqlite3.Connection) -> None:
    """Add the correct_ids_json column to quiz_attempts if it's missing.

    Migration-friendly: older DBs created before this column existed won't
    get it from CREATE TABLE IF NOT EXISTS, so we ALTER lazily and swallow
    the duplicate-column error.
    """
    try:
        conn.execute("ALTER TABLE quiz_attempts ADD COLUMN correct_ids_json TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists


FLASHCARD_RATINGS_DDL = (
    "CREATE TABLE IF NOT EXISTS {name} ("
    "user_id TEXT NOT NULL DEFAULT '', "
    "lecture_id TEXT, "
    "chapter_id INTEGER, "
    "card_key TEXT, "
    "rating TEXT, "
    "updated_at TEXT, "
    "easiness REAL, "
    "reps INTEGER, "
    "interval_days INTEGER, "
    "due_at TEXT, "
    "last_reviewed_at TEXT, "
    "PRIMARY KEY (user_id, lecture_id, chapter_id, card_key)"
    ")"
)


def _ensure_flashcard_ratings_table(conn: sqlite3.Connection) -> None:
    """Create the flashcard_ratings table if it doesn't exist.

    P1.7: user_id joined the PRIMARY KEY, which SQLite can't ALTER in place.
    Legacy tables (no user_id column) are rebuilt in place: rows carry over
    with user_id='' and become read-invisible under strict per-user scoping —
    accepted tradeoff, ratings are regenerable study state.
    """
    conn.execute(FLASHCARD_RATINGS_DDL.format(name="flashcard_ratings"))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(flashcard_ratings)")}
    if "user_id" not in cols:
        _ensure_flashcard_schedule_columns(conn)
        conn.execute("ALTER TABLE flashcard_ratings RENAME TO flashcard_ratings_old")
        conn.execute(FLASHCARD_RATINGS_DDL.format(name="flashcard_ratings"))
        conn.execute(
            "INSERT INTO flashcard_ratings "
            "(user_id, lecture_id, chapter_id, card_key, rating, updated_at, "
            " easiness, reps, interval_days, due_at, last_reviewed_at) "
            "SELECT '', lecture_id, chapter_id, card_key, rating, updated_at, "
            " easiness, reps, interval_days, due_at, last_reviewed_at "
            "FROM flashcard_ratings_old"
        )
        conn.execute("DROP TABLE flashcard_ratings_old")
    _ensure_flashcard_schedule_columns(conn)


def _ensure_flashcard_schedule_columns(conn: sqlite3.Connection) -> None:
    """Lazily add the SM-2 schedule columns (P6.2) to flashcard_ratings.

    Migration-friendly: the base table is created *without* these columns in
    older DBs, so we ALTER once and swallow the duplicate-column error — the
    same lazy-migrate pattern as `_ensure_quiz_attempts_correct_ids`.
    """
    for col, ddl in (
        ("easiness", "REAL"),
        ("reps", "INTEGER"),
        ("interval_days", "INTEGER"),
        ("due_at", "TEXT"),
        ("last_reviewed_at", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE flashcard_ratings ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # column already exists
