"""
Standalone test: webhook signature verification (P0.1) and tier/status
normalization (P0.2). Run directly: venv/bin/python backend/test_webhooks.py
"""

import hmac
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("LEMONSQUEEZY_WEBHOOK_SECRET", None)
os.environ["NORAI_ALLOW_UNSIGNED_WEBHOOKS"] = "0"

# P1 branch tests need a real async session — isolate to a throwaway SQLite
# file BEFORE backend.db.database is imported anywhere.
_TMP_DB = "/tmp/norai_test_webhooks.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
# Force-assign (not setdefault): the shared runner DATABASE_URL accumulates
# rows across suite runs and trips UNIQUE constraints here.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"

from backend.routers.webhooks import (
    verify_signature,
    PLAN_TIER_BY_VARIANT,
    VALID_SUBSCRIPTION_STATUSES,
)

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


def test_verify_signature_fails_closed():
    # Empty secret must NOT authenticate anything.
    check("empty secret rejects", verify_signature(b"body", "sig", "") is False)
    body = b'{"hello":"world"}'
    sig = hmac.new(b"k", body, hashlib.sha256).hexdigest()
    check("valid HMAC accepted", verify_signature(body, sig, "k") is True)
    check("bad HMAC rejected", verify_signature(body, "0" * 64, "k") is False)
    check("tampered body rejected", verify_signature(b"tampered", sig, "k") is False)


def test_tier_map():
    check("exact 'pro' -> pro", PLAN_TIER_BY_VARIANT.get("pro") == "pro")
    check("exact 'pro-student' -> pro", PLAN_TIER_BY_VARIANT.get("pro-student") == "pro")
    check("exact 'starter' -> starter", PLAN_TIER_BY_VARIANT.get("starter") == "starter")
    check("unknown variant not silently 'pro'",
          PLAN_TIER_BY_VARIANT.get("student-discount-pro") is None)
    # The security property: substring 'pro' must not upgrade an unknown variant.
    check("'hacker-pro-supreme' not mapped to pro",
          PLAN_TIER_BY_VARIANT.get("hacker-pro-supreme") is None)


def test_status_allowlist():
    check("active in allowlist", "active" in VALID_SUBSCRIPTION_STATUSES)
    check("on_trial NOT in allowlist", "on_trial" not in VALID_SUBSCRIPTION_STATUSES)
    check("paused in allowlist", "paused" in VALID_SUBSCRIPTION_STATUSES)


# ── P1: handler-level branch tests (direct call, real async session) ─────────

import asyncio
import json

import fastapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

os.environ["LEMONSQUEEZY_WEBHOOK_SECRET"] = "whsec_test_k"
from backend.routers.webhooks import handle_lemonsqueezy_webhook
# The router snapshots the secret at import time — patch the module global so
# handler branches past the 503 guard are reachable.
import backend.routers.webhooks as _wh_mod
_wh_mod.LEMONSQUEEZY_WEBHOOK_SECRET = "whsec_test_k"
from backend.db.database import Base, engine
from backend.db.models import User as DbUser, Subscription, WebhookEvent


class _FakeRequest:
    def __init__(self, body_bytes: bytes, signature: str = ""):
        self._body = body_bytes
        self.headers = {"X-Signature": signature}

    async def body(self) -> bytes:
        return self._body

    async def json(self):
        return json.loads(self._body)  # mirrors Starlette: raises on bad JSON


def _signed(payload: dict) -> bytes:
    raw = json.dumps(payload).encode()
    sig = hmac.new(b"whsec_test_k", raw, hashlib.sha256).hexdigest()
    return raw, sig  # type: ignore[return-value]


async def _setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    return sf


async def _call(payload: dict):
    sf = await _setup_db()
    raw, sig = _signed(payload)
    async with sf() as s:
        res = await handle_lemonsqueezy_webhook(_FakeRequest(raw, sig), s)
        # The real get_db dependency commits on success; a bare session
        # rolls back on close, so commit explicitly here.
        await s.commit()
        return res


