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

os.environ["NORAI_DEV_ACCESS"] = "0"

# Patch the auth dependency so we can simulate a signed-in user without
# crafting real Supabase JWTs.
from backend import main as main_mod
main_mod.NORAI_DEV_ACCESS = False
from backend.db.models import User as _User

FAKE_USER_ID = "user_test_1"


async def _seed(user_id: str = FAKE_USER_ID, used: int = 0, quota: int = 45,
                tier: str = "free", status: str = "trial", elapsed_period: bool = False):
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
            sub.current_period_end = None
        else:
            s.add(Subscription(
                user_id=user_id, status=status, plan_tier=tier,
                monthly_minutes_quota=quota, used_minutes_this_month=used,
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


def test_quota_requires_auth_and_reports_usage():
    client = TestClient(main_mod.app)
    # Unauthenticated /quota must return 401
    r_unauth = client.get("/quota")
    check("quota 401 without auth", r_unauth.status_code == 401)

    asyncio.run(_seed(used=3, quota=45))
    # Authenticated user
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.get("/quota")
        data = r.json()
        check("quota 200 with auth", r.status_code == 200)
        check("used reported", data["used_minutes_this_month"] == 3)
        check("quota reported 45", data["monthly_minutes_quota"] == 45)
        check("remaining computed 42", data["remaining_minutes"] == 42)
        check("plan tier free", data["plan_tier"] == "free")
        check("subscription status trial", data["subscription_status"] == "trial")
    finally:
        main_mod.app.dependency_overrides.clear()


def _enable_payments(on: bool):
    import config
    config.ENABLE_PAYMENTS = on
    config.RAZORPAY_KEY_ID = "rzp_test_key" if on else ""
    config.RAZORPAY_KEY_SECRET = "rzp_test_secret" if on else ""


def test_billing_returns_plan_and_usage():
    _enable_payments(True)
    asyncio.run(_seed(used=3, quota=45))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.get("/billing")
        data = r.json()
        check("billing 200", r.status_code == 200)
        check("plan tier", data["plan_tier"] == "free")
        check("plan details", data["plan"]["id"] == "free" and data["plan"]["max_lecture_min"] > 0)
        check("used", data["used_minutes_this_month"] == 3)
        check("remaining", data["remaining_minutes"] == 42)
        check("payments list", data["payments"] == [])
        check("payments enabled flag", data["payments_enabled"] is True)
        check("no lemon squeezy fields", "checkout_urls" not in data and "manage_url" not in data)
    finally:
        _enable_payments(False)
        main_mod.app.dependency_overrides.clear()


def test_public_plans():
    client = TestClient(main_mod.app)
    r = client.get("/billing/plans")
    data = r.json()
    ids = [p["id"] for p in data["plans"]]
    check("plans public 200", r.status_code == 200)
    check("plans catalogue", ids == ["free", "starter", "pro"])
    check("plans in INR", data["currency"] == "INR" and data["plans"][1]["price_inr"] > 0)
    check("payments off without keys", data["payments_enabled"] is False)


def test_razorpay_order_and_verify():
    import hashlib
    import hmac
    from backend import razorpay_client

    asyncio.run(_seed(used=0, quota=45))
    client = TestClient(main_mod.app)

    r = client.post("/billing/razorpay/order", json={"plan_id": "starter"})
    check("order 401 without auth", r.status_code == 401)

    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    created = []

    async def fake_create_order(amount_paise, receipt, notes):
        created.append((amount_paise, notes))
        return {"id": f"order_test_{len(created)}", "amount": amount_paise, "currency": "INR"}

    async def fake_fetch_payment(payment_id):
        return {"id": payment_id, "order_id": "order_test_1", "amount": 14900,
                "status": "captured", "method": "upi"}

    orig = razorpay_client.create_order, razorpay_client.fetch_payment
    razorpay_client.create_order, razorpay_client.fetch_payment = fake_create_order, fake_fetch_payment
    try:
        r = client.post("/billing/razorpay/order", json={"plan_id": "starter"})
        check("order 503 while payments disabled", r.status_code == 503)

        _enable_payments(True)
        r = client.post("/billing/razorpay/order", json={"plan_id": "free"})
        check("free plan not purchasable", r.status_code == 400)
        r = client.post("/billing/razorpay/order", json={"plan_id": "enterprise"})
        check("unknown plan rejected", r.status_code == 400)

        r = client.post("/billing/razorpay/order", json={"plan_id": "starter", "amount": 1})
        data = r.json()
        check("order created", r.status_code == 200 and data["order_id"] == "order_test_1")
        check("amount set server-side", created[-1][0] == 14900 and data["amount"] == 14900)
        check("order notes carry user + plan", created[-1][1] == {"user_id": FAKE_USER_ID, "plan_id": "starter"})
        check("key id returned for checkout", data["key_id"] == "rzp_test_key")

        r = client.post("/billing/razorpay/verify", json={
            "razorpay_order_id": "order_test_1", "razorpay_payment_id": "pay_test_1",
            "razorpay_signature": "0" * 64})
        check("forged signature rejected", r.status_code == 400)

        sig = hmac.new(b"rzp_test_secret", b"order_test_1|pay_test_1", hashlib.sha256).hexdigest()
        body = {"razorpay_order_id": "order_test_1", "razorpay_payment_id": "pay_test_1",
                "razorpay_signature": sig}
        r = client.post("/billing/razorpay/verify", json=body)
        data = r.json()
        check("verify 200", r.status_code == 200)
        check("verify grants starter", data["granted"] is True and data["plan_tier"] == "starter")
        check("starter quota 300", data["monthly_minutes_quota"] == 300)
        check("pass expiry reported", data["current_period_end"] is not None)
        check("payment in history", data["payments"][0]["status"] == "paid" and data["payments"][0]["method"] == "upi")

        r = client.post("/billing/razorpay/verify", json=body)
        check("re-verify is idempotent", r.status_code == 200 and r.json()["granted"] is False
              and r.json()["monthly_minutes_quota"] == 300)

        # Another user's order is invisible.
        async def other_user():
            return _User(id="someone_else", email="else@example.com", is_anonymous=False)
        asyncio.run(_seed(user_id="someone_else"))
        main_mod.app.dependency_overrides[main_mod.get_current_user] = other_user
        r = client.post("/billing/razorpay/verify", json=body)
        check("cannot verify another user's order", r.status_code == 404)

        async def anon_user():
            return _User(id="anon_1", email="anon@example.com", is_anonymous=True)
        main_mod.app.dependency_overrides[main_mod.get_current_user] = anon_user
        r = client.post("/billing/razorpay/order", json={"plan_id": "starter"})
        check("anonymous user cannot buy", r.status_code == 403)
    finally:
        razorpay_client.create_order, razorpay_client.fetch_payment = orig
        _enable_payments(False)
        main_mod.app.dependency_overrides.clear()


def test_paid_plan_raises_duration_cap():
    # A Starter pass lifts the 45-min free cap to 90 min.
    asyncio.run(_seed(used=0, quota=300, tier="starter", status="active"))
    async def _set_end():
        from sqlalchemy import select
        sf = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with sf() as s:
            sub = (await s.execute(select(Subscription).where(Subscription.user_id == FAKE_USER_ID))).scalar_one()
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=10)
            await s.commit()
    asyncio.run(_set_end())
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00" + b"fakedata"
        r = client.post("/process", data={"source_type": "upload", "duration": "100"},
                        files={"file": ("v.mp4", fake_mp4, "video/mp4")})
        check("starter rejects 100-min lecture", r.status_code == 429)
        r = client.get("/quota")
        check("quota reports starter max length", r.json()["max_lecture_minutes"] == 90)
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


def test_process_rejects_guest_with_header():
    client = TestClient(main_mod.app)
    r = client.post(
        "/process",
        headers={"X-Guest-Id": "test_guest_device"},
        data={"source_type": "youtube", "url": "https://youtube.com/watch?v=abc123"},
    )
    # Guest access removed: must return 401
    check("process rejects guest header with 401", r.status_code == 401)


def test_guest_rejected_from_quota():
    client = TestClient(main_mod.app)
    r = client.get("/quota", headers={"X-Guest-Id": "test_guest_quota"})
    check("guest quota rejected with 401", r.status_code == 401)


def test_process_enforces_pre_download_quota():
    asyncio.run(_seed(used=44, quota=45))  # only 1 minute left
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
    asyncio.run(_seed(used=45, quota=45))
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
    asyncio.run(_seed(used=45, quota=45, elapsed_period=True))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        r = client.get("/quota")
        data = r.json()
        check("expired-period quota 200", r.status_code == 200)
        check("expired-period used rolled to 0", data["used_minutes_this_month"] == 0)
        check("expired-period remaining restored to 45", data["remaining_minutes"] == 45)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_process_unlocked_after_period_rollover():
    # P0 regression: rollover used to run only on pipeline completion, which
    # this very gate blocked — expired-period users were 429-locked forever.
    asyncio.run(_seed(used=45, quota=45, elapsed_period=True))
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
    asyncio.run(_seed(used=0, quota=45))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        # 50 minutes > 45-min free-trial ceiling.
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "50"},
            files={"file": ("v.mp4", b"fakedata", "video/mp4")},
        )
        check("process 429 over free-trial duration", r.status_code == 429)
    finally:
        main_mod.app.dependency_overrides.clear()


