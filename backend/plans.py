"""
backend/plans.py — the plan catalogue and the rules for granting/revoking it.

Single source of truth for what each plan costs and unlocks. The pricing page
(GET /billing/plans), order creation, quota checks in /process, and the
pipeline's duration gate all read from here.

Paid plans are prepaid 30-day passes bought as one-time Razorpay orders (UPI,
cards, netbanking, wallets) — no mandate/auto-debit setup. When a pass lapses
the account falls back to the free plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from backend.timeutil import ensure_utc
from config import FREE_MONTHLY_MINUTES, MAX_FREE_DURATION_MIN, PLAN_PRO_PRICE_INR, PLAN_STARTER_PRICE_INR


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    tagline: str
    price_inr: int              # whole rupees, GST-inclusive list price
    minutes: int                # lecture-minutes included per pass/period
    max_lecture_min: int        # longest single lecture accepted
    period_days: int
    features: tuple[str, ...] = field(default_factory=tuple)

    @property
    def amount_paise(self) -> int:
        return self.price_inr * 100

    @property
    def purchasable(self) -> bool:
        return self.price_inr > 0

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "price_inr": self.price_inr,
            "minutes": self.minutes,
            "max_lecture_min": self.max_lecture_min,
            "period_days": self.period_days,
            "features": list(self.features),
            "purchasable": self.purchasable,
        }


FREE = Plan(
    id="free",
    name="Free",
    tagline="Everything NorAI does, free. No card needed.",
    price_inr=0,
    minutes=FREE_MONTHLY_MINUTES,
    max_lecture_min=min(MAX_FREE_DURATION_MIN, FREE_MONTHLY_MINUTES),
    period_days=30,
    features=(
        f"{FREE_MONTHLY_MINUTES} lecture-minutes every 30 days",
        f"Lectures up to {min(MAX_FREE_DURATION_MIN, FREE_MONTHLY_MINUTES)} minutes long",
        "Study notes, revision sheet, quiz & flashcards",
        "Lecture-grounded AI tutor and PDF export",
    ),
)

STARTER = Plan(
    id="starter",
    name="Starter",
    tagline="For a regular weekly course load.",
    price_inr=PLAN_STARTER_PRICE_INR,
    minutes=300,
    max_lecture_min=90,
    period_days=30,
    features=(
        "300 lecture-minutes (5 hours) for 30 days",
        "Lectures up to 90 minutes long",
        "Everything in Free",
        "Unused minutes carry over when you buy again",
    ),
)

PRO = Plan(
    id="pro",
    name="Pro",
    tagline="For exam season and heavy semesters.",
    price_inr=PLAN_PRO_PRICE_INR,
    minutes=1200,
    max_lecture_min=180,
    period_days=30,
    features=(
        "1,200 lecture-minutes (20 hours) for 30 days",
        "Lectures up to 3 hours long",
        "Everything in Starter",
        "Lowest price per lecture-minute",
    ),
)

PLANS: dict[str, Plan] = {p.id: p for p in (FREE, STARTER, PRO)}


def get_plan(plan_id: str | None) -> Plan:
    """Plan for a tier id; unknown/legacy tiers resolve to Free."""
    return PLANS.get(plan_id or "free", FREE)


def _is_active_paid(sub, now: datetime) -> bool:
    end = ensure_utc(sub.current_period_end)
    return sub.plan_tier != "free" and sub.status == "active" and end is not None and end > now


def downgrade_to_free(sub, now: datetime, status: str = "expired") -> None:
    sub.plan_tier = FREE.id
    sub.status = status
    sub.monthly_minutes_quota = FREE.minutes
    sub.used_minutes_this_month = 0
    sub.current_period_start = now
    sub.current_period_end = None


def apply_purchase(sub, plan: Plan, now: datetime | None = None) -> None:
    """Grant a paid pass. Unused minutes of an active pass carry over.

    Same plan while active -> the pass is extended (end + period). A different
    plan (upgrade/downgrade) or a lapsed pass -> a fresh period starts now.
    """
    now = now or datetime.now(timezone.utc)
    carry = 0
    end = ensure_utc(sub.current_period_end)
    active = _is_active_paid(sub, now)
    if active:
        carry = max(0, (sub.monthly_minutes_quota or 0) - (sub.used_minutes_this_month or 0))
    period = timedelta(days=plan.period_days)

    sub.current_period_end = (end + period) if (active and sub.plan_tier == plan.id) else (now + period)
    sub.plan_tier = plan.id
    sub.status = "active"
    sub.monthly_minutes_quota = plan.minutes + carry
    sub.used_minutes_this_month = 0
    sub.current_period_start = now


def revoke_purchase(sub, plan: Plan, now: datetime | None = None) -> None:
    """Undo one fully refunded pass (stacked passes keep the remainder)."""
    now = now or datetime.now(timezone.utc)
    end = ensure_utc(sub.current_period_end)
    if sub.plan_tier == "free" or end is None:
        return
    new_end = end - timedelta(days=plan.period_days)
    new_quota = (sub.monthly_minutes_quota or 0) - plan.minutes
    if new_end <= now or new_quota <= 0:
        downgrade_to_free(sub, now, status="refunded")
    else:
        sub.current_period_end = new_end
        sub.monthly_minutes_quota = new_quota
