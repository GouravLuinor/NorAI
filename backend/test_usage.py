"""
Standalone test: P2 usage metering + Lecture status persistence.
Run directly: venv/bin/python backend/test_usage.py
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isolate DB writes to a throwaway SQLite file (never the real DATABASE_URL).
_TMP_DB = "/tmp/norai_test_usage.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.db.database import Base, engine
from backend.db.models import User, Subscription, Lecture, UsageLog
from backend.usage import rollover_if_needed, meter_minutes, record_pipeline_outcome

PASSED = 0
FAILED = 0


def check(label: str, cond: bool):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label}")


def run(coro):
    return asyncio.run(coro)


async def _setup_user(user_id: str, used: int = 0, quota: int = 15,
                      period_start_days_ago: int = 0, period_end_days_from_now=None):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_factory() as s:
        u = User(id=user_id, email=f"{user_id}@example.com", is_anonymous=False)
        s.add(u)
        sub = Subscription(
            user_id=user_id, status="trial", plan_tier="free",
            monthly_minutes_quota=quota, used_minutes_this_month=used,
            current_period_start=now - timedelta(days=period_start_days_ago),
            current_period_end=(
                now + timedelta(days=period_end_days_from_now)
                if period_end_days_from_now is not None else None
            ),
        )
        s.add(sub)
        lec = Lecture(id=f"lec_{user_id}", user_id=user_id, title="T", status="processing")
        s.add(lec)
        await s.commit()
    return f"lec_{user_id}"


async def _read(user_id: str, lecture_id: str):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == user_id))).scalar_one()
        lec = (await s.execute(select(Lecture).where(Lecture.id == lecture_id))).scalar_one()
        logs = (await s.execute(select(UsageLog).where(UsageLog.lecture_id == lecture_id))).scalars().all()
        return sub, lec, logs


def test_meter_minutes():
    check("none -> 0", meter_minutes(None) == 0)
    check("zero -> 0", meter_minutes(0) == 0)
    check("negative -> 0", meter_minutes(-5) == 0)
    check("60s -> 1", meter_minutes(60) == 1)
    check("90s -> 2 (ceil)", meter_minutes(90) == 2)
    check("505.76s -> 9", meter_minutes(505.76) == 9)


def test_rollover():
    now = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    sub = Subscription(used_minutes_this_month=0, current_period_start=now - timedelta(days=40))
    check("zero usage no rollover", rollover_if_needed(sub, now) is False)

    sub = Subscription(
        used_minutes_this_month=5,
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=25),
    )
    check("future period_end keeps usage", rollover_if_needed(sub, now) is False)
    check("usage unchanged", sub.used_minutes_this_month == 5)

    sub = Subscription(
        used_minutes_this_month=7,
        current_period_start=now - timedelta(days=35),
        current_period_end=now - timedelta(days=5),
    )
    check("elapsed period_end rolls over", rollover_if_needed(sub, now) is True)
    check("usage reset to 0", sub.used_minutes_this_month == 0)

    sub = Subscription(
        used_minutes_this_month=3,
        current_period_start=now - timedelta(days=31),
        current_period_end=None,
    )
    check("30d fallback rolls over", rollover_if_needed(sub, now) is True)
    check("fallback usage reset", sub.used_minutes_this_month == 0)

    sub = Subscription(
        used_minutes_this_month=3,
        current_period_start=now - timedelta(days=10),
        current_period_end=None,
    )
    check("30d fallback no rollover within month", rollover_if_needed(sub, now) is False)


def test_success_meters_and_updates_status():
    run(_setup_user("u_success", used=2))
    record_pipeline_outcome(
        user_id="u_success", lecture_id="lec_u_success",
        duration_sec=505.76, completed=True, title="My Lecture", output_dir="outputs/x",
        llm_calls=17,
    )
    sub, lec, logs = run(_read("u_success", "lec_u_success"))
    check("used minutes incremented by ceil", sub.used_minutes_this_month == 2 + 9)
    check("lecture status completed", lec.status == "completed")
    check("lecture duration persisted", lec.duration_seconds == 505)
    check("lecture title persisted", lec.title == "My Lecture")
    check("lecture output_dir persisted", lec.output_dir == "outputs/x")
    check("usage log written", len(logs) >= 1)
    check("no error message on success", lec.error_message is None)


def test_failure_does_not_meter_but_updates_status():
    run(_setup_user("u_fail", used=4))
    record_pipeline_outcome(
        user_id="u_fail", lecture_id="lec_u_fail",
        duration_sec=600, completed=False, error_message="boom",
        output_dir="outputs/y",
    )
    sub, lec, logs = run(_read("u_fail", "lec_u_fail"))
    check("failed run NOT metered", sub.used_minutes_this_month == 4)
    check("lecture status failed", lec.status == "failed")
    check("error message persisted", lec.error_message == "boom")
    check("no usage log on failure", len(logs) == 0)


def test_rollover_happens_at_meter_time():
    # Used 5, period started 40 days ago, no period_end -> reset before adding.
    run(_setup_user("u_roll", used=5, period_start_days_ago=40))
    record_pipeline_outcome(user_id="u_roll", lecture_id="lec_u_roll", duration_sec=60, completed=True)
    sub, _, _ = run(_read("u_roll", "lec_u_roll"))
    check("rollover reset then metered", sub.used_minutes_this_month == 1)


def test_no_user_id_is_safe_noop():
    # Should log + return, never raise.
    run(_setup_user("u_anon", used=0))
    record_pipeline_outcome(user_id=None, lecture_id="lec_u_anon", duration_sec=60, completed=True)
    sub, lec, logs = run(_read("u_anon", "lec_u_anon"))
    check("lecture untouched without user_id", lec.status == "processing")
    check("usage untouched without user_id", sub.used_minutes_this_month == 0)


if __name__ == "__main__":
    test_meter_minutes()
    test_rollover()
    test_success_meters_and_updates_status()
    test_failure_does_not_meter_but_updates_status()
    test_rollover_happens_at_meter_time()
    test_no_user_id_is_safe_noop()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
