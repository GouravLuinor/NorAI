"""
backend/routers/study.py — study dashboard and cross-lecture learning summary.

Provides unified study aggregation across all lectures for a student:
- Continue where you left off (recent active lecture)
- Due flashcards across lectures (SM-2 spaced repetition)
- Quiz retakes (recent attempts with missed questions)
"""

import json as json_lib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user_optional
from backend.db.database import get_db
from backend.db.models import Lecture, User
from backend.dependencies import sanitize_lecture_id
from backend.lecture_db import (
    _db,
    _ensure_flashcard_ratings_table,
    _ensure_quiz_attempts_table,
    _ensure_quiz_attempts_correct_ids,
)
from backend.lecture_registry import get_lecture, list_lectures
from config import DEMO_LECTURE_IDS
from flashcards.sm2 import due_in_days

router = APIRouter()
logger = logging.getLogger("norai")

PRIMARY_DEMO_ID = "8821152f-f6de-49e9-a885-0adaac6ba4cb"


def _get_lecture_artifact_dir(lecture_id: str) -> Path:
    """Find the artifacts directory for a lecture (outputs/ or seed_data/)."""
    out_dir = Path("outputs") / lecture_id
    if out_dir.exists():
        return out_dir
    seed_dir = Path("seed_data") / lecture_id
    if seed_dir.exists():
        return seed_dir
    return out_dir


def _count_lecture_flashcards(artifact_dir: Path) -> Dict[int, int]:
    """Count flashcards per chapter on disk for a lecture. Returns chapter_id -> count."""
    deck_dir = artifact_dir / "flashcards"
    chapter_counts: Dict[int, int] = {}
    if not deck_dir.exists():
        return chapter_counts

    for p in sorted(deck_dir.glob("flashcards_chapter_*.json")):
        try:
            # Filename format: flashcards_chapter_1.json
            stem = p.stem.split("chapter_")[-1]
            ch_id = int(stem)
            data = json_lib.loads(p.read_text(encoding="utf-8"))
            cards = data.get("flashcards", []) if isinstance(data, dict) else data
            chapter_counts[ch_id] = len(cards) if isinstance(cards, list) else 0
        except Exception:
            continue

    if not chapter_counts:
        # Fall back to combined flashcards.json
        combined = deck_dir / "flashcards.json"
        if combined.exists():
            try:
                data = json_lib.loads(combined.read_text(encoding="utf-8"))
                cards = data.get("flashcards", []) if isinstance(data, dict) else data
                chapter_counts[1] = len(cards) if isinstance(cards, list) else 0
            except Exception:
                pass

    return chapter_counts


