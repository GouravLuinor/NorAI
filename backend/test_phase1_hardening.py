"""
Standalone test: Phase 1 hardening — inbound rate limiter, security headers,
upload magic-byte signatures, persona scoping (owner-only), and cross-user
quiz/flashcard scoping.

Run directly: venv/bin/python backend/test_phase1_hardening.py
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Isolate DB writes BEFORE any backend import.
_TMP_DB = "/tmp/norai_test_p1hard.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
# Dev access lets the scoped endpoints resolve a lecture that exists on disk
# without real Supabase JWTs; identity separation below still holds because
# scoping keys off user.id, not the access gate.
os.environ["NORAI_DEV_ACCESS"] = "1"

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


# ── 1. Token bucket + DailyCounter units ──────────────────────────────────────
from backend.middleware import (
    DailyCounter,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    _TokenBucketLimiter,
    _limiters,
)


def test_token_bucket():
    lim = _TokenBucketLimiter(capacity=2, window_seconds=60)
    check("bucket allows up to capacity", lim.allow("k") and lim.allow("k"))
    check("bucket denies when drained", lim.allow("k") is False)
    check("retry_after >= 1s", lim.retry_after("k") >= 1)
    check("other keys unaffected", lim.allow("other") is True)

    fast = _TokenBucketLimiter(capacity=1, window_seconds=0.2)
    check("fast refill drains", fast.allow("k"))
    import time as _t
    _t.sleep(0.25)
    check("fast refill restores", fast.allow("k") is True)


def test_daily_counter():
    dc = DailyCounter(limit=2)
    check("daily counter admits up to limit",
          dc.check_and_increment("ip1") and dc.check_and_increment("ip1"))
    check("daily counter caps", dc.check_and_increment("ip1") is False)
    check("daily counter per-key", dc.check_and_increment("ip2") is True)
    # Simulate UTC day rollover.
    dc._day = "1999-01-01"
    check("daily counter resets on new day", dc.check_and_increment("ip1") is True)


# ── 2. Middleware ASGI behavior ───────────────────────────────────────────────

async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok"})


def _drive(middleware, scope):
    messages: list = []

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        messages.append(message)

    asyncio.run(middleware(scope, receive, send))
    return messages


def _start_headers(messages):
    return next(m for m in messages if m["type"] == "http.response.start")


def test_rate_limit_middleware():
    original = _limiters["chat"]
    _limiters["chat"] = _TokenBucketLimiter(capacity=2, window_seconds=60)
    try:
        mw = RateLimitMiddleware(_ok_app)
        base_scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [(b"x-guest-id", b"guest-rl-1")],
            "client": ("10.0.0.9", 5000),
        }
        s1 = _start_headers(_drive(mw, dict(base_scope)))
        s2 = _start_headers(_drive(mw, dict(base_scope)))
        check("limiter admits within capacity", s1["status"] == 200 and s2["status"] == 200)
        s3 = _start_headers(_drive(mw, dict(base_scope)))
        check("limiter trips 429", s3["status"] == 429)
        hdrs = {k.lower(): v for k, v in s3.get("headers", [])}
        check("429 carries retry-after", b"retry-after" in hdrs)
        check("429 body is JSON", any(
            v == b"application/json" for k, v in s3.get("headers", [])))

        other = dict(base_scope)
        other["headers"] = [(b"x-guest-id", b"guest-rl-2")]
        check("separate identity unaffected",
              _start_headers(_drive(mw, other))["status"] == 200)

        unscoped = dict(base_scope)
        unscoped["path"] = "/notes/some-id"
        unscoped["headers"] = [(b"x-guest-id", b"guest-rl-1")]
        check("non-matching routes bypass limiter",
              _start_headers(_drive(mw, unscoped))["status"] == 200)
    finally:
        _limiters["chat"] = original


def test_security_headers_middleware():
    mw = SecurityHeadersMiddleware(_ok_app)
    saved_env = os.environ.get("NORAI_ENV")
    try:
        os.environ.pop("NORAI_ENV", None)
        scope = {"type": "http", "method": "GET", "path": "/quota", "headers": [],
                 "client": ("10.0.0.9", 5000)}
        start = _start_headers(_drive(mw, dict(scope)))
        hdrs = {k.lower(): v for k, v in start.get("headers", [])}
        check("nosniff set", hdrs.get(b"x-content-type-options") == b"nosniff")
        check("frame DENY set", hdrs.get(b"x-frame-options") == b"DENY")
        check("referrer-policy set", b"referrer-policy" in hdrs)
        check("no CSP outside production", b"content-security-policy" not in hdrs)
        check("no HSTS without TLS", b"strict-transport-security" not in hdrs)

        tls_scope = dict(scope)
        tls_scope["headers"] = [(b"x-forwarded-proto", b"https")]
        hdrs_tls = {
            k.lower(): v
            for k, v in _start_headers(_drive(mw, tls_scope)).get("headers", [])
        }
        check("HSTS behind TLS", b"strict-transport-security" in hdrs_tls)

        os.environ["NORAI_ENV"] = "production"
        hdrs_prod = {
            k.lower(): v
            for k, v in _start_headers(_drive(mw, dict(scope))).get("headers", [])
        }
        csp = hdrs_prod.get(b"content-security-policy", b"")
        check("CSP enforced in production", csp.startswith(b"default-src 'self'"))
        check("CSP pins frame-ancestors none", b"frame-ancestors 'none'" in csp)
        check("CSP img-src mirrors allowlist", b"i.ytimg.com" in csp)
    finally:
        if saved_env is None:
            os.environ.pop("NORAI_ENV", None)
        else:
            os.environ["NORAI_ENV"] = saved_env


# ── 3. Upload magic-byte signatures ───────────────────────────────────────────

def test_magic_bytes():
    from backend.main import ALLOWED_UPLOAD_EXTENSIONS, _MAGIC_CHECKS

    check("signature map covers all extensions",
          set(_MAGIC_CHECKS) == ALLOWED_UPLOAD_EXTENSIONS)

    mp4_head = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    check("mp4 ftyp accepted", _MAGIC_CHECKS[".mp4"](mp4_head))
    check("mov ftyp accepted", _MAGIC_CHECKS[".mov"](mp4_head))
    ebml_head = b"\x1a\x45\xdf\xa3\x01\x00\x00\x00\x00\x00\x00\x1fB\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08"
    check("mkv EBML accepted", _MAGIC_CHECKS[".mkv"](ebml_head))
    check("webm EBML accepted", _MAGIC_CHECKS[".webm"](ebml_head))
    avi_head = b"RIFF\x24\x00\x00\x00AVI LIST"
    check("avi RIFF/AVI accepted", _MAGIC_CHECKS[".avi"](avi_head))

    garbage = b"PK\x03\x04 this is actually a zip file........"
    for ext in (".mp4", ".mov", ".mkv", ".webm"):
        check(f"{ext} rejects non-video payload ({garbage[:2]!r})",
              _MAGIC_CHECKS[ext](garbage) is False)


# ── 4. Persona scoping ────────────────────────────────────────────────────────

PERSONA_LECTURE = "p1-persona-lek"
OWNER_ID = "user_owner_p1"


async def _seed_persona_fixture():
    from backend.db.database import Base, engine
    from backend.db.models import Lecture, User
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sf() as s:
        s.add(User(id=OWNER_ID, email=f"{OWNER_ID}@example.com", is_anonymous=False))
        s.add(Lecture(id=PERSONA_LECTURE, user_id=OWNER_ID, title="Persona Lek"))
        await s.commit()
    return sf


async def _run_persona_tests():
    from backend import main as main_mod

    sf = await _seed_persona_fixture()

    async def persona(raw, user, lecture_id=PERSONA_LECTURE):
        async with sf() as s:
            return await main_mod._effective_persona_instructions(raw, user, s, lecture_id)

    class StubUser:
        def __init__(self, uid: str):
            self.id = uid

    out = await persona("Explain like I'm five.", StubUser(OWNER_ID))
    check("owner persona honored", "STUDY PREFERENCES" in out and "five" in out)

    out = await persona("Explain like I'm five.", StubUser("user_stranger_p1"))
    check("stranger persona stripped", out == "")

    out = await persona("Explain like I'm five.", StubUser("guest-xyz"))
    check("guest persona stripped", out == "")

    out = await persona("Explain like I'm five.", None)
    check("anonymous persona stripped", out == "")

    out = await persona("   ", StubUser(OWNER_ID))
    check("blank persona ignored", out == "")

    long_text = "be brief " * 80  # 720 chars
    out = await persona(long_text, StubUser(OWNER_ID))
    inner = out.split("<<< USER PREFERENCES\n", 1)[-1].rsplit("\nUSER PREFERENCES >>>", 1)[0]
    check("persona capped at 500 chars", len(inner) <= 500)

    out = await persona("Be Socratic.", StubUser(OWNER_ID), lecture_id="default")
    if os.environ.get("NORAI_DEV_ACCESS") == "1":
        # Local dev owns everything on disk (incl. outputs/default) — the
        # production rule needs the escape hatch disabled.
        saved_flag = os.environ.pop("NORAI_DEV_ACCESS")
        try:
            out = await persona("Be Socratic.", StubUser(OWNER_ID), lecture_id="default")
        finally:
            os.environ["NORAI_DEV_ACCESS"] = saved_flag
    check("demo/default lectures never accept personas", out == "")

    # Dev escape hatch parity: an on-disk lecture is 'owned' locally.
    dev_dir = Path("outputs/p1-dev-lek")
    dev_dir.mkdir(parents=True, exist_ok=True)
    try:
        out = await persona("Dev persona.", None, lecture_id="p1-dev-lek")
        check("dev-flag bypass keeps local personas working", "Dev persona." in out)
    finally:
        shutil.rmtree(dev_dir, ignore_errors=True)


# ── 5. Cross-user quiz / flashcard scoping (endpoint level) ───────────────────

SCOPED_LEK = "p1-scoped-lek"
USER_A = "user_a_p1"
USER_B = "user_b_p1"


def test_quiz_flashcard_scoping():
    from fastapi.testclient import TestClient

    from backend import main as main_mod
    from backend.db.models import User as UserModel

    lek_dir = Path("outputs") / SCOPED_LEK / "tutor"
    lek_dir.mkdir(parents=True, exist_ok=True)

    holder = {"user": None}
    main_mod.app.dependency_overrides[main_mod.get_current_user_optional] = (
        lambda: holder["user"]
    )
    try:
        client = TestClient(main_mod.app)
        holder["user"] = UserModel(id=USER_A, email=f"{USER_A}@example.com")

        created = client.post("/quiz/attempts", json={
            "lecture_id": SCOPED_LEK, "chapter_id": 1,
            "difficulty": "All",
            "questions": [{"id": 1, "type": "MCQ", "question": "2+2?",
                           "options": ["3", "4"], "answer": "4",
                           "explanation": "basic arithmetic"}],
        })
        check("attempt created for owner", created.status_code == 200)
        attempt_id = created.json().get("attempt_id", "")
        check("attempt id returned", bool(attempt_id))

        holder["user"] = UserModel(id=USER_B, email=f"{USER_B}@example.com")

        listed_b = client.get("/quiz/attempts", params={"lecture_id": SCOPED_LEK})
        check("stranger sees zero attempts", listed_b.status_code == 200
              and listed_b.json().get("attempts") == [])

        finish_b = client.post(
            f"/quiz/attempts/{attempt_id}/finish",
            params={"lecture_id": SCOPED_LEK},
            json={"answers": [], "confidences": [], "score": 0, "total": 1},
        )
        check("stranger cannot finish foreign attempt", finish_b.status_code == 404)

        missed_b = client.get(
            f"/quiz/attempts/{attempt_id}/missed",
            params={"lecture_id": SCOPED_LEK},
        )
        check("stranger cannot read foreign attempt", missed_b.status_code == 404)

        rated_b = client.post("/flashcards/ratings", json={
            "lecture_id": SCOPED_LEK, "chapter_id": 1,
            "ratings": [{"card_key": "card-b-1", "rating": "Good"}],
        })
        check("stranger rates own card", rated_b.status_code == 200)

        holder["user"] = UserModel(id=USER_A, email=f"{USER_A}@example.com")
        seen_by_a = client.get("/flashcards/ratings",
                               params={"lecture_id": SCOPED_LEK, "chapter_id": 1})
        check("owner does not see stranger's ratings",
              seen_by_a.status_code == 200
              and seen_by_a.json().get("ratings") == {})

        holder["user"] = UserModel(id=USER_A, email=f"{USER_A}@example.com")

        listed_a = client.get("/quiz/attempts", params={"lecture_id": SCOPED_LEK})
        attempts_a = listed_a.json().get("attempts", [])
        check("owner sees own attempt", len(attempts_a) == 1
              and attempts_a[0]["id"] == attempt_id)

        finish_a = client.post(
            f"/quiz/attempts/{attempt_id}/finish",
            params={"lecture_id": SCOPED_LEK},
            json={"answers": [{"pick": "4"}], "confidences": ["high"],
                  "evaluation": {}, "correct_ids": ["q-1"], "score": 1.0, "total": 1},
        )
        check("owner finishes own attempt", finish_a.status_code == 200)

        client.post("/flashcards/ratings", json={
            "lecture_id": SCOPED_LEK, "chapter_id": 1,
            "ratings": [{"card_key": "card-a-1", "rating": "Again"}],
        })
        ratings_a = client.get("/flashcards/ratings",
                               params={"lecture_id": SCOPED_LEK, "chapter_id": 1}).json()
        check("owner sees only own ratings",
              set(ratings_a.get("ratings", {})) == {"card-a-1"})
    finally:
        main_mod.app.dependency_overrides.pop(main_mod.get_current_user_optional, None)
        shutil.rmtree(Path("outputs") / SCOPED_LEK, ignore_errors=True)


if __name__ == "__main__":
    test_token_bucket()
    test_daily_counter()
    test_rate_limit_middleware()
    test_security_headers_middleware()
    test_magic_bytes()
    asyncio.run(_run_persona_tests())
    test_quiz_flashcard_scoping()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
