"""
backend/routers/billing.py — plans, quota, Razorpay checkout, and usage/cost endpoints.

The app mounts this router with no prefix, so paths are unchanged.

Checkout flow (Razorpay Standard Checkout, one-time orders):
  1. POST /billing/razorpay/order   -> server creates the order (amount comes
     from backend/plans.py, never from the client) and a `payments` row.
  2. The browser opens Razorpay Checkout (UPI / cards / netbanking / wallets).
  3. POST /billing/razorpay/verify  -> server checks the checkout signature,
     confirms the payment with Razorpay, and grants the plan.
  4. The `order.paid` webhook does the same grant server-to-server, so a closed
     tab after paying still upgrades the account. backend/payments.py makes the
     two paths idempotent.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from backend import razorpay_client
from backend.auth import get_current_user, get_current_user_optional
from backend.db.database import get_db
from backend.db.models import Payment, Subscription, UsageLog, User
from backend.payments import mark_failed, mark_paid
from backend.plans import PLANS, get_plan
from backend.usage import rollover_if_needed

router = APIRouter()
logger = logging.getLogger("norai")

_RZP_ID = r"^[A-Za-z0-9_]{1,64}$"


def _payments_enabled() -> bool:
    # Read at call time so tests (and a hot-reloaded .env) see the current value.
    return bool(config.ENABLE_PAYMENTS and config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET)


async def _load_subscription(db: AsyncSession, user_id: str) -> Optional[Subscription]:
    """The user's subscription with an expired pass already rolled back to Free."""
    try:
        sub = (
            await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        ).scalar_one_or_none()
        # Roll the period forward BEFORE reporting usage, else an expired
        # period/pass shows a permanently exhausted quota in the UI.
        if sub is not None and rollover_if_needed(sub):
            await db.commit()
        return sub
    except Exception as exc:
        logger.warning("DB lookup failed for subscription of %s: %s", user_id, exc)
        return None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@router.get("/billing/plans")
async def list_plans():
    """Public plan catalogue for the pricing page (no auth)."""
    return {
        "currency": "INR",
        "payments_enabled": _payments_enabled(),
        "plans": [p.public() for p in PLANS.values()],
    }


