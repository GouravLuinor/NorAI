"""
Standalone test: Razorpay webhook signature checks, payment state transitions
(paid / failed / refunded), idempotency against duplicate deliveries and the
verify-vs-webhook race, and the plan grant/revoke rules in backend/plans.py.

Run directly: venv/bin/python backend/test_webhooks.py
"""

import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["NORAI_ALLOW_UNSIGNED_WEBHOOKS"] = "0"

# Real async session on a throwaway SQLite file, set BEFORE backend.db.database
# is imported anywhere. Force-assign: a shared runner DATABASE_URL accumulates
# rows across suite runs and trips UNIQUE constraints here.
_TMP_DB = "/tmp/norai_test_webhooks.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"

import asyncio

import fastapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import config
from backend import razorpay_client
from backend.db.database import Base, engine
from backend.db.models import Payment, Subscription, User, WebhookEvent
from backend.payments import mark_failed, mark_paid, mark_refunded
from backend.plans import FREE, PRO, STARTER, apply_purchase, revoke_purchase
from backend.routers.webhooks import handle_razorpay_webhook
from backend.usage import rollover_if_needed

WEBHOOK_SECRET = "whsec_test_k"
KEY_SECRET = "rzp_secret_test"
config.RAZORPAY_WEBHOOK_SECRET = WEBHOOK_SECRET
config.RAZORPAY_KEY_SECRET = KEY_SECRET

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


# ── signatures ───────────────────────────────────────────────────────────────

def _hmac(secret: str, msg: bytes) -> str:
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def test_signatures():
    sig = _hmac(KEY_SECRET, b"order_1|pay_1")
    check("checkout signature accepted", razorpay_client.verify_payment_signature("order_1", "pay_1", sig))
    check("checkout signature bound to payment id",
          not razorpay_client.verify_payment_signature("order_1", "pay_2", sig))
    check("checkout signature bound to order id",
          not razorpay_client.verify_payment_signature("order_2", "pay_1", sig))

    body = b'{"event":"order.paid"}'
    wsig = _hmac(WEBHOOK_SECRET, body)
    check("webhook signature accepted", razorpay_client.verify_webhook_signature(body, wsig))
    check("tampered webhook body rejected", not razorpay_client.verify_webhook_signature(b'{"event":"x"}', wsig))

    saved = config.RAZORPAY_KEY_SECRET, config.RAZORPAY_WEBHOOK_SECRET
    config.RAZORPAY_KEY_SECRET = config.RAZORPAY_WEBHOOK_SECRET = ""
    try:
        check("empty key secret fails closed",
              not razorpay_client.verify_payment_signature("order_1", "pay_1", _hmac("", b"order_1|pay_1")))
        check("empty webhook secret fails closed",
              not razorpay_client.verify_webhook_signature(body, _hmac("", body)))
    finally:
        config.RAZORPAY_KEY_SECRET, config.RAZORPAY_WEBHOOK_SECRET = saved


# ── plan rules (pure) ────────────────────────────────────────────────────────

class _Sub:
    def __init__(self, tier="free", status="trial", quota=45, used=0, end=None):
        self.plan_tier, self.status = tier, status
        self.monthly_minutes_quota, self.used_minutes_this_month = quota, used
        self.current_period_start, self.current_period_end = None, end
        self.created_at = None


def test_plan_rules():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)

    s = _Sub(used=30)
    apply_purchase(s, STARTER, now)
    check("free -> starter grants 300 min", s.plan_tier == "starter" and s.monthly_minutes_quota == 300)
    check("purchase resets usage", s.used_minutes_this_month == 0)
    check("pass lasts 30 days", s.current_period_end == now + timedelta(days=30))

    s.used_minutes_this_month = 100
    apply_purchase(s, STARTER, now + timedelta(days=10))
    check("same plan carries unused minutes", s.monthly_minutes_quota == 300 + 200)
    check("same plan extends the end date", s.current_period_end == now + timedelta(days=60))

    s.used_minutes_this_month = 0
    upgrade_at = now + timedelta(days=20)
    apply_purchase(s, PRO, upgrade_at)
    check("upgrade carries minutes into pro", s.plan_tier == "pro" and s.monthly_minutes_quota == 1200 + 500)
    check("upgrade starts a fresh period", s.current_period_end == upgrade_at + timedelta(days=30))

    lapsed = _Sub(tier="starter", status="active", quota=300, used=10, end=now - timedelta(days=1))
    apply_purchase(lapsed, STARTER, now)
    check("lapsed pass does not carry minutes", lapsed.monthly_minutes_quota == 300)

    r = _Sub()
    apply_purchase(r, PRO, now)
    revoke_purchase(r, PRO, now + timedelta(days=1))
    check("full refund of only pass -> free", r.plan_tier == "free" and r.monthly_minutes_quota == FREE.minutes)
    check("refund marks status refunded", r.status == "refunded")

    st = _Sub()
    apply_purchase(st, STARTER, now)
    apply_purchase(st, STARTER, now)  # stacked: 600 min, 60 days
    revoke_purchase(st, STARTER, now + timedelta(days=1))
    check("refund of one stacked pass keeps the other",
          st.plan_tier == "starter" and st.monthly_minutes_quota == 300
          and st.current_period_end == now + timedelta(days=30))

    exp = _Sub(tier="pro", status="active", quota=1200, used=50, end=now - timedelta(seconds=1))
    check("expired pass rolls over", rollover_if_needed(exp, now) is True)
    check("expired pass falls back to free",
          exp.plan_tier == "free" and exp.monthly_minutes_quota == FREE.minutes and exp.status == "expired")
    active = _Sub(tier="pro", status="active", quota=1200, used=50, end=now + timedelta(days=3))
    check("active pass untouched", rollover_if_needed(active, now) is False and active.used_minutes_this_month == 50)


