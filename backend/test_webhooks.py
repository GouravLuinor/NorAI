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


if __name__ == "__main__":
    test_verify_signature_fails_closed()
    test_tier_map()
    test_status_allowlist()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
