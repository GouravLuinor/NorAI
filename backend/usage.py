"""
backend/usage.py

P2 — Billing & quota made real.

Persists pipeline outcomes to the SaaS database (Lecture status, duration,
usage metering, UsageLog rows). It is deliberately written to be safely
callable from the SYNCHRONOUS pipeline worker thread:

  * it opens its OWN fresh engine (NullPool) inside an `asyncio.run()` block,
    so it never shares (or races) the main event loop's asyncpg pool;
  * it never raises — any DB error is logged and swallowed so a metering
    failure can never take down a running pipeline.

Metering rules (decided for P2):
  * only SUCCESSFUL runs consume quota minutes;
  * usage is `ceil(duration_sec / 60)` lecture-minutes per completed run;
  * a Subscription's `used_minutes_this_month` resets when its billing
    period has elapsed (`current_period_end` when set, else 30 days after
    `current_period_start`).
"""

import asyncio
import math
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select

from backend.db.database import DATABASE_URL
from backend.db.models import Lecture, Subscription, UsageLog

logger = logging.getLogger(__name__)

# Copied from backend/db/database.py: asyncpg/sqlite need matching connect args.
_ENGINE_KWARGS: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    _ENGINE_KWARGS["connect_args"] = {"check_same_thread": False}


def rollover_if_needed(sub: Subscription, now: Optional[datetime] = None) -> bool:
    """Reset used_minutes_this_month when the billing period has elapsed.

    Uses `current_period_end` when set, otherwise falls back to 30 days after
    `current_period_start` (the webhook does not yet populate period end).
    Returns True when a rollover occurred.
    """
    now = now or datetime.now(timezone.utc)
    if sub.used_minutes_this_month == 0:
        return False
    end = sub.current_period_end
    if end is None:
        start = sub.current_period_start or sub.created_at or now
        end = start + __import__("datetime").timedelta(days=30)
    # SQLite returns naive datetimes; assume any naive timestamp is UTC.
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if now >= end:
        sub.used_minutes_this_month = 0
        sub.current_period_start = now
        return True
    return False


def meter_minutes(duration_sec: Optional[float]) -> int:
    """Quota minutes consumed by a completed lecture (ceil of minutes)."""
    if not duration_sec or duration_sec <= 0:
        return 0
    return int(math.ceil(duration_sec / 60.0))


async def _record_outcome(
    user_id: str,
    lecture_id: str,
    duration_sec: Optional[float],
    completed: bool,
    error_message: Optional[str],
    title: Optional[str],
    output_dir: Optional[str],
    llm_calls: int = 0,
    est_cost_usd: Optional[float] = None,
) -> None:
    """Single-session write of the pipeline outcome (called via asyncio.run)."""
    async with async_sessionmaker(
        bind=create_async_engine(DATABASE_URL, poolclass=NullPool, **_ENGINE_KWARGS),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )() as session:
        lecture = await session.get(Lecture, lecture_id)
        if lecture is None:
            logger.warning(
                "usage: no Lecture row for %s (user %s) — skipping DB outcome", lecture_id, user_id
            )
            return

        lecture.status = "completed" if completed else "failed"
        lecture.duration_seconds = int(duration_sec or 0)
        lecture.output_dir = output_dir or lecture.output_dir
        if title:
            lecture.title = title
        if error_message:
            lecture.error_message = error_message[:4000]

        if not completed:
            await session.commit()
            return

        # Meter only successful runs.
        result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
        sub = result.scalar_one_or_none()
        minutes = meter_minutes(duration_sec)
        if sub is not None:
            rollover_if_needed(sub)
            sub.used_minutes_this_month = (sub.used_minutes_this_month or 0) + minutes
            session.add(sub)

        if minutes or llm_calls:
            session.add(
                UsageLog(
                    user_id=user_id,
                    lecture_id=lecture_id,
                    stage="pipeline",
                    input_tokens=0,
                    output_tokens=0,
                    estimated_cost_usd=float(est_cost_usd or 0.0),
                )
            )

        await session.commit()


def record_pipeline_outcome(
    user_id: Optional[str],
    lecture_id: str,
    duration_sec: Optional[float] = None,
    completed: bool = True,
    error_message: Optional[str] = None,
    title: Optional[str] = None,
    output_dir: Optional[str] = None,
    llm_calls: int = 0,
    est_cost_usd: Optional[float] = None,
) -> None:
    """Sync entry point for the pipeline worker thread. Never raises."""
    if not user_id:
        logger.info("usage: no user_id for lecture %s — skipping DB outcome", lecture_id)
        return
    try:
        asyncio.run(
            _record_outcome(
                user_id=user_id,
                lecture_id=lecture_id,
                duration_sec=duration_sec,
                completed=completed,
                error_message=error_message,
                title=title,
                output_dir=output_dir,
                llm_calls=llm_calls,
                est_cost_usd=est_cost_usd,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("usage: failed to record pipeline outcome for %s: %s", lecture_id, exc)