# ── DB-backed: payment transitions + webhook handler ─────────────────────────

USER = "user_rzp_1"


async def _sf():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(bind=engine, expire_on_commit=False)


async def _seed_order(order_id: str, plan=STARTER):
    sf = await _sf()
    async with sf() as s:
        if await s.get(User, USER) is None:
            s.add(User(id=USER, email="rzp@example.com", is_anonymous=False))
            s.add(Subscription(user_id=USER, status="trial", plan_tier="free",
                               monthly_minutes_quota=45, used_minutes_this_month=0))
        s.add(Payment(id=order_id, user_id=USER, plan_id=plan.id,
                      amount_paise=plan.amount_paise, status="created"))
        await s.commit()


async def _reset_sub():
    sf = await _sf()
    async with sf() as s:
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == USER))).scalar_one()
        sub.plan_tier, sub.status, sub.monthly_minutes_quota = "free", "trial", 45
        sub.used_minutes_this_month, sub.current_period_end = 0, None
        await s.commit()


async def _sub():
    sf = await _sf()
    async with sf() as s:
        return (await s.execute(select(Subscription).where(Subscription.user_id == USER))).scalar_one()


async def _payment(order_id: str) -> Payment:
    sf = await _sf()
    async with sf() as s:
        return await s.get(Payment, order_id)


class _FakeRequest:
    def __init__(self, body: bytes, signature: str, event_id: str | None):
        self._body = body
        self.headers = {"X-Razorpay-Signature": signature}
        if event_id:
            self.headers["x-razorpay-event-id"] = event_id

    async def body(self) -> bytes:
        return self._body

    async def json(self):
        return json.loads(self._body)  # mirrors Starlette: raises on bad JSON


async def _deliver(payload: dict, event_id: str | None, signature: str | None = None):
    sf = await _sf()
    raw = json.dumps(payload).encode()
    sig = signature if signature is not None else _hmac(WEBHOOK_SECRET, raw)
    async with sf() as s:
        res = await handle_razorpay_webhook(_FakeRequest(raw, sig, event_id), s)
        await s.commit()  # what the real get_db dependency does on success
        return res


def _paid_event(order_id: str, payment_id: str, amount: int) -> dict:
    return {
        "event": "order.paid",
        "payload": {
            "payment": {"entity": {"id": payment_id, "order_id": order_id, "amount": amount,
                                   "status": "captured", "method": "upi"}},
            "order": {"entity": {"id": order_id, "amount": amount, "status": "paid"}},
        },
    }


