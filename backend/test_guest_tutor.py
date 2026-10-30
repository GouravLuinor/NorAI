#!/usr/bin/env python3
"""
Test guest tutor on demo lectures (Phase D):
1. GET /lectures/{id}/suggested-questions returns canonical questions and remaining quota.
2. Unauthenticated request without guest id fails with 401.
3. Cached suggested question answers instantly with zero token consumption and does not consume quota.
4. Non-cached guest question decrements quota (5/day limit) and rejects 6th question with 429.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP_DB = "/tmp/norai_test_guest_tutor.db"
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["GEMINI_API_KEY"] = "offline-test"
os.environ["NORAI_DEV_ACCESS"] = "0"

from fastapi.testclient import TestClient
from backend import main as main_mod
from backend import access
from config import DEMO_LECTURE_IDS

DEMO_ID = "8821152f-f6de-49e9-a885-0adaac6ba4cb"  # MIT Algorithms

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


def main() -> int:
    with TestClient(main_mod.app) as client:
        # 1. Suggested questions endpoint
        r = client.get(
            f"/lectures/{DEMO_ID}/suggested-questions",
            headers={"X-Guest-Id": "guest-visitor-1"},
        )
        check("GET suggested questions 200", r.status_code == 200)
        data = r.json()
        check("suggested_questions is non-empty list", len(data.get("suggested_questions", [])) > 0)
        check("is_guest is true", data.get("is_guest") is True)
        check("guest_questions_remaining is 5", data.get("guest_questions_remaining") == 5)

        # 2. Unauthenticated POST /chat without X-Guest-Id rejected with 401
        r = client.post(
            "/chat",
            json={
                "lecture_id": DEMO_ID,
                "thread_id": "t1",
                "user_question": "What is the time complexity of quicksort?",
            },
        )
        check("POST /chat without guest header rejected with 401", r.status_code == 401)

        # 3. Cached suggested question answers instantly without consuming quota
        cached_q = "What is the formal definition of a computational problem?"
        r = client.post(
            "/chat",
            headers={"X-Guest-Id": "guest-visitor-1"},
            json={
                "lecture_id": DEMO_ID,
                "thread_id": "t1",
                "user_question": cached_q,
            },
        )
        check("POST /chat cached question 200", r.status_code == 200)
        body = r.json()
        check("cached question response has cached=True", body.get("cached") is True)
        check("cached question has answer text", "computational problem" in body.get("answer", "").lower())
        check("cached question has citations", len(body.get("verified_citations", [])) > 0)

        # Quota should still be 5 because cached questions are free
        r_quota = client.get(
            f"/lectures/{DEMO_ID}/suggested-questions",
            headers={"X-Guest-Id": "guest-visitor-1"},
        )
        check("quota intact at 5 after cached question", r_quota.json().get("guest_questions_remaining") == 5)

        # 3b. Verify cached turn is persisted to thread history
        r_thread = client.get(
            f"/threads/t1?lecture_id={DEMO_ID}",
            headers={"X-Guest-Id": "guest-visitor-1"},
        )
        check("GET /threads/t1 with guest header 200", r_thread.status_code == 200)
        t_data = r_thread.json()
        msgs = t_data.get("messages", [])
        check("cached turn persisted in messages (>= 2)", len(msgs) >= 2)
        check("user message in thread history", msgs[0]["role"] == "user" and msgs[0]["content"] == cached_q)
        check("assistant message in thread history", msgs[1]["role"] == "assistant" and len(msgs[1]["content"]) > 0)

        # Guest thread isolation: visitor-2 does not see visitor-1's thread history
        r_other_thread = client.get(
            f"/threads/t1?lecture_id={DEMO_ID}",
            headers={"X-Guest-Id": "guest-visitor-2"},
        )
        check("different guest sees clean isolated thread", len(r_other_thread.json().get("messages", [])) == 0)

        # Free demo actions (flashcards & quizzes) don't fail with 401 and don't consume quota
        r_fc = client.post(
            "/flashcards/ratings",
            json={
                "lecture_id": DEMO_ID,
                "chapter_id": 1,
                "ratings": [{"card_key": "card-1", "rating": "Good"}],
            },
        )
        check("unauthenticated POST /flashcards/ratings on demo succeeds (200)", r_fc.status_code == 200)

        r_quiz = client.post(
            "/quiz/attempts",
            json={
                "lecture_id": DEMO_ID,
                "chapter_id": 1,
                "difficulty": "Medium",
                "questions": [],
            },
        )
        check("unauthenticated POST /quiz/attempts on demo succeeds (200)", r_quiz.status_code == 200)

        # Thread management endpoints support X-Guest-Id
        r_new_thread = client.post(
            "/threads",
            headers={"X-Guest-Id": "guest-visitor-1"},
            json={"lecture_id": DEMO_ID, "thread_id": "guest-t2"},
        )
        check("POST /threads with X-Guest-Id succeeds (200)", r_new_thread.status_code == 200)

        r_list = client.get(
            f"/threads?lecture_id={DEMO_ID}",
            headers={"X-Guest-Id": "guest-visitor-1"},
        )
        check("GET /threads lists guest threads", r_list.status_code == 200 and "t1" in r_list.json().get("threads", []))

        r_del = client.delete(
            f"/threads/guest-t2?lecture_id={DEMO_ID}",
            headers={"X-Guest-Id": "guest-visitor-1"},
        )
        check("DELETE /threads with X-Guest-Id succeeds (200)", r_del.status_code == 200)

        # Quota check after all the non-tutor actions
        r_quota2 = client.get(
            f"/lectures/{DEMO_ID}/suggested-questions",
            headers={"X-Guest-Id": "guest-visitor-1"},
        )
        check("quota still 5 after free demo actions and thread ops", r_quota2.json().get("guest_questions_remaining") == 5)

        # 4. Custom questions consume guest quota up to 5
        mock_tutor_response = {
            "answer": "This is a mocked answer from Nora.",
            "retrieved_chunks": [],
            "retrieved_images": [],
            "verified_citations": [],
            "chapter_id": 1,
            "thread_id": "t1",
        }
        with patch("backend.dependencies.ainvoke_tutor", new=AsyncMock(return_value=mock_tutor_response)):
            # 5 allowed turns
            for i in range(5):
                r_custom = client.post(
                    "/chat",
                    headers={"X-Guest-Id": "guest-visitor-1"},
                    json={
                        "lecture_id": DEMO_ID,
                        "thread_id": "t1",
                        "user_question": f"Custom question {i}",
                    },
                )
                check(f"custom question {i + 1} succeeds (200)", r_custom.status_code == 200)

            # 6th turn must be 429 (guest limit reached)
            r_exceeded = client.post(
                "/chat",
                headers={"X-Guest-Id": "guest-visitor-1"},
                json={
                    "lecture_id": DEMO_ID,
                    "thread_id": "t1",
                    "user_question": "Custom question 6",
                },
            )
            check("6th custom question rejected with 429", r_exceeded.status_code == 429)
            check("429 error mentions guest limit", "5 free guest questions" in r_exceeded.json().get("detail", ""))

    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
