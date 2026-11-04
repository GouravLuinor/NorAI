"""
backend/db/database.py

SQLAlchemy 2.0 Async engine and session management for NorAI.
Supports PostgreSQL (Supabase / Production) and fallback to SQLite (local dev).
"""

import logging
import os
from typing import Any, AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Ensure .env vars (DATABASE_URL, etc.) are loaded when this module is imported standalone.
load_dotenv()

logger = logging.getLogger("norai")

# Base class for ORM models
Base = declarative_base()

# Retrieve database URL from environment or default to local sqlite
DEFAULT_SQLITE_URL = "sqlite+aiosqlite:///outputs/norai_main.db"


def _normalize_db_url(url: str) -> str:
    """Make any postgres URL work with the asyncpg driver.

    * Forces the async driver for `postgres://` and `postgresql://` URLs.
    * Strips `sslmode=` and `pgbouncer=true` query params: the Supabase pooler
      connection strings ship both, but asyncpg has no `sslmode` kwarg and
      SQLAlchemy forwards URL query params verbatim to asyncpg.connect() — an
      unknown kwarg raises TypeError on every connect (asyncpg 0.31). asyncpg
      negotiates SSL opportunistically on its own, so dropping them is safe.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        qs = parse_qsl(parts.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in qs if k.lower() not in ("sslmode", "pgbouncer")]
        if len(filtered) != len(qs):
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(filtered), parts.fragment))
    return url


DATABASE_URL = _normalize_db_url(
    os.environ.get("DATABASE_URL") or os.environ.get("NORAI_POSTGRES_URL") or DEFAULT_SQLITE_URL
)

if DATABASE_URL == DEFAULT_SQLITE_URL:
    env = os.environ.get("NORAI_ENV", "development").strip()
    if env not in ("", "development"):
        logger.warning(
            "DATABASE_URL is unset — falling back to local SQLite (%s). "
            "In %s this data lives on ephemeral disk and is LOST on restart; "
            "point DATABASE_URL at Supabase/Postgres.",
            DEFAULT_SQLITE_URL, env,
        )



# ── Which DB owns a lecture dir ──────────────────────────────────────────────
# gc_sweep (backend/jobs.py) deletes lecture dirs the DB has no row for. Without
# knowing which DB created a dir, booting against ANY other DB (the offline
# tests' throwaway SQLite, a switch from Supabase to local mode) made every
# older lecture look orphaned, and they were deleted (2026-10-30, 2026-11-04).
# The pipeline now tags each dir it creates; the sweep only touches dirs tagged
# with the current DB. Untagged (older) dirs are never swept.
DB_MARKER_FILE = ".norai_db"


def database_identity(url: str | None = None) -> str:
    """Short stable id for a database URL, password excluded (so rotating
    the password doesn't orphan every lecture)."""
    import hashlib

    target = url or DATABASE_URL
    try:
        from sqlalchemy.engine import make_url

        target = make_url(target).render_as_string(hide_password=True)
    except Exception:  # noqa: BLE001 — unparsable URL: hash it whole
        pass
    return hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]


def mark_lecture_dir(lecture_dir) -> None:
    """Record that the current DB owns this lecture dir (see DB_MARKER_FILE)."""
    from pathlib import Path

    try:
        (Path(lecture_dir) / DB_MARKER_FILE).write_text(database_identity() + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not tag lecture dir %s with its DB: %s", lecture_dir, exc)


def lecture_dir_database(lecture_dir) -> str | None:
    """The DB id a lecture dir was tagged with, or None for untagged dirs."""
    from pathlib import Path

    try:
        return (Path(lecture_dir) / DB_MARKER_FILE).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def get_engine_kwargs(url: str | None = None) -> dict[str, Any]:
    target_url = url or DATABASE_URL
    kwargs: dict[str, Any] = {"echo": False}
    if target_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    elif "asyncpg" in target_url or target_url.startswith("postgresql"):
        connect_args: dict[str, Any] = {"timeout": 5, "command_timeout": 30}
        # Supabase Transaction Pooler (port 6543, PgBouncer) rejects client-side
        # prepared-statement persistence — disable asyncpg's statement cache so
        # every query uses simple (unnamed) statements. Session Pooler (5432)
        # keeps prepared statements as normal.
        try:
            port = urlsplit(target_url).port
        except ValueError:
            # Passwords may contain @ / stray colons that break netloc port
            # parsing; in that case the pooler can't be detected — proceed.
            port = None
        if port == 6543:
            connect_args["statement_cache_size"] = 0
        kwargs["connect_args"] = connect_args
    return kwargs


def _sqlite_pragmas(dbapi_conn, _record):
    """P3.1: WAL + busy_timeout on every new SQLite connection.

    The main app DB previously ran the default rollback journal, so concurrent
    writes (status polls + pipeline progress + webhooks) serialized with
    SQLITE_BUSY errors. Setting pragmas via a connect event listener runs them
    exactly once per pooled connection instead of ad-hoc per call site.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


engine = create_async_engine(DATABASE_URL, **get_engine_kwargs(DATABASE_URL))

if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    event.listen(engine.sync_engine, "connect", _sqlite_pragmas)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


