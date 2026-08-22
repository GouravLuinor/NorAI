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
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import func, select, update

from backend.db.database import DATABASE_URL, get_engine_kwargs
from backend.db.models import Lecture, Subscription, UsageLog
from backend.timeutil import ensure_utc

logger = logging.getLogger(__name__)

# Copied from backend/db/database.py: asyncpg/sqlite need matching connect args.
_ENGINE_KWARGS: dict = get_engine_kwargs(DATABASE_URL)


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
        end = start + timedelta(days=30)
    # SQLite returns naive datetimes; normalize at one helper (P2.6).
    end = ensure_utc(end)
    if end is None:
        return False
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
    stage_usage: Optional[list[dict]] = None,
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

        # Meter only successful runs. P2.3: the minute increment is applied
        # atomically in SQL (used = used + n) — the previous ORM
        # read-modify-write lost increments under concurrent completions.
        result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
        sub = result.scalar_one_or_none()
        minutes = meter_minutes(duration_sec)
        if sub is not None:
            rolled = rollover_if_needed(sub)
            if rolled:
                # Rollover first, committed on its own so the increment below
                # starts from a clean period.
                await session.commit()
            await session.execute(
                update(Subscription)
                .where(Subscription.user_id == user_id)
                .values(
                    used_minutes_this_month=func.coalesce(
                        Subscription.used_minutes_this_month, 0
                    )
                    + minutes,
                    current_period_start=(
                        sub.current_period_start if rolled else Subscription.current_period_start
                    ),
                )
            )

        # P6.5: one UsageLog row per pipeline stage. Falls back to a single
        # coarse "pipeline" row when no per-stage ledger data is available.
        stages = stage_usage or (
            [
                {
                    "stage": "pipeline",
                    "model": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": llm_calls,
                    "cost_usd": float(est_cost_usd or 0.0),
                }
            ]
            if minutes or llm_calls
            else []
        )
        for s in stages:
            session.add(
                UsageLog(
                    user_id=user_id,
                    lecture_id=lecture_id,
                    stage=s.get("stage", "pipeline"),
                    input_tokens=int(s.get("input_tokens", 0) or 0),
                    output_tokens=int(s.get("output_tokens", 0) or 0),
                    estimated_cost_usd=float(s.get("cost_usd", 0.0) or 0.0),
                    model=s.get("model"),
                    calls=int(s.get("calls", 1) or 0),
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
    stage_usage: Optional[list[dict]] = None,
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
                stage_usage=stage_usage,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("usage: failed to record pipeline outcome for %s: %s", lecture_id, exc)


async def _flush_tutor_turn(
    user_id: str,
    lecture_id: str,
    stage: str,
    model: Optional[str],
    input_tokens: int,
    output_tokens: int,
    calls: int,
    cost_usd: float,
) -> None:
    """Write a single tutor-stage UsageLog row for one chat turn (asyncio.run)."""
    async with async_sessionmaker(
        bind=create_async_engine(DATABASE_URL, poolclass=NullPool, **_ENGINE_KWARGS),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )() as session:
        lecture = await session.get(Lecture, lecture_id)
        if lecture is None or lecture.user_id != user_id:
            logger.info(
                "usage: lecture %s not owned by user %s — skipping tutor usage", lecture_id, user_id
            )
            return
        session.add(
            UsageLog(
                user_id=user_id,
                lecture_id=lecture_id,
                stage=stage,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost_usd,
                model=model,
                calls=calls,
            )
        )
        await session.commit()


async def record_tutor_turn_async(
    user_id: Optional[str],
    lecture_id: str,
    stage: str = "tutor",
    model: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    calls: int = 1,
    cost_usd: float = 0.0,
) -> None:
    """Async flush of one tutor chat turn's metered usage. Never raises.

    Used by the /chat and /chat/stream handlers (already inside the event loop),
    where asyncio.run() would raise RuntimeError.
    """
    if not user_id:
        logger.info("usage: no user_id for tutor turn on %s — skipping", lecture_id)
        return
    try:
        await _flush_tutor_turn(
            user_id=user_id,
            lecture_id=lecture_id,
            stage=stage,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            calls=calls,
            cost_usd=cost_usd,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("usage: failed to record tutor turn for %s: %s", lecture_id, exc)


def record_tutor_turn(
    user_id: Optional[str],
    lecture_id: str,
    stage: str = "tutor",
    model: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    calls: int = 1,
    cost_usd: float = 0.0,
) -> None:
    """Sync flush of one tutor chat turn's metered usage. Never raises.

    For callers NOT inside an event loop (worker thread / tests); the async
    handlers should use record_tutor_turn_async instead.
    """
    if not user_id:
        logger.info("usage: no user_id for tutor turn on %s — skipping", lecture_id)
        return
    try:
        asyncio.run(
            record_tutor_turn_async(
                user_id=user_id,
                lecture_id=lecture_id,
                stage=stage,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                calls=calls,
                cost_usd=cost_usd,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("usage: failed to record tutor turn for %s: %s", lecture_id, exc)