@router.get("/study/overview")
async def get_study_overview(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the aggregated study dashboard for the current user.

    Aggregates:
    1. Continue where you left off (recent active lecture)
    2. Flashcards due today across lectures (SM-2 spaced repetition)
    3. Quizzes to retake (recent attempts with missed questions)
    4. Study progress stats
    """
    user_id_str = str(user.id) if user and user.id else ""
    guest_id = request.headers.get("x-guest-id", "")
    effective_uid = user_id_str or guest_id

    # 1. Collect candidate lectures
    user_lectures: List[Dict[str, Any]] = []
    if user is not None:
        try:
            result = await db.execute(
                select(Lecture)
                .where(Lecture.user_id == user.id)
                .order_by(Lecture.created_at.desc())
            )
            rows = result.scalars().all()
            for row in rows:
                meta = get_lecture(row.id) or {}
                user_lectures.append({
                    "lecture_id": str(row.id),
                    "title": meta.get("title") or row.title or "Untitled Lecture",
                    "chapter_count": meta.get("chapter_count", 0),
                    "duration_seconds": row.duration_seconds or 0,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "is_demo": False,
                    "source_type": row.source_type or "youtube",
                })
        except Exception as exc:
            logger.warning("Failed to fetch user lectures in /study/overview: %s", exc)

    # All lectures to scan for study activity: user's personal lectures + all demo lectures
    candidate_ids: List[str] = [l["lecture_id"] for l in user_lectures]
    for demo_id in DEMO_LECTURE_IDS:
        if demo_id not in candidate_ids:
            candidate_ids.append(demo_id)

    today_str = time.strftime("%Y-%m-%d", time.gmtime())
    total_due_flashcards = 0
    flashcard_decks: List[Dict[str, Any]] = []
    quiz_retakes: List[Dict[str, Any]] = []
    total_quizzes_finished = 0
    total_cards_rated = 0
    last_studied_lecture_id: Optional[str] = None
    last_studied_chapter_id: int = 1
    last_activity_time = ""

    for lid in candidate_ids:
        title = "Demo Lecture"
        is_demo = lid in DEMO_LECTURE_IDS
        demo_meta = get_lecture(lid)
        if demo_meta and demo_meta.get("title"):
            title = demo_meta["title"]
        else:
            matching_user_lec = next((l for l in user_lectures if l["lecture_id"] == lid), None)
            if matching_user_lec:
                title = matching_user_lec["title"]

        artifact_dir = _get_lecture_artifact_dir(lid)
        ch_card_counts = _count_lecture_flashcards(artifact_dir)

        try:
            with _db(lid) as conn:
                _ensure_flashcard_ratings_table(conn)
                _ensure_quiz_attempts_table(conn)
                _ensure_quiz_attempts_correct_ids(conn)

                # Flashcard ratings
                cursor = conn.execute(
                    "SELECT card_key, chapter_id, due_at, last_reviewed_at "
                    "FROM flashcard_ratings WHERE lecture_id=? AND user_id=?",
                    (lid, effective_uid),
                )
                ratings_rows = cursor.fetchall()
                total_cards_rated += len(ratings_rows)

                # Track ratings per chapter
                due_per_ch: Dict[int, int] = {}
                reviewed_keys_per_ch: Dict[int, set] = {}

                for r in ratings_rows:
                    ch_id = r[1] or 1
                    due_at = r[2] or ""
                    reviewed_at = r[3] or ""
                    if reviewed_at > last_activity_time:
                        last_activity_time = reviewed_at
                        last_studied_lecture_id = lid
                        last_studied_chapter_id = ch_id

                    if ch_id not in reviewed_keys_per_ch:
                        reviewed_keys_per_ch[ch_id] = set()
                    reviewed_keys_per_ch[ch_id].add(r[0])

                    # Due if due_at is on or before today
                    if due_at and due_at <= today_str:
                        due_per_ch[ch_id] = due_per_ch.get(ch_id, 0) + 1

                # If this is a demo lecture, ONLY include it if the user has actually studied it
                # (has rated cards in it). Don't spam unstudied demo decks with hundreds of unreviewed cards.
                has_demo_activity = len(ratings_rows) > 0
                if not is_demo or has_demo_activity:
                    for ch_id, total_ch_cards in ch_card_counts.items():
                        reviewed_count = len(reviewed_keys_per_ch.get(ch_id, set()))
                        ch_due = due_per_ch.get(ch_id, 0)
                        if not is_demo:
                            unreviewed = max(0, total_ch_cards - reviewed_count)
                            ch_due += min(unreviewed, 10)

                        if ch_due > 0:
                            total_due_flashcards += ch_due
                            flashcard_decks.append({
                                "lecture_id": lid,
                                "lecture_title": title,
                                "chapter_id": ch_id,
                                "due_count": ch_due,
                                "total_cards": total_ch_cards,
                                "is_demo": is_demo,
                            })

                # Quiz attempts
                q_cursor = conn.execute(
                    "SELECT id, chapter_id, difficulty, score, total, started_at, finished_at, correct_ids_json, questions_json "
                    "FROM quiz_attempts WHERE lecture_id=? AND user_id=? "
                    "ORDER BY started_at DESC LIMIT 5",
                    (lid, effective_uid),
                )
                attempt_rows = q_cursor.fetchall()
                for q_row in attempt_rows:
                    att_id = q_row[0]
                    ch_id = q_row[1] or 1
                    difficulty = q_row[2] or "Medium"
                    score = float(q_row[3] or 0)
                    total = int(q_row[4] or 0)
                    started_at = q_row[5] or ""
                    finished_at = q_row[6] or ""

                    act_time = finished_at or started_at
                    if act_time > last_activity_time:
                        last_activity_time = act_time
                        last_studied_lecture_id = lid
                        last_studied_chapter_id = ch_id

                    if finished_at:
                        total_quizzes_finished += 1
                        if total > 0 and score < total:
                            # Attempt had missed questions
                            missed = max(1, int(round(total - score)))
                            quiz_retakes.append({
                                "attempt_id": att_id,
                                "lecture_id": lid,
                                "lecture_title": title,
                                "chapter_id": ch_id,
                                "difficulty": difficulty,
                                "score": score,
                                "total": total,
                                "missed_count": missed,
                                "finished_at": finished_at,
                                "is_demo": is_demo,
                            })

        except Exception as exc:
            logger.debug("Failed to read study db for %s: %s", lid, exc)

    # 3. Determine recent lecture to continue where left off
    recent_lecture: Optional[Dict[str, Any]] = None
    if last_studied_lecture_id:
        target_id = last_studied_lecture_id
    elif user_lectures:
        target_id = user_lectures[0]["lecture_id"]
    else:
        target_id = PRIMARY_DEMO_ID

    # Enrich recent lecture details
    target_meta = get_lecture(target_id) or {}
    demo_fallback = next((d for d in DEMO_LECTURE_IDS if d == target_id), None)
    recent_lecture = {
        "lecture_id": target_id,
        "title": target_meta.get("title") or "Algorithms and Computation",
        "chapter_count": target_meta.get("chapter_count", 9),
        "duration_seconds": target_meta.get("duration_seconds", 2734),
        "category": target_meta.get("category") or "Computer Science & Algorithms",
        "is_demo": bool(demo_fallback or target_id in DEMO_LECTURE_IDS),
        "source_type": target_meta.get("source_type", "youtube"),
        "last_chapter_id": last_studied_chapter_id if last_studied_lecture_id == target_id else 1,
    }

    # Sort retakes by newest finished_at
    quiz_retakes.sort(key=lambda x: x.get("finished_at", ""), reverse=True)

    return {
        "recent_lecture": recent_lecture,
        "flashcards_due": {
            "total_due": total_due_flashcards,
            "decks": flashcard_decks[:6],
        },
        "quiz_retakes": quiz_retakes[:5],
        "stats": {
            "total_user_lectures": len(user_lectures),
            "total_quizzes_finished": total_quizzes_finished,
            "total_cards_rated": total_cards_rated,
        },
    }
