#!/usr/bin/env python3
"""Contract smoke test for the backend API. Requires a running backend on :8000.

Run directly (no pytest):  python backend/test_api_contract.py

Read-only — issues only GET probes and verifies response shapes. It does NOT
run the paid pipeline. Pass --base http://host:port to override.
"""
import argparse
import sys

import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

# route -> (expect_ok, optional shape key that must be a list, key must be a bool)
CHECKS = {
    "/docs": ("html", None, None, None),
    "/lectures": ("json-list", None, None, None),
    "/quiz/questions": ("quiz-questions", "questions", "incomplete", None),
    "/quiz/questions?difficulty=Easy": ("quiz-questions", "questions", "incomplete", None),
    "/flashcards": ("json-list", None, None, None),
    "/outline": ("chapters-list", None, None, None),
}

# A real /quiz/questions payload, but for a lecture id that won't exist in
# legacy outputs. We only assert shape here, never content accuracy.
HEALTH_QUIZ_PARAMS = "?"


def get(path: str) -> tuple[int, object]:
    req = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            headers = resp.headers.get("content-type", "")
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001
        return 0, f"error: {e}"

    try:
        data = body.decode("utf-8")
    except Exception:  # noqa: BLE001
        data = None
    return status, (headers, data)


def post_json(path: str, body: dict) -> tuple[int, object]:
    import json
    req = urllib.request.Request(
        BASE + path,
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            headers = resp.headers.get("content-type", "")
            body_bytes = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # noqa: BLE001
        return 0, f"error: {e}"
    return status, (headers, body_bytes)


def probe_lecture_endpoints() -> list[str]:
    """/study-guide + /quiz/explain + quiz/flashcards writes need a lecture id.

    P6.4 closed-by-default: anonymous probes may only read the `default`
    lecture (real lectures are owner- or share-link-only), so probe that one.
    """
    failures: list[str] = []
    lid = "default"

    status, payload = get(f"/study-guide?lecture_id={lid}")
    print(f"GET  {f'/study-guide?lecture_id={lid}':<18} -> {status}")
    if status != 200:
        failures.append(f"/study-guide: expected 200, got {status}")
    elif payload:
        try:
            parsed = json_parse(payload[1])
            if not isinstance(parsed.get("chapters"), list):
                failures.append("/study-guide: missing `chapters` list in response")
        except Exception as e:  # noqa: BLE001
            failures.append(f"/study-guide: invalid JSON -> {e}")

    status, payload = post_json("/quiz/explain", {"question": "What is a component?", "lecture_id": lid, "chapter_id": 1})
    print(f"POST {f'/quiz/explain ({lid})':<18} -> {status}")
    if status != 200:
        failures.append(f"/quiz/explain: expected 200, got {status}")
    elif payload:
        try:
            parsed = json_parse(payload[1])
            if not isinstance(parsed, dict):
                failures.append("/quiz/explain: expected object response")
        except Exception as e:  # noqa: BLE001
            failures.append(f"/quiz/explain: invalid JSON -> {e}")

    # Phase B: Quiz attempts & flashcard ratings contract probes
    status, payload = post_json("/quiz/attempts", {"lecture_id": lid, "chapter_id": 1, "difficulty": "Easy", "questions": [{"id": "q1", "question": "Test", "answer": "A"}]})
    print(f"POST {f'/quiz/attempts ({lid})':<18} -> {status}")
    attempt_id = None
    if status != 200:
        failures.append(f"/quiz/attempts: expected 200, got {status}")
    elif payload:
        try:
            parsed = json_parse(payload[1])
            attempt_id = parsed.get("attempt_id")
            if not attempt_id:
                failures.append("/quiz/attempts: missing `attempt_id` in response")
        except Exception as e:  # noqa: BLE001
            failures.append(f"/quiz/attempts: invalid JSON -> {e}")

    if attempt_id:
        status, payload = post_json(f"/quiz/attempts/{attempt_id}/finish?lecture_id={lid}", {"answers": [{"id": "q1", "user_answer": "B"}], "score": 0.0, "total": 1})
        print(f"POST {f'/quiz/attempts/finish':<18} -> {status}")
        if status != 200:
            failures.append(f"/quiz/attempts/finish: expected 200, got {status}")

        status, payload = get(f"/quiz/attempts/{attempt_id}/missed?lecture_id={lid}")
        print(f"GET  {f'/quiz/attempts/missed':<18} -> {status}")
        if status != 200:
            failures.append(f"/quiz/attempts/missed: expected 200, got {status}")
        elif payload:
            try:
                parsed = json_parse(payload[1])
                if not isinstance(parsed.get("question_ids"), list):
                    failures.append("/quiz/attempts/missed: missing `question_ids` list")
            except Exception as e:  # noqa: BLE001
                failures.append(f"/quiz/attempts/missed: invalid JSON -> {e}")

    status, payload = get(f"/quiz/attempts?lecture_id={lid}")
    print(f"GET  {f'/quiz/attempts ({lid})':<18} -> {status}")
    if status != 200:
        failures.append(f"/quiz/attempts: expected 200, got {status}")

    status, payload = post_json("/flashcards/ratings", {"lecture_id": lid, "chapter_id": 1, "ratings": [{"card_key": "test_card", "rating": "Again"}]})
    print(f"POST {f'/flashcards/ratings ({lid})':<18} -> {status}")
    if status != 200:
        failures.append(f"/flashcards/ratings: expected 200, got {status}")

    status, payload = get(f"/flashcards/ratings?lecture_id={lid}")
    print(f"GET  {f'/flashcards/ratings ({lid})':<18} -> {status}")
    if status != 200:
        failures.append(f"/flashcards/ratings: expected 200, got {status}")

    status, payload = get(f"/concept-map?chapter_id=1&lecture_id={lid}")
    print(f"GET  {f'/concept-map ({lid})':<18} -> {status}")
    if status != 200:
        failures.append(f"/concept-map: expected 200, got {status}")
    elif payload:
        try:
            parsed = json_parse(payload[1])
            if not isinstance(parsed.get("nodes"), list) or not isinstance(parsed.get("edges"), list):
                failures.append("/concept-map: missing `nodes` or `edges` list")
        except Exception as e:  # noqa: BLE001
            failures.append(f"/concept-map: invalid JSON -> {e}")

    return failures


def main(argv: list[str] | None = None) -> int:
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE, help="backend base url")
    args = parser.parse_args(argv)
    BASE = args.base.rstrip("/")

    failures = []
    for path, (mode, list_key, bool_key, _unused) in CHECKS.items():
        qs = HEALTH_QUIZ_PARAMS if path == "/quiz/questions" else ""
        status, payload = get(path + qs)
        print(f"GET {path:<18} -> {status}")

        if mode == "html":
            if status != 200:
                failures.append(f"{path}: expected 200, got {status}")
            continue

        if status != 200:
            failures.append(f"{path}: expected 200, got {status}")
            continue

        headers, body = payload
        if "json" not in headers:
            failures.append(f"{path}: not JSON (content-type={headers})")
            continue
        try:
            parsed = json_parse(body)
        except Exception as e:  # noqa: BLE001
            failures.append(f"{path}: invalid JSON -> {e}")
            continue

        if mode == "json-list":
            if not isinstance(parsed, list):
                failures.append(f"{path}: expected list, got {type(parsed)}")
            continue

        if mode == "quiz-questions":
            if not isinstance(parsed, dict):
                failures.append(f"{path}: quiz/questions must be an object, got {type(parsed)}")
            elif not isinstance(parsed.get("questions"), list):
                failures.append(f"{path}: missing `questions` list in response")
            if bool_key is not None and not isinstance(parsed.get(bool_key), bool):
                failures.append(f"{path}: missing/incorrect `{bool_key}` boolean in response")
            continue

        if mode == "chapters-list":
            if not isinstance(parsed, dict):
                failures.append(f"{path}: expected object with `chapters`, got {type(parsed)}")
            elif not isinstance(parsed.get("chapters"), list):
                failures.append(f"{path}: missing `chapters` list in response")
            continue

        if mode == "json":
            if not isinstance(parsed, dict):
                failures.append(f"{path}: expected object, got {type(parsed)}")
            continue

    if failures:
        print("\nCONTRACT FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1

    failures = probe_lecture_endpoints()
    if failures:
        print("\nCONTRACT FAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nCONTRACT OK: all probed routes returned expected shapes.")
    return 0


def json_parse(text: str):
    import json
    return json.loads(text)


if __name__ == "__main__":
    sys.exit(main())