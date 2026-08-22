"""
backend/routers/courses.py — course collections + lecture share links (P5.1).

Extracted verbatim from main.py; mounted without prefixes so paths are
unchanged.
"""

import json
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.access import ensure_lecture_access
from backend.auth import get_current_user, get_current_user_optional
from backend.db.database import get_db
from backend.db.models import Course, CourseLecture, Lecture, ShareLink, User
from backend.dependencies import sanitize_lecture_id
from backend.timeutil import ensure_utc
from backend.lecture_registry import list_lectures
from config import DEMO_LECTURE_IDS

router = APIRouter()


class CourseCreateRequest(BaseModel):
    name: str
    description: str | None = None


class CourseUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class AddLectureRequest(BaseModel):
    lecture_id: str


class ReorderLecturesRequest(BaseModel):
    lecture_ids: list[str] = []


class ShareLinkRequest(BaseModel):
    allow_tutor_chat: bool = True


def _app_origin(request: Optional[Request] = None) -> str:
    """Browser origin used to build share URLs (Render staging / custom domain / dev)."""
    if app_url := os.environ.get("NORAI_APP_URL"):
        return app_url.rstrip("/")
    if render_url := os.environ.get("RENDER_EXTERNAL_URL"):
        return render_url.rstrip("/")
    if request is not None:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
        if host:
            return f"{proto}://{host}".rstrip("/")
    return "http://localhost:5173"


def _new_share_slug() -> str:
    return secrets.token_urlsafe(12)


async def _get_owned_course(course_id: str, user: User, db: AsyncSession) -> Course:
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.user_id == user.id)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _registry_map() -> dict:
    return {lec.get("lecture_id"): lec for lec in list_lectures()}


def _lecture_listing(row: Lecture, meta: dict) -> dict:
    return {
        "lecture_id": row.id,
        "title": meta.get("title") or row.title,
        "status": row.status,
        "source_type": row.source_type,
        "duration_seconds": row.duration_seconds,
        "chapter_count": meta.get("chapter_count", 0),
        "created_at": meta.get("created_at") or (
            row.created_at.isoformat() if row.created_at else None
        ),
    }


