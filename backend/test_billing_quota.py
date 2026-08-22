"""
Standalone test: P2 /quota + /billing endpoint contracts and /process auth
requirement + pre-download quota enforcement.

Run directly: venv/bin/python backend/test_billing_quota.py

Note: uses TestClient WITHOUT the `with` block so the lifespan startup
(init_db against the real DATABASE_URL) is skipped — mirrors test_estimate.py.
"""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isolate DB writes to a throwaway SQLite file (never the real DATABASE_URL).
_TMP_DB = "/tmp/norai_test_billing.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"

import asyncio
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.db.database import Base, engine
from backend.db.models import User, Subscription
from sqlalchemy.ext.asyncio import async_sessionmaker

# LEMONSQUEEZY URLs come from config, which reads env at import time.
os.environ["LEMONSQUEEZY_CHECKOUT_STARTER_URL"] = "https://store.test/buy/starter"
os.environ["LEMONSQUEEZY_CHECKOUT_PRO_URL"] = "https://store.test/buy/pro"
os.environ["LEMONSQUEEZY_CUSTOMER_PORTAL_URL"] = "https://store.test/billing"
os.environ["NORAI_DEV_ACCESS"] = "0"

# Patch the auth dependency so we can simulate a signed-in user without
# crafting real Supabase JWTs.
from backend import main as main_mod
main_mod.NORAI_DEV_ACCESS = False
from backend.db.models import User as _User

FAKE_USER_ID = "user_test_1"


async def _seed(user_id: str = FAKE_USER_ID, used: int = 0, quota: int = 15,
                tier: str = "free", status: str = "trial", ls_sub: str | None = None,
                elapsed_period: bool = False):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from sqlalchemy import select
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as s:
        existing = (await s.execute(select(_User).where(_User.id == user_id))).scalar_one_or_none()
        if not existing:
            s.add(_User(id=user_id, email=f"{user_id}@example.com", is_anonymous=False))
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == user_id))).scalar_one_or_none()
        if sub:
            sub.used_minutes_this_month = used
            sub.monthly_minutes_quota = quota
            sub.plan_tier = tier
            sub.status = status
            sub.lemon_squeezy_subscription_id = ls_sub
        else:
            s.add(Subscription(
                user_id=user_id, status=status, plan_tier=tier,
                monthly_minutes_quota=quota, used_minutes_this_month=used,
                lemon_squeezy_subscription_id=ls_sub,
            ))
        if elapsed_period:
            now = datetime.now(timezone.utc)
            target = sub or next(
                x for x in s.new if isinstance(x, Subscription) and x.user_id == user_id
            )
            target.current_period_start = now - timedelta(days=40)
            target.current_period_end = now - timedelta(days=10)
        await s.commit()


def _fake_user():
    async def _dep():
        return _User(id=FAKE_USER_ID, email=f"{FAKE_USER_ID}@example.com", is_anonymous=False)
    return _dep


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


def test_quota_requires_no_auth_and_reports_usage():
    asyncio.run(_seed(used=3))
    client = TestClient(main_mod.app)
    # Swap the optional-auth dependency out for a fake authenticated user.
    main_mod.app.dependency_overrides[main_mod.get_current_user_optional] = _fake_user()
    try:
        r = client.get("/quota")
        data = r.json()
        check("quota 200", r.status_code == 200)
        check("used reported", data["used_minutes_this_month"] == 3)
        check("quota reported", data["monthly_minutes_quota"] == 15)
        check("remaining computed", data["remaining_minutes"] == 12)
        check("plan tier free", data["plan_tier"] == "free")
        check("subscription status trial", data["subscription_status"] == "trial")
    finally:
        main_mod.app.dependency_overrides.clear()


def test_billing_returns_plan_usage_and_links():
    asyncio.run(_seed(used=3, ls_sub="ls_123"))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.get("/billing")
        data = r.json()
        check("billing 200", r.status_code == 200)
        check("plan tier", data["plan_tier"] == "free")
        check("used", data["used_minutes_this_month"] == 3)
        check("remaining", data["remaining_minutes"] == 12)
        check("checkout starter url", data["checkout_urls"]["starter"] == "https://store.test/buy/starter")
        check("checkout pro url", data["checkout_urls"]["pro"] == "https://store.test/buy/pro")
        check("manage url", data["manage_url"] == "https://store.test/billing")
        check("ls sub id", data["lemon_squeezy_subscription_id"] == "ls_123")
    finally:
        main_mod.app.dependency_overrides.clear()


