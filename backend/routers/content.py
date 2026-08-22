"""
backend/routers/content.py — study content/document endpoints (P5.1).

Extracted verbatim from main.py; mounted without prefixes so paths are
unchanged. Clusters: flashcard ratings (SM-2), study artifacts (study guide,
flashcards, summary, notes, screenshots), and navigation metadata
(video-map, outline, concept-map).
"""
import json as json_lib
import random
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.access import ensure_lecture_access
from backend.auth import get_current_user_optional
from backend.concept_map import build_concept_map
from backend.db.database import get_db
from backend.db.models import User
from backend.dependencies import sanitize_lecture_id
from backend.lecture_db import _db, _ensure_flashcard_ratings_table
from backend.lecture_registry import get_lecture
from backend.video_map import build_video_map
from flashcards.sm2 import apply_sm2, due_in_days
from flashcards.anki import build_package

router = APIRouter()


class FlashcardRatingItem(BaseModel):
    card_key: str
    rating: str

class UpsertFlashcardRatingsRequest(BaseModel):
    lecture_id: str = "default"
    chapter_id: int | None = None
    ratings: list[FlashcardRatingItem] = []


@router.post("/flashcards/ratings")
async def upsert_flashcard_ratings(
    req: UpsertFlashcardRatingsRequest,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(req.lecture_id, user, db, require_tutor=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rating_uid = str(user.id) if user else ""
    schedule: dict = {}
    with _db(req.lecture_id) as conn:
        _ensure_flashcard_ratings_table(conn)
        for item in req.ratings:
            prev = conn.execute(
                "SELECT easiness, reps, interval_days, due_at, last_reviewed_at "
                "FROM flashcard_ratings "
                "WHERE user_id=? AND lecture_id=? AND chapter_id=? AND card_key=?",
                (rating_uid, req.lecture_id, req.chapter_id or 0, item.card_key),
            ).fetchone()
            prior = None
            if prev:
                prior = {
                    "easiness": prev[0],
                    "reps": prev[1],
                    "interval_days": prev[2],
                    "due_at": prev[3] or "",
                    "last_reviewed_at": prev[4] or "",
                }
            state = apply_sm2(item.rating, state=prior, reviewed_at=now)
            conn.execute(
                "INSERT INTO flashcard_ratings "
                "(user_id, lecture_id, chapter_id, card_key, rating, updated_at, "
                " easiness, reps, interval_days, due_at, last_reviewed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, lecture_id, chapter_id, card_key) DO UPDATE SET "
                "rating=excluded.rating, updated_at=excluded.updated_at, "
                "easiness=excluded.easiness, reps=excluded.reps, "
                "interval_days=excluded.interval_days, due_at=excluded.due_at, "
                "last_reviewed_at=excluded.last_reviewed_at",
                (rating_uid, req.lecture_id, req.chapter_id or 0, item.card_key, item.rating,
                 now, state["easiness"], state["reps"], state["interval_days"],
                 state["due_at"], state["last_reviewed_at"]),
            )
            schedule[item.card_key] = {
                "rating": item.rating,
                "easiness": state["easiness"],
                "reps": state["reps"],
                "interval_days": state["interval_days"],
                "due_at": state["due_at"],
                "due_in_days": due_in_days(state),
                "last_reviewed_at": state["last_reviewed_at"],
            }
    return {"success": True, "count": len(req.ratings), "schedule": schedule}


@router.get("/flashcards/ratings")
async def get_flashcard_ratings(
    lecture_id: str = "default",
    chapter_id: int | None = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    with _db(lecture_id) as conn:
        _ensure_flashcard_ratings_table(conn)
        where = "WHERE lecture_id=? AND user_id=?"
        params: list = [lecture_id, str(user.id) if user else ""]
        if chapter_id is not None:
            where += " AND chapter_id=?"
            params.append(chapter_id)
        cursor = conn.execute(
            "SELECT card_key, rating, easiness, reps, interval_days, due_at, last_reviewed_at "
            f"FROM flashcard_ratings {where}",
            params,
        )
        rows = cursor.fetchall()
        ratings: dict = {}
        schedule: dict = {}
        for r in rows:
            key = r[0]
            ratings[key] = r[1]
            schedule[key] = {
                "rating": r[1],
                "easiness": r[2],
                "reps": r[3],
                "interval_days": r[4],
                "due_at": r[5],
                "due_in_days": due_in_days({"due_at": r[5]}),
                "last_reviewed_at": r[6],
            }
        return {"ratings": ratings, "schedule": schedule}


@router.get("/study-guide")
async def study_guide(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Catalog the already-generated per-chapter revision notes into one doc.

    Pure file reads — no LLM call. Returns {"title", "chapters": [{chapter_id,
    title, markdown}]} in chapter order.
    """
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    # Fall back to the legacy outputs/ root (same as /outline) so the
    # "default" demo lecture — which is never registered — still resolves.
    base = Path(info["output_dir"]) if info else Path("outputs")

    title = (info.get("name") or info.get("title") or "") if info else ""
    chapters: list[dict] = []

    outline_path = base / "notes" / "lecture_outline.json"
    chapter_ids: list[int] = []
    if outline_path.exists():
        try:
            outline = json_lib.loads(outline_path.read_text(encoding="utf-8"))
            for ch in outline.get("chapters", []):
                cid = ch.get("chapter_id") or ch.get("id")
                if cid is not None:
                    chapter_ids.append(int(cid))
        except Exception:
            pass
    if not chapter_ids:
        revision_dir = base / "revision"
        if revision_dir.exists():
            chapter_ids = sorted(
                int(p.stem.replace("revision_chapter_", ""))
                for p in revision_dir.glob("revision_chapter_*.md")
                if p.stem.replace("revision_chapter_", "").isdigit()
            )

    for cid in chapter_ids:
        path = base / "revision" / f"revision_chapter_{cid}.md"
        if not path.exists():
            continue
        chapters.append({
            "chapter_id": cid,
            "title": f"Chapter {cid}",
            "markdown": path.read_text(encoding="utf-8"),
        })

    if not chapters:
        raise HTTPException(status_code=404, detail="No revision notes found for this lecture")

    return {"title": title, "chapters": chapters}


@router.get("/flashcards")
async def flashcards(
    chapter_id: int | None = None,
    n: int | None = None,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "flashcards" / f"flashcards_chapter_{chapter_id}.json" if chapter_id else base / "flashcards" / "flashcards.json"
    if not path.exists():
        return []
    raw_data = json_lib.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw_data, dict):
        cards = raw_data.get("flashcards", [])
    elif isinstance(raw_data, list):
        cards = raw_data
    else:
        cards = []
    if n is not None and len(cards) > n:
        cards = random.sample(cards, n)
    return cards


@router.get("/flashcards/export")
async def export_flashcards(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Download the lecture's flashcard deck as an Anki `.apkg` file (P6.2).

    Pure file reads + a deterministic 0-LLM transform — never regenerates
    cards. Per-chapter files take priority (they carry chapter titles), with a
    fallback to the combined `flashcards.json`.
    """
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    if not info:
        raise HTTPException(status_code=404, detail="Lecture not found")
    base = Path(info["output_dir"])
    title = info.get("name") or info.get("title") or "Lecture"

    cards: list[dict] = []
    deck_dir = base / "flashcards"
    chapter_files = sorted(deck_dir.glob("flashcards_chapter_*.json"))
    if chapter_files:
        for p in chapter_files:
            raw = json_lib.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                cid = raw.get("chapter_id")
                ctitle = raw.get("chapter_title") or f"Chapter {cid}"
                chapter_cards = raw.get("flashcards", [])
            else:
                cid, ctitle, chapter_cards = None, "", raw
            for c in chapter_cards:
                cards.append({
                    "front": c.get("front", ""),
                    "back": c.get("back", ""),
                    "explanation": c.get("explanation", ""),
                    "chapter_title": ctitle,
                    "chapter_id": cid,
                })
    else:
        combined = deck_dir / "flashcards.json"
        if combined.exists():
            data = json_lib.loads(combined.read_text(encoding="utf-8"))
            for c in (data.get("flashcards", []) if isinstance(data, dict) else data):
                cards.append({
                    "front": c.get("front", ""),
                    "back": c.get("back", ""),
                    "explanation": c.get("explanation", ""),
                    "chapter_title": "",
                    "chapter_id": None,
                })

    if not cards:
        raise HTTPException(status_code=404, detail="No flashcards found for this lecture")

    safe_lecture = sanitize_lecture_id(lecture_id) or "lecture"
    payload = build_package(cards, deck_name=f"NorAI · {title}", lecture_tag=f"lecture:{safe_lecture}")
    return Response(
        content=payload,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="norai-{safe_lecture}.apkg"'},
    )


@router.get("/summary")
async def chapter_summary(
    chapter_id: int,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "revision" / f"revision_chapter_{chapter_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this chapter")
    return path.read_text(encoding="utf-8")


@router.get("/notes/{chapter_id}")
async def study_notes(
    chapter_id: int,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    json_path = base / "notes" / f"chapter_{chapter_id}.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            return json_lib.load(f)
    md_path = base / "notes" / f"chapter_{chapter_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Study notes not found")
    return md_path.read_text(encoding="utf-8")

@router.get("/screenshots/{chapter_id}")
async def chapter_screenshots(
    chapter_id: int,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "screenshots" / "selected" / f"chapter_{chapter_id}_screenshots.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json_lib.load(f)
    return data.get("screenshots", [])


@router.get("/video-map")
async def get_video_map(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """P6.3: per-lecture seek map (chapter + chunk timestamps) for click-to-video."""
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    return build_video_map(base)


@router.get("/outline")
async def get_outline(
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the lecture outline as JSON (for the sidebar chapter list)."""
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    base = Path(info["output_dir"]) if info else Path("outputs")
    path = base / "notes" / "lecture_outline.json"
    if not path.exists():
        return {"chapters": []}
    with open(path, encoding="utf-8") as f:
        return json_lib.load(f)


@router.get("/concept-map")
async def get_concept_map(
    chapter_id: int = 1,
    lecture_id: str = "default",
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Derive zero-LLM visual concept graph for a chapter from existing output JSONs."""
    await ensure_lecture_access(lecture_id, user, db)
    info = get_lecture(lecture_id)
    if info and "output_dir" in info and Path(info["output_dir"]).exists():
        base = Path(info["output_dir"])
    elif lecture_id and lecture_id != "default" and (Path("outputs") / lecture_id).exists():
        base = Path("outputs") / lecture_id
    else:
        base = Path("outputs")
    return build_concept_map(base, chapter_id)