@router.get("/quota")
async def get_user_quota(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return user's active plan tier and remaining lecture minutes."""
    sub = await _load_subscription(db, user.id)
    plan = get_plan(sub.plan_tier if sub else "free")
    quota = sub.monthly_minutes_quota if sub else plan.minutes
    used = sub.used_minutes_this_month if sub else 0

    return {
        "user_id": user.id,
        "email": user.email,
        "plan_tier": plan.id,
        "subscription_status": sub.status if sub else "trial",
        "monthly_minutes_quota": quota,
        "used_minutes_this_month": used,
        "remaining_minutes": max(0, quota - used),
        "max_lecture_minutes": plan.max_lecture_min,
        "current_period_end": _iso(sub.current_period_end) if sub else None,
        "is_anonymous": user.is_anonymous,
    }


async def _billing_state(db: AsyncSession, user: User) -> dict:
    sub = await _load_subscription(db, user.id)
    plan = get_plan(sub.plan_tier if sub else "free")
    quota = sub.monthly_minutes_quota if sub else plan.minutes
    used = sub.used_minutes_this_month if sub else 0

    payments = []
    try:
        rows = (
            await db.execute(
                select(Payment)
                .where(Payment.user_id == user.id, Payment.status != "created")
                .order_by(Payment.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        payments = [
            {
                "order_id": p.id,
                "plan_id": p.plan_id,
                "plan_name": get_plan(p.plan_id).name,
                "amount_inr": p.amount_paise / 100,
                "status": p.status,
                "method": p.method,
                "failure_reason": p.failure_reason,
                "refunded_inr": (p.refunded_paise or 0) / 100,
                "created_at": _iso(p.created_at),
                "paid_at": _iso(p.paid_at),
            }
            for p in rows
        ]
    except Exception as exc:
        logger.warning("DB lookup failed for payments of %s: %s", user.id, exc)

    return {
        "user_id": user.id,
        "email": user.email,
        "is_anonymous": user.is_anonymous,
        "plan_tier": plan.id,
        "plan": plan.public(),
        "subscription_status": sub.status if sub else "trial",
        "payments_enabled": _payments_enabled(),
        "monthly_minutes_quota": quota,
        "used_minutes_this_month": used,
        "remaining_minutes": max(0, quota - used),
        "current_period_end": _iso(sub.current_period_end) if sub else None,
        "payments": payments,
    }


@router.get("/billing")
async def get_billing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The user's plan, remaining minutes, pass expiry, and payment history."""
    return await _billing_state(db, user)


class OrderRequest(BaseModel):
    plan_id: str = Field(..., min_length=1, max_length=32)


@router.post("/billing/razorpay/order")
async def create_razorpay_order(
    body: OrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay order for a plan. The amount is set server-side."""
    if not _payments_enabled():
        raise HTTPException(status_code=503, detail="Payments are not enabled yet.")
    if user.is_anonymous:
        raise HTTPException(status_code=403, detail="Create an account before buying a plan.")
    plan = PLANS.get(body.plan_id)
    if plan is None or not plan.purchasable:
        raise HTTPException(status_code=400, detail="Unknown or free plan.")

    receipt = f"norai_{uuid.uuid4().hex[:24]}"
    try:
        order = await razorpay_client.create_order(
            plan.amount_paise, receipt, {"user_id": user.id, "plan_id": plan.id}
        )
    except razorpay_client.RazorpayError as exc:
        logger.error("razorpay: order creation failed for %s: %s", user.id, exc)
        raise HTTPException(status_code=502, detail="Could not start the payment. Please try again.")

    db.add(Payment(id=order["id"], user_id=user.id, plan_id=plan.id,
                   amount_paise=plan.amount_paise, currency="INR", status="created"))
    await db.commit()

    return {
        "order_id": order["id"],
        "amount": plan.amount_paise,
        "currency": "INR",
        "key_id": config.RAZORPAY_KEY_ID,
        "plan": plan.public(),
        "prefill": {"email": user.email or "", "name": user.full_name or ""},
    }


class VerifyRequest(BaseModel):
    razorpay_order_id: str = Field(..., pattern=_RZP_ID)
    razorpay_payment_id: str = Field(..., pattern=_RZP_ID)
    razorpay_signature: str = Field(..., min_length=1, max_length=256)


@router.post("/billing/razorpay/verify")
async def verify_razorpay_payment(
    body: VerifyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a completed Checkout and grant the plan (idempotent with the webhook)."""
    payment = await db.get(Payment, body.razorpay_order_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if not razorpay_client.verify_payment_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        logger.warning("razorpay: bad checkout signature for order %s (user %s)", payment.id, user.id)
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    if payment.status in ("paid", "refunded"):
        return {"granted": False, **await _billing_state(db, user)}

    # The signature proves Razorpay authorised this payment for this order.
    # Confirm amount/state with the API too; if Razorpay is unreachable the
    # signature alone is enough, and the order.paid webhook reconciles later.
    method = None
    try:
        rp = await razorpay_client.fetch_payment(body.razorpay_payment_id)
        if rp.get("order_id") != payment.id or int(rp.get("amount", 0)) != payment.amount_paise:
            logger.error("razorpay: payment %s does not match order %s", body.razorpay_payment_id, payment.id)
            raise HTTPException(status_code=400, detail="Payment verification failed.")
        method = rp.get("method")
        status = rp.get("status")
        if status == "failed":
            await mark_failed(db, payment.id, body.razorpay_payment_id, rp.get("error_description"))
            raise HTTPException(status_code=402, detail=rp.get("error_description") or "Payment failed.")
        if status == "authorized":
            # Auto-capture is off in the dashboard: capture it ourselves.
            await razorpay_client.capture_payment(body.razorpay_payment_id, payment.amount_paise)
    except razorpay_client.RazorpayError as exc:
        logger.warning("razorpay: could not confirm payment %s (%s); trusting the signature",
                       body.razorpay_payment_id, exc)

    granted = await mark_paid(db, payment.id, body.razorpay_payment_id, method)
    return {"granted": granted, **await _billing_state(db, user)}


@router.get("/usage")
async def get_usage(
    period: str = "month",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """P6.5: usage/cost dashboard aggregates over the user's UsageLog rows.

    Returned period is calendar-month by default (`period=today` for the
    current day, `period=month` default). All figures are derived from the
    metered UsageLog rows; `estimated_cost_usd` for embedding stages is an
    estimate (billable chars / 4) and the API flags `is_estimated`.
    """
    if period not in ("month", "today"):
        period = "month"
    if not user:
        return {
            "is_anonymous": True,
            "totals": {"api_calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "minutes": 0},
            "by_stage": [],
            "by_day": [],
            "by_lecture": [],
            "period": period,
            "is_estimated": False,
        }

    now = datetime.now(timezone.utc)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    scope = (
        select(
            func.coalesce(func.sum(UsageLog.calls), 0).label("calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0.0).label("cost_usd"),
        ).where(
            UsageLog.user_id == user.id,
            UsageLog.created_at >= start,
        )
    )
    totals_row = (await db.execute(scope)).one()

    # `is_estimated`: any embed-stage row in the period.
    embed_hit = await db.execute(
        select(UsageLog.id).where(
            UsageLog.user_id == user.id,
            UsageLog.created_at >= start,
            UsageLog.stage == "embed",
        ).limit(1)
    )
    is_estimated = embed_hit.first() is not None

    _agg_cols = (
        UsageLog.stage,
        func.coalesce(func.sum(UsageLog.calls), 0).label("calls"),
        func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0.0).label("cost_usd"),
    )
    _lec_agg_cols = (
        UsageLog.lecture_id,
        func.coalesce(func.sum(UsageLog.calls), 0).label("calls"),
        func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0.0).label("cost_usd"),
    )

    by_stage_rows = (
        await db.execute(
            select(*_agg_cols)
            .where(UsageLog.user_id == user.id, UsageLog.created_at >= start)
            .group_by(UsageLog.stage)
            .order_by(func.sum(UsageLog.estimated_cost_usd).desc())
        )
    ).all()
    by_stage_list = [
        {
            "stage": str(r.stage),
            "calls": int(r.calls),
            "input_tokens": int(r.input_tokens),
            "output_tokens": int(r.output_tokens),
            "cost_usd": float(r.cost_usd),
        }
        for r in by_stage_rows
    ]

    # Day bucketing is dialect-specific (strftime vs to_char).
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        day_key = func.to_char(UsageLog.created_at, "YYYY-MM-DD")
    else:
        day_key = func.strftime("%Y-%m-%d", UsageLog.created_at)

    by_day_rows = (
        await db.execute(
            select(
                day_key.label("day"),
                func.coalesce(func.sum(UsageLog.calls), 0).label("calls"),
                func.coalesce(func.sum(UsageLog.estimated_cost_usd), 0.0).label("cost_usd"),
                func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_tokens"),
            )
            .where(UsageLog.user_id == user.id, UsageLog.created_at >= start)
            .group_by(day_key)
            .order_by(day_key)
        )
    ).all()
    by_day_list = [
        {
            "date": str(r.day) if r.day is not None else "unknown",
            "calls": int(r.calls),
            "cost_usd": float(r.cost_usd),
            "input_tokens": int(r.input_tokens),
            "output_tokens": int(r.output_tokens),
        }
        for r in by_day_rows
    ]

    by_lec_rows = (
        await db.execute(
            select(*_lec_agg_cols)
            .where(UsageLog.user_id == user.id, UsageLog.created_at >= start)
            .group_by(UsageLog.lecture_id)
            .order_by(func.sum(UsageLog.estimated_cost_usd).desc())
        )
    ).all()
    by_lecture_list = [
        {
            "lecture_id": str(r.lecture_id),
            "calls": int(r.calls),
            "cost_usd": float(r.cost_usd),
            "input_tokens": int(r.input_tokens),
            "output_tokens": int(r.output_tokens),
        }
        for r in by_lec_rows
    ]

    # Quota minutes consumed this month (for the summary card).
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    minutes = sub.used_minutes_this_month if sub else 0

    return {
        "user_id": str(user.id) if user else None,
        "is_anonymous": user.is_anonymous if user else True,
        "period": period,
        "is_estimated": is_estimated,
        "totals": {
            "api_calls": int(totals_row.calls),
            "input_tokens": int(totals_row.input_tokens),
            "output_tokens": int(totals_row.output_tokens),
            "cost_usd": round(float(totals_row.cost_usd), 6),
            "minutes": minutes,
        },
        "by_stage": by_stage_list,
        "by_day": by_day_list,
        "by_lecture": by_lecture_list,
    }