def test_billing_requires_auth():
    client = TestClient(main_mod.app)
    r = client.get("/billing")
    check("billing 401 without token", r.status_code == 401)


def test_process_requires_auth():
    client = TestClient(main_mod.app)
    r = client.post("/process", data={"source_type": "youtube", "url": "https://youtube.com/watch?v=abc123"})
    check("process 401 without token", r.status_code == 401)


def test_process_allows_guest_with_header():
    client = TestClient(main_mod.app)
    r = client.post(
        "/process",
        headers={"X-Guest-Id": "test_guest_device"},
        data={"source_type": "youtube", "url": "https://youtube.com/watch?v=abc123"},
    )
    # Guest resolves to a User row, so auth passes; the request must fail on
    # validation/quota, NOT on a 401.
    check("process guest not 401", r.status_code != 401)


def test_guest_has_trial_quota():
    client = TestClient(main_mod.app)
    r = client.get("/quota", headers={"X-Guest-Id": "test_guest_quota"})
    data = r.json()
    check("guest quota 200", r.status_code == 200)
    check("guest is_anonymous", data.get("is_anonymous") is True)
    check("guest trial quota 15", data.get("monthly_minutes_quota") == 15)
    check("guest remaining 15", data.get("remaining_minutes") == 15)


def test_process_enforces_pre_download_quota():
    asyncio.run(_seed(used=14, quota=15))  # only 1 minute left
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        # A 10-minute upload (duration passed in minutes) would exceed the 1
        # remaining minute, and must be rejected BEFORE any pipeline work.
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "10"},
            files={"file": ("v.mp4", b"fakedata", "video/mp4")},
        )
        check("process 429 when over remaining quota", r.status_code == 429)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_process_rejects_exhausted_quota():
    asyncio.run(_seed(used=15, quota=15))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "1"},
            files={"file": ("v.mp4", b"fakedata", "video/mp4")},
        )
        check("process 429 when quota exhausted", r.status_code == 429)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_quota_rolls_over_expired_period():
    # P0 regression: /quota must roll an elapsed billing period forward
    # instead of reporting a permanently exhausted quota.
    asyncio.run(_seed(used=15, quota=15, elapsed_period=True))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user_optional] = _fake_user()
    try:
        r = client.get("/quota")
        data = r.json()
        check("expired-period quota 200", r.status_code == 200)
        check("expired-period used rolled to 0", data["used_minutes_this_month"] == 0)
        check("expired-period remaining restored", data["remaining_minutes"] == 15)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_process_unlocked_after_period_rollover():
    # P0 regression: rollover used to run only on pipeline completion, which
    # this very gate blocked — expired-period users were 429-locked forever.
    asyncio.run(_seed(used=15, quota=15, elapsed_period=True))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "1"},
            files={"file": ("v.mp4", b"fakedata", "video/mp4")},
        )
        check("process not 429 after period rollover", r.status_code != 429)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_process_rejects_over_free_trial_duration():
    asyncio.run(_seed(used=0, quota=15))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        # 20 minutes > 15-min free-trial ceiling.
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "20"},
            files={"file": ("v.mp4", b"fakedata", "video/mp4")},
        )
        check("process 429 over free-trial duration", r.status_code == 429)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_process_allows_within_quota_upload():
    asyncio.run(_seed(used=0, quota=15))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "2"},
            files={"file": ("v.mp4", b"fakedata", "video/mp4")},
        )
        # Returns a task id and starts the pipeline; we just assert 200/202-ish
        # contract (the background thread will fail fast on the fake file, but
        # the endpoint itself must accept it).
        check("process accepts within-quota upload", r.status_code in (200, 202))
    finally:
        main_mod.app.dependency_overrides.clear()


if __name__ == "__main__":
    test_quota_requires_no_auth_and_reports_usage()
    test_billing_returns_plan_usage_and_links()
    test_billing_requires_auth()
    test_process_requires_auth()
    test_process_allows_guest_with_header()
    test_guest_has_trial_quota()
    test_process_enforces_pre_download_quota()
    test_process_rejects_exhausted_quota()
    test_quota_rolls_over_expired_period()
    test_process_unlocked_after_period_rollover()
    test_process_rejects_over_free_trial_duration()
    test_process_allows_within_quota_upload()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
