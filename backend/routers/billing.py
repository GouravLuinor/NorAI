"""
backend/routers/billing.py — quota, billing, and usage/cost endpoints (P5.1).

Extracted verbatim from main.py; the app mounts this router with no prefix,
so paths are unchanged.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user, get_current_user_optional
from backend.db.database import get_db
from backend.db.models import Subscription, UsageLog, User
from backend.usage import rollover_if_needed
from config import (
    LEMONSQUEEZY_CHECKOUT_STARTER_URL,
    LEMONSQUEEZY_CHECKOUT_PRO_URL,
    LEMONSQUEEZY_CUSTOMER_PORTAL_URL,
)

router = APIRouter()


@router.get("/quota")
async def get_user_quota(
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return user's active plan tier and remaining monthly lecture minutes."""
    if not user:
        # Default anonymous trial quota
        return {
            "plan_tier": "free",
            "subscription_status": "trial",
            "monthly_minutes_quota": 15,
            "used_minutes_this_month": 0,
            "remaining_minutes": 15,
            "is_anonymous": True,
        }

    # Fetch user subscription
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()

    # P0 fix: roll the billing period forward BEFORE reporting usage, else an
    # expired period shows a permanently exhausted quota in the UI.
    if sub is not None and rollover_if_needed(sub):
        await db.commit()

    quota = sub.monthly_minutes_quota if sub else 15
    used = sub.used_minutes_this_month if sub else 0
    remaining = max(0, quota - used)
    plan_tier = sub.plan_tier if sub else "free"
    sub_status = sub.status if sub else "trial"

    return {
        "user_id": user.id,
        "email": user.email,
        "plan_tier": plan_tier,
        "subscription_status": sub_status,
        "monthly_minutes_quota": quota,
        "used_minutes_this_month": used,
        "remaining_minutes": remaining,
        "is_anonymous": user.is_anonymous,
    }


@router.get("/billing")
async def get_billing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the user's plan, usage, and Lemon Squeezy checkout/manage links.

    Checkout / portal URLs come from env (config.py) — they are null until the
    Lemon Squeezy store exists. `manage_url` is only offered to users who have
    an active Lemon Squeezy subscription id.
    """
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()

    plan_tier = sub.plan_tier if sub else "free"
    sub_status = sub.status if sub else "trial"
    quota = sub.monthly_minutes_quota if sub else 15
    used = sub.used_minutes_this_month if sub else 0
    remaining = max(0, quota - used)
    ls_sub_id = (sub.lemon_squeezy_subscription_id if sub else None) or None

    checkout_urls = {
        "starter": LEMONSQUEEZY_CHECKOUT_STARTER_URL or None,
        "pro": LEMONSQUEEZY_CHECKOUT_PRO_URL or None,
    }
    manage_url = LEMONSQUEEZY_CUSTOMER_PORTAL_URL or None

    return {
        "user_id": user.id,
        "email": user.email,
        "is_anonymous": user.is_anonymous,
        "plan_tier": plan_tier,
        "subscription_status": sub_status,
        "monthly_minutes_quota": quota,
        "used_minutes_this_month": used,
        "remaining_minutes": remaining,
        "lemon_squeezy_subscription_id": ls_sub_id,
        "checkout_urls": checkout_urls,
        "manage_url": manage_url,
    }


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
