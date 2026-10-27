"""
backend/payments.py — payment state transitions shared by the checkout
verify endpoint and the Razorpay webhook.

Every transition is a conditional UPDATE on the payments row, so the verify
call and the webhook (which routinely arrive within milliseconds of each other)
can never both grant — or both revoke — the same pass.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Payment, Subscription
from backend.plans import apply_purchase, get_plan, revoke_purchase
from backend.usage import rollover_if_needed

logger = logging.getLogger("norai")


async def _subscription_for(db: AsyncSession, user_id: str) -> Subscription:
    sub = (
        await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, status="trial", plan_tier="free",
                           monthly_minutes_quota=get_plan("free").minutes, used_minutes_this_month=0)
        db.add(sub)
        await db.flush()
    return sub


async def mark_paid(db: AsyncSession, order_id: str, payment_id: str, method: str | None = None) -> bool:
    """created/failed -> paid and grant the plan. Returns True if THIS call granted it.

    A failed attempt on an order can be followed by a successful retry in the
    same checkout session, so 'failed' is not terminal.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(Payment)
        .where(Payment.id == order_id, Payment.status.in_(("created", "failed")))
        .values(status="paid", razorpay_payment_id=payment_id, method=method,
                failure_reason=None, paid_at=now, updated_at=now)
    )
    if result.rowcount != 1:
        return False  # already paid/refunded, or unknown order

    payment = await db.get(Payment, order_id)
    sub = await _subscription_for(db, payment.user_id)
    rollover_if_needed(sub, now)
    apply_purchase(sub, get_plan(payment.plan_id), now)
    await db.commit()
    logger.info("payments: order %s paid (%s) -> %s plan for user %s",
                order_id, payment_id, payment.plan_id, payment.user_id)
    return True


async def mark_failed(db: AsyncSession, order_id: str, payment_id: str | None, reason: str | None) -> bool:
    """created -> failed (never downgrades a paid order)."""
    result = await db.execute(
        update(Payment)
        .where(Payment.id == order_id, Payment.status == "created")
        .values(status="failed", razorpay_payment_id=payment_id,
                failure_reason=(reason or "Payment failed")[:1000],
                updated_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return result.rowcount == 1


async def mark_refunded(db: AsyncSession, payment_id: str, refunded_paise: int) -> bool:
    """Record a refund; a FULL refund revokes the pass it bought.

    Partial refunds are recorded only — access is left to the operator.
    """
    payment = (
        await db.execute(select(Payment).where(Payment.razorpay_payment_id == payment_id))
    ).scalar_one_or_none()
    if payment is None:
        logger.warning("payments: refund for unknown payment %s", payment_id)
        return False

    now = datetime.now(timezone.utc)
    total = max(payment.refunded_paise or 0, refunded_paise)
    if total < payment.amount_paise:
        await db.execute(
            update(Payment).where(Payment.id == payment.id).values(refunded_paise=total, updated_at=now)
        )
        await db.commit()
        return False

    result = await db.execute(
        update(Payment)
        .where(Payment.id == payment.id, Payment.status == "paid")
        .values(status="refunded", refunded_paise=total, updated_at=now)
    )
    if result.rowcount != 1:
        await db.commit()
        return False
    sub = await _subscription_for(db, payment.user_id)
    revoke_purchase(sub, get_plan(payment.plan_id), now)
    await db.commit()
    logger.info("payments: order %s fully refunded -> revoked %s pass for user %s",
                payment.id, payment.plan_id, payment.user_id)
    return True
