"""
backend/routers/webhooks.py

Razorpay webhook: the server-to-server source of truth for payments.

Configure in the Razorpay dashboard (Settings -> Webhooks):
  URL     https://<your-domain>/api/webhooks/razorpay
  Secret  RAZORPAY_WEBHOOK_SECRET
  Events  order.paid, payment.captured, payment.failed, refund.processed

Signature: HMAC-SHA256 of the raw body with the webhook secret, sent in
X-Razorpay-Signature. Razorpay retries non-2xx deliveries and may deliver an
event more than once, so every event is recorded in `webhook_events` keyed by
x-razorpay-event-id and the payment transitions themselves are idempotent.
"""

import hashlib
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import config
from backend import razorpay_client
from backend.db.database import get_db
from backend.db.models import WebhookEvent
from backend.payments import mark_failed, mark_paid, mark_refunded

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _allow_unsigned() -> bool:
    # Dev-only escape hatch. NEVER set in production — it disables signature verification.
    return os.environ.get("NORAI_ALLOW_UNSIGNED_WEBHOOKS", "") == "1"


def _entity(payload: dict, name: str) -> dict:
    return ((payload.get("payload") or {}).get(name) or {}).get("entity") or {}


@router.post("/razorpay")
async def handle_razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    if config.RAZORPAY_WEBHOOK_SECRET:
        signature = request.headers.get("X-Razorpay-Signature", "")
        if not razorpay_client.verify_webhook_signature(raw_body, signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    elif not _allow_unsigned():
        logger.error(
            "Rejecting webhook: RAZORPAY_WEBHOOK_SECRET is not configured. "
            "Set it (or NORAI_ALLOW_UNSIGNED_WEBHOOKS=1 for local dev only)."
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Webhook secret not configured")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event = str(payload.get("event", ""))
    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw_body).hexdigest()
    key = f"rzp:{event_id}"[:128]

    if await db.get(WebhookEvent, key) is not None:
        return {"status": "success", "message": "Event already processed"}

    payment = _entity(payload, "payment")
    order = _entity(payload, "order")

    if event in ("order.paid", "payment.captured"):
        order_id = order.get("id") or payment.get("order_id")
        if order_id and payment.get("id"):
            await mark_paid(db, order_id, payment["id"], payment.get("method"))
    elif event == "payment.failed":
        if payment.get("order_id"):
            await mark_failed(db, payment["order_id"], payment.get("id"),
                              payment.get("error_description"))
    elif event == "refund.processed":
        refund = _entity(payload, "refund")
        payment_id = refund.get("payment_id") or payment.get("id")
        # payment.amount_refunded is the cumulative total; refund.amount is just this one.
        refunded = int(payment.get("amount_refunded") or refund.get("amount") or 0)
        if payment_id and refunded > 0:
            await mark_refunded(db, payment_id, refunded)
    else:
        logger.info("razorpay webhook: ignoring event %s", event)

    # Recorded after processing: if processing raised, Razorpay's retry runs it again
    # (the transitions are idempotent, so a partial first attempt is safe).
    db.add(WebhookEvent(id=key, event_name=event or "unknown", payload=payload, processed=True))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # a concurrent duplicate delivery recorded it first
    return {"status": "success", "event": event}
