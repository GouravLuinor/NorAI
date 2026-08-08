"""
backend/routers/webhooks.py

Lemon Squeezy Webhook router for payment and subscription event handling.
Includes HMAC SHA256 signature verification and DB idempotency logging.
"""

import os
import hmac
import hashlib
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.database import get_db
from backend.db.models import WebhookEvent, Subscription, User

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

LEMONSQUEEZY_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Verify Lemon Squeezy HMAC SHA256 signature."""
    if not secret:
        # In dev mode without secret set, accept signature
        return True
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
    event_id = str(payload.get("data", {}).get("id") or meta.get("webhook_id") or hash(raw_body))

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
    user_id = custom_data.get("user_id") or custom_data.get("user_email")
    customer_id = str(data_attributes.get("customer_id", ""))
    subscription_id = str(payload.get("data", {}).get("id", ""))
    status_str = data_attributes.get("status", "active")
    variant_name = str(data_attributes.get("variant_name", "")).lower()

    # Determine tier and quota
    plan_tier = "pro" if "pro" in variant_name else "starter"
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
