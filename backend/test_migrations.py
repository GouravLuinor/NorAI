#!/usr/bin/env python3
"""P4.3 — Alembic migration smoke tests (standalone, no pytest).

Run directly:  venv/bin/python backend/test_migrations.py

Covers:
  1. fresh DB        -> `upgrade head` creates every table + the P4.1 pipeline columns
  2. pre-Alembic DB  -> a DB built by the old `create_all` is absorbed (no error),
                       stamped at head, and gains the new pipeline columns
  3. idempotency     -> `upgrade head` on an already-migrated DB is a no-op
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_TMP = tempfile.mkdtemp(prefix="norai_mig_")
_FRESH_DB = str(Path(_TMP) / "fresh.db")
_LEGACY_DB = str(Path(_TMP) / "legacy.db")

# database.py resolves DATABASE_URL at import; point it at a throwaway DB.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_FRESH_DB}"
# env.py's get_url() honors NORAI_ALEMBIC_URL, letting tests swap DBs without
# re-importing the module graph.
os.environ["NORAI_ALEMBIC_URL"] = f"sqlite+aiosqlite:///{_FRESH_DB}"

from backend.db.migrate import run_migrations  # noqa: E402

TABLES = {"users", "subscriptions", "lectures", "usage_logs", "webhook_events"}
PIPELINE_COLUMNS = {
    "stage", "stage_message", "progress", "attempts",
    "heartbeat_at", "queued_at", "started_at", "cancel_requested",
}
# P6.5: cost-dashboard columns added to usage_logs.
USAGE_COLUMNS = {"model", "calls"}
# P6.4: courses + share links.
COURSE_TABLES = {"courses", "course_lectures", "share_links"}


def _conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _table_names(db_path: str) -> set:
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {r[0] for r in rows}


def _column_names(db_path: str, table: str) -> set:
    with _conn(db_path) as c:
        rows = c.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


_MIG_HEAD = "0004_courses_and_shares"


def _version(db_path: str):
    with _conn(db_path) as c:
        return c.execute("SELECT version_num FROM alembic_version").fetchone()


passed = 0
failed = 0


def check(name: str, cond: bool):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name}")


# ── 1. Fresh DB ──────────────────────────────────────────────────────────────
run_migrations()
check("fresh: all tables created", TABLES <= _table_names(_FRESH_DB))
check(
    "fresh: alembic_version at head",
    _version(_FRESH_DB) == (_MIG_HEAD,),
)
check(
    "fresh: lectures has pipeline columns",
    PIPELINE_COLUMNS <= _column_names(_FRESH_DB, "lectures"),
)
check(
    "fresh: lectures has original columns",
    {"id", "user_id", "title", "status", "output_dir", "error_message"}
    <= _column_names(_FRESH_DB, "lectures"),
)
check(
    "fresh: subscriptions.unique user_id",
    len([i for i in _conn(_FRESH_DB).execute("PRAGMA index_list(subscriptions)").fetchall() if i[1] == "sqlite_autoindex_subscriptions_1"]) == 1,
)
check(
    "fresh: users.email unique index present",
    "ix_users_email" in _table_names(_FRESH_DB) or "ix_users_email" in {
        r[1] for r in _conn(_FRESH_DB).execute("SELECT type,name FROM sqlite_master WHERE type='index'").fetchall()
    },
)
check(
    "fresh: usage_logs has P6.5 columns",
    USAGE_COLUMNS <= _column_names(_FRESH_DB, "usage_logs"),
)
check(
    "fresh: P6.4 course tables created",
    COURSE_TABLES <= _table_names(_FRESH_DB),
)
check(
    "fresh: share_links columns",
    {"id", "lecture_id", "created_by", "allow_tutor_chat", "expires_at"}
    <= _column_names(_FRESH_DB, "share_links"),
)
check(
    "fresh: course_lectures PK columns",
    {"course_id", "lecture_id", "position"} <= _column_names(_FRESH_DB, "course_lectures"),
)

# ── 2. Pre-Alembic DB (old create_all schema) ───────────────────────────────
with _conn(_LEGACY_DB) as c:
    c.execute(
        """CREATE TABLE lectures (
            id VARCHAR(128) NOT NULL PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL,
            title VARCHAR(512) NOT NULL,
            source_type VARCHAR(32) NOT NULL,
            source_url TEXT,
            duration_seconds INTEGER NOT NULL,
            status VARCHAR(32) NOT NULL,
            output_dir VARCHAR(512),
            error_message TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )"""
    )
    c.execute("INSERT INTO lectures (id, user_id, title, source_type, duration_seconds, status, created_at, updated_at) VALUES ('legacy-1', 'u1', 'Old', 'upload', 60, 'processing', '2026-01-01', '2026-01-01')")

os.environ["NORAI_ALEMBIC_URL"] = f"sqlite+aiosqlite:///{_LEGACY_DB}"
run_migrations()

check("legacy: absorbed without error", "lectures" in _table_names(_LEGACY_DB))
check(
    "legacy: alembic_version stamped at head",
    _version(_LEGACY_DB) == (_MIG_HEAD,),
)
check(
    "legacy: pipeline columns added",
    PIPELINE_COLUMNS <= _column_names(_LEGACY_DB, "lectures"),
)
check(
    "legacy: usage_logs gained P6.5 columns",
    USAGE_COLUMNS <= _column_names(_LEGACY_DB, "usage_logs"),
)
check(
    "legacy: P6.4 course tables added",
    COURSE_TABLES <= _table_names(_LEGACY_DB),
)
with _conn(_LEGACY_DB) as c:
    row = c.execute("SELECT attempts, cancel_requested FROM lectures WHERE id='legacy-1'").fetchone()
check(
    "legacy: existing row backfilled (attempts=0, cancel_requested=0)",
    row == (0, 0),
)

# ── 3. Idempotency ───────────────────────────────────────────────────────────
run_migrations()  # again
check("idempotent: re-upgrade is a no-op", True)
check(
    "idempotent: columns intact after re-upgrade",
    PIPELINE_COLUMNS <= _column_names(_LEGACY_DB, "lectures"),
)
check(
    "idempotent: P6.5 usage columns intact",
    USAGE_COLUMNS <= _column_names(_LEGACY_DB, "usage_logs"),
)
check(
    "idempotent: P6.4 course tables intact",
    COURSE_TABLES <= _table_names(_LEGACY_DB),
)
check(
    "idempotent: only one alembic_version row",
    len(_conn(_LEGACY_DB).execute("SELECT * FROM alembic_version").fetchall()) == 1,
)

print(f"\n{passed} checks passed, {failed} failed")
sys.exit(1 if failed else 0)