@router.get("/courses")
async def list_courses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Course).where(Course.user_id == user.id).order_by(Course.created_at.desc())
    )
    courses = result.scalars().all()
    out = []
    for c in courses:
        count = await db.execute(
            select(func.count())
            .select_from(CourseLecture)
            .where(CourseLecture.course_id == c.id)
        )
        out.append({
            "course_id": c.id,
            "name": c.name,
            "description": c.description,
            "lecture_count": count.scalar_one(),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"courses": out}


@router.post("/courses")
async def create_course(
    req: CourseCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Course name is required")
    course = Course(user_id=user.id, name=name[:256], description=req.description)
    db.add(course)
    await db.commit()
    return {
        "course_id": course.id,
        "name": course.name,
        "description": course.description,
        "lecture_count": 0,
    }


@router.get("/courses/{course_id}")
async def get_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await _get_owned_course(course_id, user, db)
    links = (
        await db.execute(
            select(CourseLecture)
            .where(CourseLecture.course_id == course_id)
            .order_by(CourseLecture.position)
        )
    ).scalars().all()
    registry = _registry_map()
    lectures = []
    for link in links:
        row = (
            await db.execute(select(Lecture).where(Lecture.id == link.lecture_id))
        ).scalar_one_or_none()
        if row is None:
            continue
        lectures.append(_lecture_listing(row, registry.get(row.id, {})))
    return {
        "course_id": course.id,
        "name": course.name,
        "description": course.description,
        "lectures": lectures,
    }


@router.patch("/courses/{course_id}")
async def update_course(
    course_id: str,
    req: CourseUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await _get_owned_course(course_id, user, db)
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Course name cannot be empty")
        course.name = name[:256]
    if req.description is not None:
        course.description = req.description
    await db.commit()
    return {
        "course_id": course.id,
        "name": course.name,
        "description": course.description,
    }


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await _get_owned_course(course_id, user, db)
    await db.delete(course)
    await db.commit()
    return {"success": True}


@router.post("/courses/{course_id}/lectures")
async def add_lecture_to_course(
    course_id: str,
    req: AddLectureRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_course(course_id, user, db)
    result = await db.execute(
        select(Lecture).where(Lecture.id == req.lecture_id, Lecture.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Lecture not found")

    existing = await db.execute(
        select(CourseLecture).where(
            CourseLecture.course_id == course_id,
            CourseLecture.lecture_id == req.lecture_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        max_pos = await db.execute(
            select(func.coalesce(func.max(CourseLecture.position), 0)).where(
                CourseLecture.course_id == course_id
            )
        )
        db.add(
            CourseLecture(
                course_id=course_id,
                lecture_id=req.lecture_id,
                position=max_pos.scalar_one() + 1,
            )
        )
        await db.commit()
    return {"success": True, "course_id": course_id, "lecture_id": req.lecture_id}


@router.delete("/courses/{course_id}/lectures/{lecture_id}")
async def remove_lecture_from_course(
    course_id: str,
    lecture_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_course(course_id, user, db)
    result = await db.execute(
        select(CourseLecture).where(
            CourseLecture.course_id == course_id,
            CourseLecture.lecture_id == lecture_id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()
    return {"success": True}


@router.put("/courses/{course_id}/lectures")
async def reorder_course_lectures(
    course_id: str,
    req: ReorderLecturesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_course(course_id, user, db)
    for position, lecture_id in enumerate(req.lecture_ids):
        result = await db.execute(
            select(CourseLecture).where(
                CourseLecture.course_id == course_id,
                CourseLecture.lecture_id == lecture_id,
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=400, detail=f"Lecture {lecture_id} is not in this course"
            )
        link.position = position
    await db.commit()
    return {"success": True}


# ---------------------------------------------------------------------------
# P6.4 — Share links (owner creates/revokes; viewers read via the slug)
# ---------------------------------------------------------------------------

@router.post("/lectures/{lecture_id}/share")
async def create_share_link(
    lecture_id: str,
    request: Request,
    req: ShareLinkRequest | None = None,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS

    if not is_demo:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        result = await db.execute(
            select(Lecture).where(Lecture.id == clean_id, Lecture.user_id == user.id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Lecture not found")

    creator_id = user.id if user else "demo-user"
    allow_tutor_chat = req.allow_tutor_chat if req is not None else True

    existing = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == creator_id,
        )
    )
    link = existing.scalar_one_or_none()
    if link is None:
        link = ShareLink(
            id=_new_share_slug(),
            lecture_id=clean_id,
            created_by=creator_id,
            allow_tutor_chat=allow_tutor_chat,
        )
        db.add(link)
    else:
        # Re-sharing refreshes the existing slug (re-enabling an expired link).
        link.allow_tutor_chat = allow_tutor_chat
        link.expires_at = None
    await db.commit()
    return {
        "slug": link.id,
        "url": f"{_app_origin(request)}/share/{link.id}",
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@router.get("/lectures/{lecture_id}/share")
async def get_share_link(
    lecture_id: str,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return the owner's or demo's existing share link for a lecture, or 404 if none."""
    clean_id = sanitize_lecture_id(lecture_id)
    is_demo = clean_id in DEMO_LECTURE_IDS
    creator_id = user.id if user else "demo-user"

    query = select(ShareLink).where(ShareLink.lecture_id == clean_id)
    if not is_demo:
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        query = query.where(ShareLink.created_by == user.id)

    result = await db.execute(query)
    link = result.scalar_one_or_none()
    if link is None:
        if is_demo:
            # Auto-provision a public share link for demo lectures on first request
            link = ShareLink(
                id=_new_share_slug(),
                lecture_id=clean_id,
                created_by=creator_id,
                allow_tutor_chat=True,
            )
            db.add(link)
            await db.commit()
        else:
            raise HTTPException(status_code=404, detail="No share link exists for this lecture")

    return {
        "slug": link.id,
        "url": f"{_app_origin(request)}/share/{link.id}",
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@router.patch("/lectures/{lecture_id}/share")
async def update_share_link(
    lecture_id: str,
    req: ShareLinkRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = sanitize_lecture_id(lecture_id)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == user.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="No share link exists for this lecture")
    link.allow_tutor_chat = req.allow_tutor_chat
    await db.commit()
    return {
        "slug": link.id,
        "url": f"{_app_origin(request)}/share/{link.id}",
        "allow_tutor_chat": link.allow_tutor_chat,
    }


@router.delete("/lectures/{lecture_id}/share")
async def delete_share_link(
    lecture_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean_id = sanitize_lecture_id(lecture_id)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.lecture_id == clean_id,
            ShareLink.created_by == user.id,
        )
    )
    link = result.scalar_one_or_none()
    if link is not None:
        await db.delete(link)
        await db.commit()
    return {"success": True}


@router.get("/share/{slug}")
async def resolve_share_link(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Resolve an unlisted share slug to a lecture the viewer may open.

    Public (no auth required): anyone holding the link may read the lecture's
    artifacts. Returns only navigation metadata — never source URLs.
    """
    result = await db.execute(select(ShareLink).where(ShareLink.id == slug))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    now = datetime.now(timezone.utc)
    if link.expires_at is not None:
        expires_at = ensure_utc(link.expires_at)  # SQLite stores naive UTC
        if expires_at < now:
            raise HTTPException(status_code=404, detail="Share link has expired")
    lecture = (
        await db.execute(select(Lecture).where(Lecture.id == link.lecture_id))
    ).scalar_one_or_none()

    if lecture is None:
        if str(link.lecture_id) in DEMO_LECTURE_IDS:
            meta = get_lecture(str(link.lecture_id))
            return {
                "lecture_id": str(link.lecture_id),
                "title": (meta.get("title") if meta else None) or "Demo Lecture",
                "status": "completed",
                "source_type": "youtube",
                "allow_tutor_chat": link.allow_tutor_chat,
            }
        raise HTTPException(status_code=404, detail="Lecture not found")

    return {
        "lecture_id": lecture.id,
        "title": lecture.title,
        "status": lecture.status,
        "source_type": lecture.source_type,
        "allow_tutor_chat": link.allow_tutor_chat,
    }
