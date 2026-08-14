"""
Standalone test: P6.5 usage dashboard — ledger accounting, per-stage UsageLog
rows, tutor-turn metering, and the GET /usage aggregate endpoint.

Run directly: venv/bin/python backend/test_usage_dashboard.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isolate DB writes to a throwaway SQLite file (never the real DATABASE_URL).
_TMP_DB = "/tmp/norai_test_usage_dashboard.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["GEMINI_API_KEY"] = "test-key"

import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.db.database import Base, engine
from backend.db.models import User, Subscription, Lecture, UsageLog
from backend import main as main_mod
from backend.db.models import User as _User

PASSED = 0
FAILED = 0

FAKE_USER_ID = "user_dash_1"


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


async def _setup_user(user_id: str = FAKE_USER_ID, used: int = 0):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as s:
        u = await s.get(_User, user_id)
        if not u:
            s.add(_User(id=user_id, email=f"{user_id}@example.com", is_anonymous=False))
        sub = (await s.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )).scalar_one_or_none()
        if sub:
            sub.used_minutes_this_month = used
        else:
            s.add(Subscription(user_id=user_id, status="trial", plan_tier="free",
                               monthly_minutes_quota=15, used_minutes_this_month=used))
        lec = await s.get(Lecture, "lec_dash")
        if not lec:
            s.add(Lecture(id="lec_dash", user_id=user_id, title="Dash", status="processing"))
        await s.commit()


def _fake_user():
    async def _dep():
        return _User(id=FAKE_USER_ID, email=f"{FAKE_USER_ID}@example.com", is_anonymous=False)
    return _dep


# ── Ledger accounting ─────────────────────────────────────────────────────────

def test_ledger_accumulates_and_diffs():
    from backend import usage_ledger as ul
    ul.reset_usage()
    ul.record_llm_usage("extract", "gemini-3.5-flash-lite", 1000, 200)
    ul.record_llm_usage("tutor", "gemini-3.5-flash-lite", 500, 300)
    ul.record_embed_usage("embed", "gemini-embedding-2", 800)

    before = ul.snapshot_usage()
    ul.record_llm_usage("tutor", "gemini-3.5-flash-lite", 100, 100)
    diff = ul.diff_usage(before)

    tutor = next((d for d in diff if d["stage"] == "tutor"), None)
    check("tutor delta isolates the increment", tutor is not None)
    check("tutor calls delta 1", tutor and tutor["calls"] == 1)
    check("tutor tokens delta", tutor and tutor["input_tokens"] == 100 and tutor["output_tokens"] == 100)
    check("tutor model tracked", tutor and tutor["model"] == "gemini-3.5-flash-lite")

    # 1000*0.30 + 200*2.5 = $0.0008 per 1M... exact from model_price:
    full = ul.diff_usage({})
    extract = next((d for d in full if d["stage"] == "extract"), None)
    check("extract cost > 0", extract and extract["cost_usd"] > 0)
    embed = next((d for d in full if d["stage"] == "embed"), None)
    check("embed estimated from chars", embed and embed["input_tokens"] == 200)

    ul.reset_usage()


def test_record_generate_usage_reads_gemini_metadata():
    from backend import usage_ledger as ul
    ul.reset_usage()

    class _Meta:
        prompt_token_count = 123
        candidates_token_count = 45

    class _Resp:
        usage_metadata = _Meta()

    ul.record_generate_usage("outline", "gemini-3.5-flash-lite", _Resp())
    full = ul.diff_usage({})
    outline = next((d for d in full if d["stage"] == "outline"), None)
    check("raw gemini metadata read", outline and outline["input_tokens"] == 123 and outline["output_tokens"] == 45)
    check("outline calls 1", outline and outline["calls"] == 1)

    # Missing usage_metadata is tolerated and still counted.
    class _Empty:
        pass

    ul.record_generate_usage("notes", "gemini-3.5-flash-lite", _Empty())
    full2 = ul.diff_usage({})
    notes = next((d for d in full2 if d["stage"] == "notes"), None)
    check("missing metadata still counts the call", notes and notes["calls"] == 1 and notes["cost_usd"] == 0)

    ul.reset_usage()


# ── DB persistence ────────────────────────────────────────────────────────────

async def _read_logs(lecture_id: str, stage: str | None = None):
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as s:
        q = select(UsageLog).where(UsageLog.lecture_id == lecture_id)
        if stage:
            q = q.where(UsageLog.stage == stage)
        return (await s.execute(q)).scalars().all()


def test_pipeline_writes_per_stage_rows():
    run(_setup_user())
    from backend.usage import record_pipeline_outcome

    stages = [
        {"stage": "extract", "model": "gemini-3.5-flash-lite", "calls": 3,
         "input_tokens": 3000, "output_tokens": 600, "cost_usd": 0.00165},
        {"stage": "embed", "model": "gemini-embedding-2", "calls": 2,
         "input_tokens": 400, "output_tokens": 0, "cost_usd": 0.00008},
    ]
    record_pipeline_outcome(
        user_id=FAKE_USER_ID, lecture_id="lec_dash", duration_sec=505.76,
        completed=True, title="Dash", output_dir="outputs/x",
        llm_calls=5, est_cost_usd=0.00173, stage_usage=stages,
    )

    logs = run(_read_logs("lec_dash"))

    check("two stage rows written", len(logs) == 2)
    by_stage = {l.stage: l for l in logs}
    check("extract row has model", by_stage.get("extract") and by_stage["extract"].model == "gemini-3.5-flash-lite")
    check("extract row tokens", by_stage.get("extract") and by_stage["extract"].input_tokens == 3000)
    check("extract row calls", by_stage.get("extract") and by_stage["extract"].calls == 3)
    check("embed row cost", by_stage.get("embed") and abs(by_stage["embed"].estimated_cost_usd - 0.00008) < 1e-9)


def test_tutor_turn_metered_only_for_owner():
    run(_setup_user())
    from backend.usage import record_tutor_turn

    record_tutor_turn(
        user_id=FAKE_USER_ID, lecture_id="lec_dash", stage="tutor",
        model="gemini-3.5-flash-lite", input_tokens=500, output_tokens=300,
        calls=1, cost_usd=0.000575,
    )

    logs = run(_read_logs("lec_dash", "tutor"))
    check("tutor row written", len(logs) == 1)
    check("tutor row tokens", logs and logs[0].input_tokens == 500 and logs[0].output_tokens == 300)

    # A non-owner must NOT get a row.
    run(_setup_user("user_dash_stranger", used=0))
    record_tutor_turn(
        user_id="user_dash_stranger", lecture_id="lec_dash", stage="tutor",
        input_tokens=100, output_tokens=100, calls=1, cost_usd=0.000175,
    )
    logs2 = run(_read_logs("lec_dash", "tutor"))
    check("non-owner turn NOT written", len(logs2) == 1)


def test_tutor_turn_async_variant():
    from backend.usage import record_tutor_turn_async

    run(_setup_user())
    before = run(_read_logs("lec_dash", "tutor"))
    run(record_tutor_turn_async(
        user_id=FAKE_USER_ID, lecture_id="lec_dash", stage="tutor",
        model="gemini-3.5-flash-lite", input_tokens=40, output_tokens=20,
        calls=1, cost_usd=0.00004,
    ))
    logs = run(_read_logs("lec_dash", "tutor"))
    added = [l for l in logs if l.input_tokens == 40]
    check("async variant writes row", len(logs) == len(before) + 1 and len(added) == 1)

    run(record_tutor_turn_async(
        user_id=None, lecture_id="lec_dash", stage="tutor",
        input_tokens=9, output_tokens=9, calls=1, cost_usd=0.0,
    ))
    logs2 = run(_read_logs("lec_dash", "tutor"))
    check("async variant skips anonymous", len(logs2) == len(logs))


# ── GET /usage endpoint ───────────────────────────────────────────────────────

def test_usage_endpoint_aggregates():
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user_optional] = _fake_user()
    try:
        r = client.get("/usage")
        data = r.json()
        check("usage 200", r.status_code == 200)
        check("totals cost aggregated", data["totals"]["cost_usd"] > 0)
        check("totals calls aggregated", data["totals"]["api_calls"] >= 4)
        check("by_stage has extract", any(s["stage"] == "extract" for s in data["by_stage"]))
        check("by_stage has tutor", any(s["stage"] == "tutor" for s in data["by_stage"]))
        check("by_day populated", len(data["by_day"]) >= 1)
        check("by_lecture populated", any(l["lecture_id"] == "lec_dash" for l in data["by_lecture"]))
        check("is_anonymous false for user", data["is_anonymous"] is False)
        check("is_estimated true (embed present)", data["is_estimated"] is True)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_usage_endpoint_anonymous_is_zero():
    client = TestClient(main_mod.app)
    # No override -> get_current_user_optional returns None (no auth header).
    try:
        r = client.get("/usage")
        data = r.json()
        check("anonymous usage 200", r.status_code == 200)
        check("anonymous zero totals", data["totals"]["cost_usd"] == 0 and data["totals"]["api_calls"] == 0)
        check("anonymous flagged", data["is_anonymous"] is True)
    finally:
        main_mod.app.dependency_overrides.clear()


if __name__ == "__main__":
    test_ledger_accumulates_and_diffs()
    test_record_generate_usage_reads_gemini_metadata()
    test_pipeline_writes_per_stage_rows()
    test_tutor_turn_metered_only_for_owner()
    test_tutor_turn_async_variant()
    test_usage_endpoint_aggregates()
    test_usage_endpoint_anonymous_is_zero()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)