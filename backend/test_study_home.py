"""
backend/test_study_home.py — offline test suite for Phase C Study Home API.
"""

import os
import sys
import tempfile
from pathlib import Path
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GEMINI_API_KEY", "test-offline-key")
os.environ.setdefault("NORAI_DEV_ACCESS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/norai_test_study.db")

from backend import main as main_mod
from backend.db.models import User


def check(desc: str, ok: bool):
    if ok:
        print(f"  [PASS] {desc}")
    else:
        print(f"  [FAIL] {desc}")
        sys.exit(1)


def _fake_user(email: str = "study-user@norai.local", user_id: str = "usr-study-123"):
    async def _override():
        return User(
            id=user_id,
            email=email,
            is_anonymous=False,
        )
    return _override


def main() -> int:
    print("Testing GET /study/overview endpoint...")

    with TestClient(main_mod.app) as client:
        # 1. Unauthenticated / anonymous visitor
        r = client.get("/study/overview")
        check("GET /study/overview returns 200 for unauthenticated", r.status_code == 200)
        data = r.json()
        check("overview has recent_lecture", "recent_lecture" in data)
        check("overview has flashcards_due", "flashcards_due" in data)
        check("overview has quiz_retakes", "quiz_retakes" in data)
        check("overview has stats", "stats" in data)
        check("recent_lecture defaults to a valid lecture", bool(data["recent_lecture"]["lecture_id"]))

        # 2. Authenticated user
        main_mod.app.dependency_overrides[main_mod.get_current_user_optional] = _fake_user()
        try:
            r = client.get("/study/overview")
            check("GET /study/overview returns 200 for authenticated user", r.status_code == 200)
            user_data = r.json()
            check("authenticated overview structure is valid", isinstance(user_data["flashcards_due"]["decks"], list))
            check("stats dictionary is populated", "total_user_lectures" in user_data["stats"])
            check("new user has 0 due cards initially (demo cards not forced due)", user_data["flashcards_due"]["total_due"] == 0)

            # Record quiz attempt on chapter 3 for the recent lecture
            recent_lid = user_data["recent_lecture"]["lecture_id"]
            r_attempt = client.post(
                "/quiz/attempts",
                json={
                    "lecture_id": recent_lid,
                    "chapter_id": 3,
                    "difficulty": "Medium",
                    "questions": [],
                },
            )
            check("POST /quiz/attempts succeeds (200)", r_attempt.status_code == 200)

            # Re-fetch overview and verify last_chapter_id reflects the studied chapter
            r_after = client.get("/study/overview")
            check("GET /study/overview returns 200 after quiz attempt", r_after.status_code == 200)
            updated = r_after.json()
            check("recent_lecture.last_chapter_id updated to 3", updated["recent_lecture"]["last_chapter_id"] == 3)
        finally:
            main_mod.app.dependency_overrides.pop(main_mod.get_current_user_optional, None)

    print("All study overview tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