def _seed_payload(event_name: str, event_id: str, variant: str = "pro",
                  status_: str = "active", with_user: bool = True) -> dict:
    meta_custom = {"user_id": "user_wh_1"} if with_user else {}
    return {
        "meta": {"event_name": event_name, "custom_data": meta_custom,
                 "webhook_id": event_id},
        "data": {
            "id": f"sub-{event_id}",
            "attributes": {"customer_id": "c-123", "variant_name": variant,
                           "status": status_},
        },
    }


async def _run_branch_tests():
    check_count_before = PASSED

    # Seed user + subscription row.
    sf = await _setup_db()
    async with sf() as s:
        s.add(DbUser(id="user_wh_1", email="wh@example.com", is_anonymous=False))
        s.add(Subscription(user_id="user_wh_1", status="trial", plan_tier="free",
                           monthly_minutes_quota=15))
        await s.commit()

    # Bad signature → 401 before any parsing.
    try:
        sf2 = await _setup_db()
        raw, _sig = _signed(_seed_payload("subscription_created", "evt-sig"))
        async with sf2() as s:
            await handle_lemonsqueezy_webhook(_FakeRequest(raw, "0" * 64), s)
        check("bad signature rejected", False)
    except fastapi.HTTPException as e:
        check(f"bad signature rejected (got {e.status_code})", e.status_code == 401)

    # Malformed JSON → 400.
    try:
        sf3 = await _setup_db()
        bad = b"{not json"
        bad_sig = hmac.new(b"whsec_test_k", bad, hashlib.sha256).hexdigest()
        async with sf3() as s:
            await handle_lemonsqueezy_webhook(_FakeRequest(bad, bad_sig), s)
        check("malformed JSON rejected", False)
    except fastapi.HTTPException as e:
        check(f"malformed JSON rejected (got {e.status_code})", e.status_code == 400)

    # Missing custom_data.user_id → ignored.
    res = await _call(_seed_payload("subscription_created", "evt-nouser", with_user=False))
    check("missing user_id ignored",
          res.get("status") == "ignored" and "user_id" in res.get("reason", ""))

    # Unknown event name → success no-op.
    res = await _call(_seed_payload("order_created", "evt-unknown"))
    check("unknown event no-op success", res.get("status") == "success")

    # subscription_created upgrades tier + quota.
    res = await _call(_seed_payload("subscription_created", "evt-created"))
    check("created processed", res.get("status") == "success")
    sf4 = await _setup_db()
    async with sf4() as s:
        sub = (await s.execute(
            select(Subscription).where(Subscription.user_id == "user_wh_1")
        )).scalar_one_or_none()
        check("tier upgraded to pro", bool(sub) and sub.plan_tier == "pro")
        check("quota upgraded to 1500", bool(sub) and sub.monthly_minutes_quota == 1500)
        check("status active", bool(sub) and sub.status == "active")

    # subscription_cancelled flips status only.
    res = await _call(_seed_payload("subscription_cancelled", "evt-cancelled"))
    check("cancelled processed", res.get("status") == "success")
    sf5 = await _setup_db()
    async with sf5() as s:
        sub = (await s.execute(
            select(Subscription).where(Subscription.user_id == "user_wh_1")
        )).scalar_one_or_none()
        check("status cancelled", bool(sub) and sub.status == "cancelled")

    # Idempotency: same webhook_id replay returns already-processed.
    res = await _call(_seed_payload("subscription_created", "evt-created"))
    check("replay idempotent", "already processed" in res.get("message", ""))

    if PASSED == check_count_before:
        print("FAIL  no branch assertions ran")
        globals()["FAILED"] += 1


if __name__ == "__main__":
    test_verify_signature_fails_closed()
    test_tier_map()
    test_status_allowlist()
    asyncio.run(_run_branch_tests())
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
