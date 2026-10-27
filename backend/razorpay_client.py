"""
backend/razorpay_client.py — minimal Razorpay REST client + signature checks.

Talks to the Razorpay Orders/Payments API directly over httpx (already a
dependency) instead of pulling in the `razorpay` SDK. Keys come from env via
config.py; use rzp_test_… keys outside production.

Signatures (https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/):
  * checkout:  HMAC_SHA256(order_id + "|" + payment_id, key_secret)
  * webhooks:  HMAC_SHA256(raw_body, webhook_secret)  (X-Razorpay-Signature)
"""

from __future__ import annotations

import hashlib
import hmac

import httpx

import config

API_BASE = "https://api.razorpay.com/v1"
_TIMEOUT = httpx.Timeout(15.0)


class RazorpayError(Exception):
    """Razorpay API call failed (network error or non-2xx response)."""


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Checkout handler signature. Fails closed when the key secret is unset."""
    secret = config.RAZORPAY_KEY_SECRET
    if not (secret and order_id and payment_id and signature):
        return False
    expected = _hmac_hex(secret, f"{order_id}|{payment_id}".encode("utf-8"))
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Webhook signature over the raw request body. Fails closed without a secret."""
    secret = config.RAZORPAY_WEBHOOK_SECRET
    if not (secret and signature):
        return False
    return hmac.compare_digest(_hmac_hex(secret, raw_body), signature)


async def _request(method: str, path: str, json: dict | None = None) -> dict:
    auth = (config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET)
    try:
        async with httpx.AsyncClient(base_url=API_BASE, auth=auth, timeout=_TIMEOUT) as client:
            resp = await client.request(method, path, json=json)
    except httpx.HTTPError as exc:
        raise RazorpayError(f"Razorpay unreachable: {exc}") from exc
    if resp.status_code >= 400:
        try:
            desc = resp.json().get("error", {}).get("description", "")
        except ValueError:
            desc = resp.text[:200]
        raise RazorpayError(f"Razorpay {method} {path} -> {resp.status_code}: {desc}")
    return resp.json()


async def create_order(amount_paise: int, receipt: str, notes: dict) -> dict:
    return await _request(
        "POST",
        "/orders",
        {"amount": amount_paise, "currency": "INR", "receipt": receipt[:40], "notes": notes},
    )


async def fetch_payment(payment_id: str) -> dict:
    return await _request("GET", f"/payments/{payment_id}")


async def capture_payment(payment_id: str, amount_paise: int) -> dict:
    """Capture an `authorized` payment (only needed if auto-capture is off)."""
    return await _request(
        "POST", f"/payments/{payment_id}/capture", {"amount": amount_paise, "currency": "INR"}
    )