async def _run_db_tests():
    # Bad signature → 401 before anything is parsed.
    try:
        await _deliver({"event": "order.paid"}, "evt_bad", signature="0" * 64)
        check("bad webhook signature rejected", False)
    except fastapi.HTTPException as e:
        check(f"bad webhook signature rejected (got {e.status_code})", e.status_code == 401)

    # No secret configured → 503 (fails closed).
    config.RAZORPAY_WEBHOOK_SECRET = ""
    try:
        await _deliver({"event": "order.paid"}, "evt_nosecret", signature="")
        check("missing webhook secret -> 503", False)
    except fastapi.HTTPException as e:
        check(f"missing webhook secret -> 503 (got {e.status_code})", e.status_code == 503)
    finally:
        config.RAZORPAY_WEBHOOK_SECRET = WEBHOOK_SECRET

    # Malformed JSON → 400.
    sf = await _sf()
    bad = b"{not json"
    try:
        async with sf() as s:
            await handle_razorpay_webhook(_FakeRequest(bad, _hmac(WEBHOOK_SECRET, bad), "evt_badjson"), s)
        check("malformed JSON rejected", False)
    except fastapi.HTTPException as e:
        check(f"malformed JSON rejected (got {e.status_code})", e.status_code == 400)

    # order.paid grants the plan.
    await _seed_order("order_A")
    res = await _deliver(_paid_event("order_A", "pay_A", STARTER.amount_paise), "evt_A1")
    sub = await _sub()
    p = await _payment("order_A")
    check("order.paid processed", res.get("status") == "success")
    check("order.paid grants starter", sub.plan_tier == "starter" and sub.monthly_minutes_quota == 300)
    check("payment marked paid with method", p.status == "paid" and p.method == "upi" and p.razorpay_payment_id == "pay_A")

    # Duplicate delivery (same event id) is a no-op.
    res = await _deliver(_paid_event("order_A", "pay_A", STARTER.amount_paise), "evt_A1")
    check("duplicate delivery acknowledged", "already processed" in res.get("message", ""))
    # payment.captured for the same order (different event id) must not grant twice.
    cap = _paid_event("order_A", "pay_A", STARTER.amount_paise)
    cap["event"] = "payment.captured"
    await _deliver(cap, "evt_A2")
    sub = await _sub()
    check("order.paid + payment.captured grant once", sub.monthly_minutes_quota == 300)

    # Verify endpoint and webhook racing on the same order grant exactly once.
    await _reset_sub()
    await _seed_order("order_B")
    sf = await _sf()

    async def _grant():
        async with sf() as s:
            return await mark_paid(s, "order_B", "pay_B", "card")

    results = await asyncio.gather(_grant(), _grant(), _grant())
    sub = await _sub()
    check("concurrent grants: exactly one wins", sorted(results) == [False, False, True])
    check("concurrent grants: quota granted once", sub.monthly_minutes_quota == 300)

    # payment.failed marks the order failed and grants nothing; a later retry succeeds.
    await _reset_sub()
    await _seed_order("order_C")
    failed = {"event": "payment.failed", "payload": {"payment": {"entity": {
        "id": "pay_C1", "order_id": "order_C", "status": "failed",
        "error_description": "Payment declined by bank"}}}}
    await _deliver(failed, "evt_C1")
    p = await _payment("order_C")
    sub = await _sub()
    check("payment.failed recorded", p.status == "failed" and p.failure_reason == "Payment declined by bank")
    check("failed payment grants nothing", sub.plan_tier == "free")
    await _deliver(_paid_event("order_C", "pay_C2", STARTER.amount_paise), "evt_C2")
    sub = await _sub()
    check("retry after failure grants the plan", sub.plan_tier == "starter")
    # A late payment.failed for the first attempt must not undo the paid order.
    async with sf() as s:
        check("late failure cannot downgrade a paid order", await mark_failed(s, "order_C", "pay_C1", "late") is False)
    check("order still paid", (await _payment("order_C")).status == "paid")

    # Partial refund: recorded, access kept.
    refund = lambda amt, eid: {"event": "refund.processed", "payload": {
        "refund": {"entity": {"id": f"rfnd_{eid}", "payment_id": "pay_C2", "amount": amt}},
        "payment": {"entity": {"id": "pay_C2", "order_id": "order_C", "amount_refunded": amt}}}}
    await _deliver(refund(5000, "p1"), "evt_R1")
    p = await _payment("order_C")
    sub = await _sub()
    check("partial refund recorded", p.status == "paid" and p.refunded_paise == 5000)
    check("partial refund keeps access", sub.plan_tier == "starter")

    # Full refund (cumulative) revokes the pass.
    await _deliver(refund(STARTER.amount_paise, "full"), "evt_R2")
    p = await _payment("order_C")
    sub = await _sub()
    check("full refund marks payment refunded", p.status == "refunded")
    check("full refund revokes the plan", sub.plan_tier == "free" and sub.status == "refunded")
    async with sf() as s:
        check("second full refund is a no-op", await mark_refunded(s, "pay_C2", STARTER.amount_paise) is False)

    # Unknown order / unknown event are acknowledged (no retries storm), not crashes.
    res = await _deliver(_paid_event("order_missing", "pay_X", 100), "evt_X")
    check("unknown order acknowledged", res.get("status") == "success")
    res = await _deliver({"event": "subscription.charged", "payload": {}}, "evt_Y")
    check("unhandled event acknowledged", res.get("status") == "success")
    async with sf() as s:
        check("events recorded for idempotency", await s.get(WebhookEvent, "rzp:evt_Y") is not None)


if __name__ == "__main__":
    test_signatures()
    test_plan_rules()
    asyncio.run(_run_db_tests())
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
