"""
backend/test_rate_limit_handler.py

Standalone tests for Gemini RPD daily quota exhaustion detection,
Pacific Midnight reset calculations, and cooldown fast-failing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
import zoneinfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.rate_limit_handler import (
    GeminiCooldownTracker,
    GeminiDailyQuotaExceededException,
    is_daily_quota_exhausted,
    seconds_until_pacific_midnight,
)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        print(f"  ✗ FAIL: {name}")


def test_is_daily_quota_exhausted():
    print("\n── Testing is_daily_quota_exhausted ──────────────────────────")

    # None and empty
    check("None returns False", is_daily_quota_exhausted(None) is False)
    check("Generic exception returns False", is_daily_quota_exhausted(RuntimeError("disk full")) is False)

    # 429 RPM should NOT be detected as daily
    rpm_err = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'Queries' and limit 'Queries per minute'")
    check("429 RPM returns False (silent retry)", is_daily_quota_exhausted(rpm_err) is False)

    # 429 RPD variations
    rpd_err1 = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric 'Queries' and limit 'Requests per day'")
    check("429 'Requests per day' returns True", is_daily_quota_exhausted(rpd_err1) is True)

    rpd_err2 = Exception("Resource has been exhausted (e.g. check quota). Daily quota exceeded.")
    check("429 'Daily quota exceeded' returns True", is_daily_quota_exhausted(rpd_err2) is True)

    rpd_err3 = Exception("429 RESOURCE_EXHAUSTED: PerDay limit reached for generateContent")
    check("429 'PerDay' returns True", is_daily_quota_exhausted(rpd_err3) is True)

    rpd_err4 = Exception("429 Quota exceeded: GenerateRequestsPerDayPerProject limit=500")
    check("429 'GenerateRequestsPerDay' returns True", is_daily_quota_exhausted(rpd_err4) is True)


def test_seconds_until_pacific_midnight():
    print("\n── Testing seconds_until_pacific_midnight ────────────────────")
    pac_tz = zoneinfo.ZoneInfo("America/Los_Angeles")

    # Live test
    rem = seconds_until_pacific_midnight()
    check("Live seconds between 1 and 86400", 1 <= rem <= 86400)

    # Mock Pacific midday (12:00:00) -> exactly 12 hours = 43200 seconds until midnight
    mock_midday = datetime(2026, 6, 15, 12, 0, 0, tzinfo=pac_tz).astimezone(timezone.utc)
    with patch("backend.rate_limit_handler.datetime") as mock_dt:
        mock_dt.now.return_value = mock_midday
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        calc = seconds_until_pacific_midnight()
        check("Midday Pacific gives 43200s", calc == 43200)

    # Mock 1 minute before midnight (23:59:00) -> 60 seconds
    mock_night = datetime(2026, 6, 15, 23, 59, 0, tzinfo=pac_tz).astimezone(timezone.utc)
    with patch("backend.rate_limit_handler.datetime") as mock_dt:
        mock_dt.now.return_value = mock_night
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        calc = seconds_until_pacific_midnight()
        check("23:59:00 Pacific gives 60s", calc == 60)


def test_gemini_cooldown_tracker():
    print("\n── Testing GeminiCooldownTracker ────────────────────────────")
    GeminiCooldownTracker.clear_cooldown()

    active, rem, msg = GeminiCooldownTracker.is_downtime_active()
    check("Initially inactive", active is False and rem == 0)

    GeminiCooldownTracker.record_daily_exhaustion(retry_after_seconds=3600, message="Custom message")
    active, rem, msg = GeminiCooldownTracker.is_downtime_active()
    check("Active after record", active is True and 3500 <= rem <= 3600 and msg == "Custom message")

    GeminiCooldownTracker.clear_cooldown()
    active, rem, msg = GeminiCooldownTracker.is_downtime_active()
    check("Inactive after clear", active is False)


def test_fastapi_rate_limit_integration():
    print("\n── Testing FastAPI endpoints with cooldown ──────────────────")
    from fastapi.testclient import TestClient
    import backend.main as main_mod

    client = TestClient(main_mod.app)

    # 1. Initially normal
    GeminiCooldownTracker.clear_cooldown()
    r = client.get("/system/rate-limit")
    check("GET /system/rate-limit 200", r.status_code == 200)
    check("rateLimited is False", r.json().get("rateLimited") is False)

    # 2. Record daily exhaustion
    GeminiCooldownTracker.record_daily_exhaustion(retry_after_seconds=1800, message="Capacity reached")
    r = client.get("/system/rate-limit")
    data = r.json()
    check("rateLimited is True", data.get("rateLimited") is True)
    check("limitType is rpd", data.get("limitType") == "rpd")
    check("retryAfterSeconds reported", 1700 <= data.get("retryAfterSeconds", 0) <= 1800)

    # 3. POST /process must fast-fail with 429 when downtime active
    main_mod.app.dependency_overrides[main_mod.get_current_user] = lambda: main_mod.User(id="test-u", email="u@test.com")
    try:
        r = client.post("/process", data={"source_type": "youtube", "url": "https://youtube.com/watch?v=abc"})
        check("POST /process fast-fails with 429 during downtime", r.status_code == 429)
        pdata = r.json()
        detail = pdata.get("detail", {})
        check("error is RATE_LIMIT_EXCEEDED", detail.get("error") == "RATE_LIMIT_EXCEEDED")
        check("limitType is rpd", detail.get("limitType") == "rpd")
    finally:
        main_mod.app.dependency_overrides.clear()
        GeminiCooldownTracker.clear_cooldown()


if __name__ == "__main__":
    test_is_daily_quota_exhausted()
    test_seconds_until_pacific_midnight()
    test_gemini_cooldown_tracker()
    test_fastapi_rate_limit_integration()

    print(f"\nTotal: {PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED > 0 else 0)
