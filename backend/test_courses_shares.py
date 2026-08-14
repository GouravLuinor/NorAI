#!/usr/bin/env python3
"""
P6.4 — offline contract tests for course collections + share links.

Boots the FastAPI app IN-PROCESS against a throwaway SQLite DB (lifespan
startup runs Alembic migrations + supervisor). No paid pipeline, no network.

Run directly:  venv/bin/python backend/test_courses_shares.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP_DB = "/tmp/norai_test_courses.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["GEMINI_API_KEY"] = "offline-courses-test"


def _utc_now():
    return datetime.now(timezone.utc)

from fastapi.testclient import TestClient  # noqa: E402
import asyncio  # noqa: E402

from backend import lecture_registry as _reg  # noqa: E402

# Redirect the file-based lecture registry to a temp path so tests never
# pollute the real outputs/lectures.json.
_TMP_REGISTRY = Path("/tmp/norai_test_registry.json")
if _TMP_REGISTRY.exists():
    _TMP_REGISTRY.unlink()
_reg.REGISTRY_PATH = _TMP_REGISTRY

from backend import main as main_mod  # noqa: E402
from backend.db.models import User as _User, Lecture as _Lecture, ShareLink as _ShareLink  # noqa: E402
from backend.db.database import AsyncSessionLocal  # noqa: E402

FAKE_USER_A = "user_a_1234"
FAKE_USER_B = "user_b_5678"

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


def _fake_user(user_id: str):
    async def _dep():
        return _User(id=user_id, email=f"{user_id}@example.com", is_anonymous=False)

    return _dep


def _migrate():
    # run_migrations() internally uses asyncio.run(), so it must be invoked
    # from a plain (non-loop) context.
    from backend.db.migrate import run_migrations

    run_migrations()


async def _seed():
    async with AsyncSessionLocal() as s:
        s.add_all(
            [
                _Lecture(
                    id="lec-own",
                    user_id=FAKE_USER_A,
                    title="Owned Lecture",
                    status="completed",
                    source_type="youtube",
                ),
                _Lecture(
                    id="lec-foreign",
                    user_id=FAKE_USER_B,
                    title="Foreign Lecture",
                    status="completed",
                    source_type="youtube",
                ),
                _ShareLink(
                    id="expired-slug",
                    lecture_id="lec-foreign",
                    created_by=FAKE_USER_B,
                    allow_tutor_chat=True,
                    expires_at=_utc_now() - timedelta(minutes=5),
                ),
            ]
        )
        await s.commit()
    # Registry entry so get_lecture() resolves lec-own (the access gate lives
    # in ensure_lecture_access, not the registry).
    _reg._save(
        {
            "lec-own": {
                "lecture_id": "lec-own",
                "title": "Owned Lecture",
                "created_at": "2026-01-01T00:00:00",
                "output_dir": "/tmp/norai_test_registry_out/lec-own",
            }
        }
    )


async def _stub_tutor(**kwargs):
    return {
        "answer": "stub answer",
        "retrieved_chunks": [],
        "retrieved_images": [],
        "verified_citations": [],
        "chapter_id": None,
        "thread_id": kwargs.get("thread_id"),
    }


def _as_user(user_id: str):
    main_mod.app.dependency_overrides[main_mod.get_current_user] = _fake_user(user_id)
    main_mod.app.dependency_overrides[main_mod.get_current_user_optional] = _fake_user(user_id)


def _clear_auth():
    main_mod.app.dependency_overrides.clear()


def main() -> int:
    _migrate()
    asyncio.run(_seed())

    with TestClient(main_mod.app) as client:
        # ── Anonymous lecture listing / reads ────────────────────────────────
        r = client.get("/lectures")
        check("anon GET /lectures 200 + list", r.status_code == 200 and isinstance(r.json(), list))

        r = client.get("/lectures/lec-foreign")
        check("anon read of unshared lecture 404 (closed-by-default)", r.status_code == 404)

        r = client.get("/outline?lecture_id=lec-foreign")
        check("anon outline of unshared lecture 404", r.status_code == 404)

        r = client.get("/courses")
        check("anon GET /courses 401", r.status_code == 401)

        # ── Owner-scoped lecture list ────────────────────────────────────────
        _as_user(FAKE_USER_A)
        try:
            r = client.get("/lectures")
            ids = [x.get("lecture_id") for x in r.json()]
            check(
                "owner GET /lectures scoped (only own)",
                r.status_code == 200 and "lec-own" in ids and "lec-foreign" not in ids,
            )

            # ── Course CRUD ──────────────────────────────────────────────────
            r = client.get("/courses")
            check("owner GET /courses empty", r.status_code == 200 and r.json()["courses"] == [])

            r = client.post("/courses", json={"name": "  Physics 101  "})
            body = r.json()
            course_id = body.get("course_id")
            check(
                "POST /courses creates + trims name",
                r.status_code == 200 and body["name"] == "Physics 101",
            )

            r = client.post("/courses", json={"name": "   "})
            check("POST /courses blank name 400", r.status_code == 400)

            r = client.get("/courses")
            check("GET /courses lists 1 course", len(r.json()["courses"]) == 1)

            # ── Course membership ────────────────────────────────────────────
            r = client.post(f"/courses/{course_id}/lectures", json={"lecture_id": "lec-own"})
            check("POST add owned lecture", r.status_code == 200)

            r = client.post(f"/courses/{course_id}/lectures", json={"lecture_id": "lec-foreign"})
            check("POST add foreign lecture 404", r.status_code == 404)

            r = client.get(f"/courses/{course_id}")
            detail = r.json()
            check(
                "GET /courses/{id} lists member lecture",
                r.status_code == 200
                and [x.get("lecture_id") for x in detail["lectures"]] == ["lec-own"],
            )

            r = client.put(
                f"/courses/{course_id}/lectures",
                json={"lecture_ids": ["nope", "lec-own"]},
            )
            check("PUT reorder invalid member 400", r.status_code == 400)

            r = client.patch(f"/courses/{course_id}", json={"name": "Physics 201"})
            check("PATCH rename course", r.status_code == 200 and r.json()["name"] == "Physics 201")

            r = client.delete(f"/courses/{course_id}/lectures/lec-own")
            check("DELETE remove lecture from course", r.status_code == 200)
            r = client.get(f"/courses/{course_id}")
            check(
                "GET course now empty of lectures",
                r.json().get("lectures") == [],
            )

            r = client.delete(f"/courses/{course_id}")
            check("DELETE course", r.status_code == 200)
            r = client.get("/courses")
            check("GET /courses empty after delete", r.json()["courses"] == [])
        finally:
            _clear_auth()

        # ── Non-owner course access ──────────────────────────────────────────
        _as_user(FAKE_USER_A)
        try:
            client.post("/courses", json={"name": "Physics"})
        finally:
            _clear_auth()
        _as_user(FAKE_USER_B)
        try:
            r = client.get("/courses")
            course_b_list = r.json()["courses"]
            # user B has no courses; A's course must not leak.
            check(
                "user B sees no courses (isolation)",
                r.status_code == 200 and course_b_list == [],
            )
        finally:
            _clear_auth()

        # ── Share links ──────────────────────────────────────────────────────
        _as_user(FAKE_USER_A)
        try:
            r = client.post("/lectures/lec-own/share", json={"allow_tutor_chat": False})
            body = r.json()
            slug = body.get("slug")
            check(
                "POST share creates slug + url",
                r.status_code == 200 and slug and f"/share/{slug}" in body["url"],
            )
            check("share allow_tutor_chat honored", body["allow_tutor_chat"] is False)

            r = client.post("/lectures/lec-foreign/share", json={})
            check("non-owner cannot share 404", r.status_code == 404)

            # GET returns the existing link for the owner (ShareModal load path).
            r = client.get("/lectures/lec-own/share")
            body = r.json()
            check(
                "GET share returns existing slug + url",
                r.status_code == 200 and body.get("slug") == slug and f"/share/{slug}" in body.get("url", ""),
            )
            r = client.get("/lectures/lec-foreign/share")
            check("GET share non-owner 404", r.status_code == 404)
        finally:
            _clear_auth()

        # Anonymous access via the share link (read allowed; tutor chat gated).
        _clear_auth()
        r = client.get("/lectures/lec-own")
        check("anon read shared lecture 200", r.status_code == 200)

        # /quiz/explain is READ-gated only (index retrieval, no LLM): a share
        # link without tutor permission still passes require_tutor=False.
        r = client.post(
            "/quiz/explain",
            json={"question": "What is a component?", "lecture_id": "lec-own", "chapter_id": 1},
        )
        check(
            "anon quiz/explain on tutor-disabled share passes read gate 200",
            r.status_code == 200,
        )

        r = client.get("/share/expired-slug")
        check("expired share slug 404", r.status_code == 404)

        # Stub the tutor so the gate is the only thing under test.
        main_mod.ainvoke_tutor = _stub_tutor
        try:
            chat_body = {
                "thread_id": "t1",
                "user_question": "hi",
                "lecture_id": "lec-own",
            }
            r = client.post("/chat", json=chat_body)
            check("anon chat on tutor-disabled share 404", r.status_code == 404)

            r = client.post("/chat/stream", json=chat_body)
            check("anon chat/stream on tutor-disabled share 404", r.status_code == 404)

            r = client.post("/quiz/attempts", json={"lecture_id": "lec-own"})
            check("anon quiz attempt on tutor-disabled share 404", r.status_code == 404)

            r = client.post(
                "/flashcards/ratings",
                json={"lecture_id": "lec-own", "ratings": []},
            )
            check("anon flashcards rating on tutor-disabled share 404", r.status_code == 404)
        finally:
            main_mod.ainvoke_tutor = None
            del main_mod.ainvoke_tutor
            _clear_auth()

        # Owner re-enables tutor chat on the share.
        _as_user(FAKE_USER_A)
        try:
            r = client.patch("/lectures/lec-own/share", json={"allow_tutor_chat": True})
            check("PATCH share enables tutor chat", r.status_code == 200 and r.json()["allow_tutor_chat"] is True)
        finally:
            _clear_auth()

        _clear_auth()
        main_mod.ainvoke_tutor = _stub_tutor
        try:
            chat_body = {
                "thread_id": "t1",
                "user_question": "hi",
                "lecture_id": "lec-own",
            }
            r = client.post("/chat", json=chat_body)
            check("anon chat on tutor-enabled share passes gate (stub 200)", r.status_code == 200)
        finally:
            main_mod.ainvoke_tutor = None
            del main_mod.ainvoke_tutor
            _clear_auth()

        # Revoking kills anonymous read access.
        _as_user(FAKE_USER_A)
        try:
            r = client.delete("/lectures/lec-own/share")
            check("DELETE share revokes", r.status_code == 200)
            r = client.get("/lectures/lec-own/share")
            check("GET share after revoke 404", r.status_code == 404)
        finally:
            _clear_auth()
        _clear_auth()
        r = client.get("/lectures/lec-own")
        check("anon read revoked lecture 404", r.status_code == 404)

        # After revoke the read-gate on quiz/explain also 404s.
        r = client.post(
            "/quiz/explain",
            json={"question": "What is a component?", "lecture_id": "lec-own", "chapter_id": 1},
        )
        check("anon quiz/explain on revoked lecture 404", r.status_code == 404)

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
