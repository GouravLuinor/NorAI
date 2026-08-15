#!/usr/bin/env python3
"""
Offline contract test (P5.8): boots the FastAPI app IN-PROCESS against a
throwaway SQLite DB and exercises read-only + auth-negative + validation-
negative paths. No paid pipeline, no network (no Gemini, no Supabase JWKS, no
YouTube download).

Run directly (no pytest):  venv/bin/python backend/test_api_contract_offline.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isolate DB writes to a throwaway SQLite file (never the real DATABASE_URL).
_TMP_DB = "/tmp/norai_test_contract.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["GEMINI_API_KEY"] = "offline-contract-test"
os.environ["NORAI_DEV_ACCESS"] = "0"

from fastapi.testclient import TestClient

from backend import main as main_mod
from backend.db.models import User as _User

FAKE_USER_ID = "contract_test_user"

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


def _fake_user():
    async def _dep():
        return _User(id=FAKE_USER_ID, email=f"{FAKE_USER_ID}@example.com", is_anonymous=False)

    return _dep


def main() -> int:
    # `with` block runs lifespan startup: Alembic migrations on the temp DB,
    # pipeline supervisor (daemon), one GC sweep. No jobs are enqueued, so the
    # paid pipeline never runs.
    with TestClient(main_mod.app) as client:
        r = client.get("/docs")
        check(
            "GET /docs 200 + html",
            r.status_code == 200 and "text/html" in r.headers.get("content-type", ""),
        )

        r = client.get("/openapi.json")
        paths = r.json().get("paths", {})
        check("openapi exposes POST /process", "/process" in paths)
        check("openapi exposes POST /chat", "/chat" in paths)
        check("openapi exposes GET /quota", "/quota" in paths)

        r = client.get("/lectures")
        check("GET /lectures 200 + list", r.status_code == 200 and isinstance(r.json(), list))

        r = client.get("/outline")
        data = r.json()
        check(
            "GET /outline 200 + chapters list",
            r.status_code == 200 and isinstance(data.get("chapters"), list),
        )

        r = client.get("/quiz/questions")
        data = r.json()
        check(
            "GET /quiz/questions 200 + questions list",
            r.status_code == 200
            and isinstance(data.get("questions"), list)
            and isinstance(data.get("incomplete"), bool),
        )

        r = client.get("/quota")
        data = r.json()
        check(
            "GET /quota anonymous 200 + trial shape",
            r.status_code == 200
            and data.get("is_anonymous") is True
            and data.get("monthly_minutes_quota") == 15
            and data.get("remaining_minutes") == 15,
        )

        # ── Auth-negative (no token; fails fast, no Supabase call) ────────────
        r = client.post("/process")
        check("POST /process 401 unauthenticated", r.status_code == 401)
        r = client.get("/billing")
        check("GET /billing 401 unauthenticated", r.status_code == 401)

        # ── Validation-negative (authenticated as a fake user) ───────────────
        main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user()
        try:
            r = client.post("/process", data={"source_type": "bogus"})
            check("POST /process unsupported source_type 400", r.status_code == 400)

            r = client.post(
                "/process",
                data={"source_type": "youtube", "url": "https://example.com/not-a-video"},
            )
            check("POST /process invalid youtube url 400", r.status_code == 400)

            r = client.post(
                "/process",
                data={"source_type": "gdrive", "url": "https://example.com/not-a-drive-file"},
            )
            check("POST /process invalid gdrive url 400", r.status_code == 400)

            r = client.post("/process", data={"source_type": "upload"})
            check("POST /process upload without file 400", r.status_code == 400)

            r = client.post("/chat", json={})
            check("POST /chat empty body 422", r.status_code == 422)
        finally:
            main_mod.app.dependency_overrides.clear()

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
