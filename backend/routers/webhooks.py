"""
backend/routers/webhooks.py

Lemon Squeezy Webhook router for payment and subscription event handling.
Includes HMAC SHA256 signature verification and DB idempotency logging.
"""

import os
import hmac
import hashlib
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import get_db
from backend.db.models import WebhookEvent, Subscription, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

LEMONSQUEEZY_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")
# Dev-only escape hatch. NEVER set in production — it disables signature verification.
ALLOW_UNSIGNED_WEBHOOKS = os.environ.get("NORAI_ALLOW_UNSIGNED_WEBHOOKS", "") == "1"

VALID_SUBSCRIPTION_STATUSES = {"trial", "active", "cancelled", "past_due", "paused"}

# Exact-match variant name -> plan tier. Unknown variants default to "starter".
PLAN_TIER_BY_VARIANT = {
    "pro": "pro",
    "pro-student": "pro",
    "pro student": "pro",
    "starter": "starter",
    "free": "free",
}


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Verify Lemon Squeezy HMAC SHA256 signature. Fails closed when no secret is set."""
    if not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@router.post("/lemonsqueezy")
async def handle_lemonsqueezy_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Lemon Squeezy webhook handler for subscription lifecycle events.
    """
    if not LEMONSQUEEZY_WEBHOOK_SECRET:
        if not ALLOW_UNSIGNED_WEBHOOKS:
            logger.error(
                "Rejecting webhook: LEMONSQUEEZY_WEBHOOK_SECRET is not configured. "
                "Set it (or NORAI_ALLOW_UNSIGNED_WEBHOOKS=1 for local dev only)."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook secret not configured",
            )

    raw_body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not verify_signature(raw_body, signature, LEMONSQUEEZY_WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature header",
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    meta = payload.get("meta", {})
    event_name = meta.get("event_name", "")
    custom_data = meta.get("custom_data", {})
    event_id = str(
        payload.get("data", {}).get("id")
        or meta.get("webhook_id")
        or hashlib.sha256(raw_body).hexdigest()
    )

    # Check idempotency in database
    existing_event = await db.get(WebhookEvent, event_id)
    if existing_event:
        return {"status": "success", "message": "Event already processed"}

    # Record event
    webhook_event = WebhookEvent(
        id=event_id,
        event_name=event_name,
        payload=payload,
        processed=True,
    )
    db.add(webhook_event)

    # Process event types
    data_attributes = payload.get("data", {}).get("attributes", {})
    user_id = custom_data.get("user_id")
    if not user_id:
        logger.warning("Webhook %s missing custom_data.user_id — dropping event", event_name)
        await db.flush()
        return {"status": "ignored", "reason": "missing custom_data.user_id"}

    customer_id = str(data_attributes.get("customer_id", ""))
    subscription_id = str(payload.get("data", {}).get("id", ""))
    status_str = str(data_attributes.get("status", "active")).lower()
    if status_str not in VALID_SUBSCRIPTION_STATUSES:
        logger.warning("Webhook %s: unknown status %r, defaulting to 'active'", event_name, status_str)
        status_str = "active"

    # Determine tier and quota (exact match; unknown variants default to starter)
    variant_name = str(data_attributes.get("variant_name", "")).strip().lower()
    plan_tier = PLAN_TIER_BY_VARIANT.get(variant_name, "starter")
    quota_minutes = 1500 if plan_tier == "pro" else 300  # Pro: 25 hrs (1500 mins), Starter: 5 hrs (300 mins)

    if user_id and event_name in ["subscription_created", "subscription_updated"]:
        # Find subscription by user_id
        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        sub = result.scalar_one_or_none()

        if sub:
            sub.status = status_str
            sub.plan_tier = plan_tier
            sub.monthly_minutes_quota = quota_minutes
            sub.lemon_squeezy_customer_id = customer_id
            sub.lemon_squeezy_subscription_id = subscription_id
            db.add(sub)

    elif user_id and event_name == "subscription_cancelled":
        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = "cancelled"
            db.add(sub)

    await db.flush()
    return {"status": "success", "event": event_name}