def test_process_allows_within_quota_upload():
    asyncio.run(_seed(used=0, quota=45))
    client = TestClient(main_mod.app)
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
    try:
        # P1.5 magic-byte sniffing: the payload must at least look like mp4
        # (ftyp box) for the endpoint to accept it.
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00" + b"fakedata"
        r = client.post(
            "/process",
            data={"source_type": "upload", "duration": "2"},
            files={"file": ("v.mp4", fake_mp4, "video/mp4")},
        )
        # Returns a task id and starts the pipeline; we just assert 200/202-ish
        # contract (the background thread will fail fast on the fake file, but
        # the endpoint itself must accept it).
        check("process accepts within-quota upload", r.status_code in (200, 202))
    finally:
        main_mod.app.dependency_overrides.clear()


if __name__ == "__main__":
    test_quota_requires_auth_and_reports_usage()
    test_billing_returns_plan_and_usage()
    test_public_plans()
    test_razorpay_order_and_verify()
    test_paid_plan_raises_duration_cap()
    test_billing_requires_auth()
    test_process_requires_auth()
    test_process_rejects_guest_with_header()
    test_guest_rejected_from_quota()
    test_process_enforces_pre_download_quota()
    test_process_rejects_exhausted_quota()
    test_quota_rolls_over_expired_period()
    test_process_unlocked_after_period_rollover()
    test_process_rejects_over_free_trial_duration()
    test_process_allows_within_quota_upload()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)

