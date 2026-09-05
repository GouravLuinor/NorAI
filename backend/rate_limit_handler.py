"""
backend/rate_limit_handler.py

Gemini Free-Tier Rate Limit & Downtime Handler.
Differentiates between:
1. Short-term RPM limits (15 Requests/Min) — handled silently by internal backoff/retries.
2. Daily quota exhaustion (500 Requests/Day) — aborts retries, triggers system cooldown,
   calculates seconds until Midnight US Pacific Time (00:00 PST/PDT), and serves structured
   HTTP 429 downtime responses.
"""

from __future__ import annotations

import logging
import threading
import time
import zoneinfo
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Canonical US Pacific timezone for Gemini API daily quota resets
_PACIFIC_TZ = zoneinfo.ZoneInfo("America/Los_Angeles")


def seconds_until_pacific_midnight() -> int:
    """Calculate exact seconds remaining until next Midnight US Pacific Time (00:00 PST/PDT)."""
    now_utc = datetime.now(timezone.utc)
    now_pacific = now_utc.astimezone(_PACIFIC_TZ)
    next_midnight_pacific = (now_pacific + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    next_midnight_utc = next_midnight_pacific.astimezone(timezone.utc)
    remaining = int((next_midnight_utc - now_utc).total_seconds())
    return max(1, remaining)


def is_daily_quota_exhausted(exc: BaseException | None) -> bool:
    """
    True if the exception indicates Gemini's daily quota (500 RPD) has been exhausted.
    Does NOT match transient short-term RPM limits.
    """
    if exc is None:
        return False

    msg = str(exc).lower()
    details = ""
    # Check for google-genai or google-api-core error details
    if hasattr(exc, "details"):
        details = str(getattr(exc, "details")).lower()
    elif hasattr(exc, "message"):
        details = str(getattr(exc, "message")).lower()

    combined = f"{msg} {details}"

    # Must indicate 429 or resource exhaustion
    has_quota_code = (
        "429" in combined
        or "resource_exhausted" in combined
        or "quota exceeded" in combined
        or "rate_limit_exceeded" in combined
    )
    if not has_quota_code:
        return False

    # Check for daily indicators
    daily_indicators = (
        "requests per day",
        "perday",
        "per day",
        "daily",
        "generaterequestsperday",
        "quota exceeded for quota metric 'queries' and limit 'queries per day'",
    )
    return any(ind in combined for ind in daily_indicators)


class GeminiDailyQuotaExceededException(HTTPException):
    """Structured HTTP 429 exception raised when Gemini's daily quota (500 RPD) is exhausted."""

    def __init__(self, retry_after_seconds: int | None = None, message: str | None = None):
        if retry_after_seconds is None:
            retry_after_seconds = seconds_until_pacific_midnight()
        self.limit_type = "rpd"
        self.retry_after_seconds = retry_after_seconds
        self.friendly_message = (
            message
            or "Daily system capacity reached. Free-tier quota resets at midnight Pacific Time."
        )
        super().__init__(
            status_code=429,
            detail={
                "error": "RATE_LIMIT_EXCEEDED",
                "limitType": "rpd",
                "retryAfterSeconds": self.retry_after_seconds,
                "message": self.friendly_message,
            },
        )


class GeminiCooldownTracker:
    """Thread-safe global tracker for Gemini daily quota exhaustion downtime."""

    _lock = threading.Lock()
    _downtime_until: float | None = None
    _message: str = ""

    @classmethod
    def record_daily_exhaustion(cls, retry_after_seconds: int | None = None, message: str | None = None):
        """Record an active system downtime window until next reset."""
        if retry_after_seconds is None:
            retry_after_seconds = seconds_until_pacific_midnight()
        with cls._lock:
            cls._downtime_until = time.time() + retry_after_seconds
            cls._message = (
                message
                or "Daily system capacity reached. Free-tier quota resets at midnight Pacific Time."
            )
            logger.warning(
                "Gemini daily quota exhausted. System in cooldown for %ds until Pacific Midnight.",
                retry_after_seconds,
            )

    @classmethod
    def is_downtime_active(cls) -> tuple[bool, int, str]:
        """Return (True, remaining_seconds, message) if in active downtime, else (False, 0, '')."""
        with cls._lock:
            if cls._downtime_until is None:
                return False, 0, ""
            remaining = int(cls._downtime_until - time.time())
            if remaining <= 0:
                cls._downtime_until = None
                cls._message = ""
                return False, 0, ""
            return True, remaining, cls._message

    @classmethod
    def clear_cooldown(cls):
        """Clear the cooldown (used in tests or manual overrides)."""
        with cls._lock:
            cls._downtime_until = None
            cls._message = ""
