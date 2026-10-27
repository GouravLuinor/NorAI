"""
backend/transcript.py — append-only chat transcript (what the UI displays).

Why this exists: the UI used to rebuild a thread's history from the LangGraph
checkpoint's `messages`, but that list is the tutor's *working memory* —
save_memory_node deletes summarised turns from it (RemoveMessage), and the
quiz/command nodes never record the user's turn at all. History therefore
shrank, reordered and lost user messages, and the client's content-based
merge papered over it by re-appending cached copies (duplicates).

The transcript is a separate table in the same per-lecture checkpoints
SQLite file, keyed by the client-supplied message id:

  * user turn       -> id = message_id
  * assistant turn  -> id = "ai-" + message_id

`UNIQUE(thread_id, message_id)` makes every write idempotent, so a retried or
double-submitted request can never create a second copy. Writes happen under
the per-lecture turn lock (see backend/dependencies.py), so `seq` order is the
true conversation order.

All functions are blocking sqlite3 calls — run them via asyncio.to_thread.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterable

_DDL = """
CREATE TABLE IF NOT EXISTS chat_transcript (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id  TEXT NOT NULL,
    message_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (thread_id, message_id)
)
"""


def assistant_id_for(message_id: str) -> str:
    return f"ai-{message_id}"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute(_DDL)
    return conn


def load(db_path: Path, thread_id: str) -> list[dict]:
    """Ordered transcript rows for a (scoped) thread; [] when none exist."""
    if not db_path.exists():
        return []
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT message_id, role, content FROM chat_transcript WHERE thread_id = ? ORDER BY seq",
            (thread_id,),
        ).fetchall()
    finally:
        conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2]} for r in rows]


def find_answer(db_path: Path, thread_id: str, message_id: str) -> str | None:
    """The stored assistant reply for a user message id, if that turn completed."""
    if not db_path.exists():
        return None
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT content FROM chat_transcript WHERE thread_id = ? AND message_id = ?",
            (thread_id, assistant_id_for(message_id)),
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def append_turn(
    db_path: Path,
    thread_id: str,
    message_id: str,
    question: str,
    answer: str,
    backfill: Iterable[tuple[str, str, str]] = (),
) -> None:
    """Record one completed turn (user + assistant) idempotently.

    `backfill` is the pre-turn history from the checkpoint, as
    (id, role, content) tuples. It is written only when this thread has no
    transcript yet, so threads created before the transcript existed keep
    their earlier messages.
    """
    now = time.time()
    conn = _connect(db_path)
    try:
        with conn:
            has_rows = conn.execute(
                "SELECT 1 FROM chat_transcript WHERE thread_id = ? LIMIT 1", (thread_id,)
            ).fetchone()
            if not has_rows:
                conn.executemany(
                    "INSERT OR IGNORE INTO chat_transcript (thread_id, message_id, role, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [(thread_id, mid, role, content, now) for mid, role, content in backfill],
                )
            conn.execute(
                "INSERT OR IGNORE INTO chat_transcript (thread_id, message_id, role, content, created_at) "
                "VALUES (?, ?, 'user', ?, ?)",
                (thread_id, message_id, question, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO chat_transcript (thread_id, message_id, role, content, created_at) "
                "VALUES (?, ?, 'assistant', ?, ?)",
                (thread_id, assistant_id_for(message_id), answer, now),
            )
    finally:
        conn.close()


def delete_thread(conn: sqlite3.Connection, thread_id: str) -> None:
    """Drop a thread's transcript inside the caller's delete transaction."""
    conn.execute(_DDL)
    conn.execute("DELETE FROM chat_transcript WHERE thread_id = ?", (thread_id,))
