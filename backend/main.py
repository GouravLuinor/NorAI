"""
backend/main.py

Fix log:
  BUG-2  CORS origins widened to cover all common Vite dev ports.
  BUG-7  /threads POST now writes ONLY to user_threads (safe, app-owned table).
         It never touches the checkpoints table — LangGraph manages that schema
         and can use an incompatible column layout.
         GET /threads unions user_threads + checkpoints safely with try/except
         per table so a missing table never crashes the whole endpoint.
  BUG-4  GET /threads/{thread_id} now returns an empty message list (not 404)
         when the thread exists in user_threads but has no LangGraph checkpoint
         yet (brand new thread that hasn't received a message).
"""
import asyncio
import json as json_lib
import random
import secrets
import uuid
import re
import os
import shutil
from dotenv import load_dotenv

load_dotenv()
from backend import jobs
from contextlib import contextmanager, asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from typing import Any, List, Optional
import sqlite3
import time
from datetime import datetime, timezone
from backend.dependencies import get_lecture_db_path, _aget_or_create_lecture_graph, sanitize_lecture_id, configure_sqlite, ThreadDeletedError


from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from backend.access import (
    _GUEST_LECTURES_DAILY,
    _DEMO_TURNS_DAILY,
    _is_guest,
    _is_free_demo_access,
    _effective_persona_instructions,
    _assert_shared_or_404,
    ensure_lecture_access,
    _flush_tutor_usage_async,
)
from backend.lecture_db import (
    _db,
    _ensure_user_threads_table,
    _ensure_quiz_attempts_table,
    _ensure_quiz_attempts_correct_ids,
    _ensure_flashcard_schedule_columns,
)
from backend.lecture_registry import list_lectures, get_lecture
from ingest.ingest import is_youtube_url, is_gdrive_url, probe_video_metadata
from backend.estimator import estimate_pipeline
from backend.auth import get_current_user_optional, get_current_user
from backend.middleware import DailyCounter
from backend.timeutil import ensure_utc
from backend.db.database import get_db
from backend.db.models import User, Subscription, Lecture, UsageLog, Course, CourseLecture, ShareLink
from backend.usage import record_pipeline_outcome, rollover_if_needed
from tutor.llm import make_chat_llm
from config import (
    CHECKPOINT_DB_PATH,
    DEMO_LECTURE_IDS,
    LEMONSQUEEZY_CHECKOUT_STARTER_URL, LEMONSQUEEZY_CHECKOUT_PRO_URL,
    LEMONSQUEEZY_CUSTOMER_PORTAL_URL,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
import logging

# P5.1: structured JSON logging (console + rotating outputs/backend.log).
from backend.logging_config import setup_logging, bind, clear_context

setup_logging()

from backend.db.migrate import run_migrations
from backend.routers import billing as billing_router, courses as courses_router, quiz as quiz_router, webhooks
from backend.routers import content as content_router
from backend.routers import tutor as tutor_router


# ── Seeded Public Demo Workspaces ──────────────────────────────────────────────
# Three high-impact educational lectures permanently accessible to all users for free.
DEMO_LECTURES = [
    {
        "lecture_id": "ab648382-638f-4dde-b7c1-4007a2e638bb",
        "title": "Foundations of Neural Networks & Deep Learning",
        "duration_seconds": 1100,
        "chapter_count": 4,
        "category": "Computer Science & Deep Learning",
        "source_type": "youtube",
        "status": "completed",
        "is_demo": True,
    },
    {
        "lecture_id": "e54d7376-0e7b-472a-9ca6-9b21ad0b2710",
        "title": "Foundations of Economic Thinking: Incentives and Opportunity Cost",
        "duration_seconds": 1150,
        "chapter_count": 6,
        "category": "Economics & Market Theory",
        "source_type": "youtube",
        "status": "completed",
        "is_demo": True,
    },
    {
        "lecture_id": "506dd685-05f9-43df-8d09-5b944c7392f5",
        "title": "The Rise of Open-Weights Models and Local Deployment",
        "duration_seconds": 580,
        "chapter_count": 3,
        "category": "Modern AI Engineering",
        "source_type": "youtube",
        "status": "completed",
        "is_demo": True,
    },
]

DEMO_LECTURE_IDS = DEMO_LECTURE_IDS  # canonical set lives in config.py

def _demo_seed_complete(dst: Path) -> bool:
    """A demo workspace is fully seeded when its Chroma index is present.

    `backend/jobs.check_disk_completed` treats the same artifact as the
    completion signal, so a dir that exists without it (partial copy, GC
    damage, interrupted hydration) must be treated as NOT seeded.
    """
    return (dst / "tutor" / "chroma" / "chroma.sqlite3").is_file()


def sync_demo_seed_data():
    """Ensure pre-processed demo lecture artifacts are copied from seed_data/ into outputs/.

    Re-copies a demo dir when it is absent OR incomplete so a partial/broken
    seed self-heals on the next boot (P5.4).
    """
    seed_dir = Path("seed_data")
    outputs_dir = Path("outputs")
    if not seed_dir.exists():
        return
    outputs_dir.mkdir(parents=True, exist_ok=True)
    for demo in DEMO_LECTURES:
        lid = str(demo["lecture_id"])
        src = seed_dir / lid
        dst = outputs_dir / lid
        if not src.exists():
            continue
        if dst.exists() and _demo_seed_complete(dst):
            continue
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        try:
            shutil.copytree(str(src), str(dst))
            logging.getLogger("norai").info(f"Seeded demo lecture {lid} from seed_data/ to outputs/")
        except Exception as e:
            logging.getLogger("norai").warning(f"Failed to seed demo lecture {lid}: {e}")

    # Seed lectures.json if missing or merge entries
    seed_reg = seed_dir / "lectures.json"
    out_reg = outputs_dir / "lectures.json"
    if seed_reg.exists():
        try:
            with open(seed_reg, encoding="utf-8") as f:
                seed_data = json_lib.load(f)
            current_data = {}
            if out_reg.exists():
                try:
                    with open(out_reg, encoding="utf-8") as f:
                        current_data = json_lib.load(f)
                except Exception:
                    current_data = {}
            merged = False
            for k, v in seed_data.items():
                if k not in current_data:
                    current_data[k] = v
                    merged = True
            if merged or not out_reg.exists():
                with open(out_reg, "w", encoding="utf-8") as f:
                    json_lib.dump(current_data, f, indent=2)
        except Exception as e:
            logging.getLogger("norai").warning(f"Failed to merge seed_data/lectures.json: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # P4.3: versioned schema (Alembic) instead of create_all. Runs in a thread
    # because the alembic command is synchronous; idempotent on every boot.
    try:
        await asyncio.to_thread(run_migrations)
    except Exception as exc:
        logging.getLogger("norai").warning("Alembic migrations skipped on startup: %s", exc)

    # Seed permanent public demo lecture artifacts into outputs/ if not present
    try:
        await asyncio.to_thread(sync_demo_seed_data)
    except Exception as exc:
        logging.getLogger("norai").warning("Demo seed sync skipped on startup: %s", exc)

    # P4.1: boot the DB-backed pipeline queue supervisor, then one GC sweep
    # for stale uploads / orphaned lecture dirs.
    try:
        jobs.start_supervisor()
    except Exception as exc:
        logging.getLogger("norai").warning("Supervisor start skipped on startup: %s", exc)

    try:
        await asyncio.to_thread(jobs.gc_sweep)
    except Exception as exc:
        logging.getLogger("norai").warning("GC sweep skipped on startup: %s", exc)

    yield


is_prod = os.environ.get("NORAI_ENV") == "production"

app = FastAPI(
    title="NorAI Tutor API",
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """P5.1: tag every request with a request_id (accept/echo X-Request-ID)."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    bind(request_id=request_id)
    try:
        response = await call_next(request)
    except Exception:
        clear_context()
        raise
    response.headers["X-Request-ID"] = request_id
    clear_context()
    return response


import mimetypes
from fastapi.staticfiles import StaticFiles

# ── Explicit MIME Type Registration ──────────────────────────────────────────
# Debian-slim Docker images may lack /etc/mime.types. Register standard web
# extensions explicitly so CSS, JS, fonts, and images never default to text/plain.
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/png", ".png")
mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/jpeg", ".jpeg")

# ── SPA static serving (P5.4) ─────────────────────────────────────────────────
# When a production build of the frontend exists (frontend/dist), the backend
# serves it directly so a single container runs the whole app. Registered as a
# middleware + /assets StaticFiles mount + catch-all route.

SPA_DIST_DIR = Path(os.environ.get("NORAI_SPA_DIST", "frontend/dist")).resolve()


def _spa_index() -> Optional[Path]:
    candidate = SPA_DIST_DIR / "index.html"
    return candidate if candidate.is_file() else None


# Mount /assets directly with StaticFiles for high-performance asset serving
if SPA_DIST_DIR.exists() and (SPA_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(SPA_DIST_DIR / "assets")), name="spa_assets_mount")

# SPA client-side routes (everything Vite's history-mode router owns).
SPA_HTML_ROUTES = {"/", "/pricing", "/billing", "/usage", "/courses"}
SPA_HTML_PREFIXES = ("/app", "/workspace", "/process/", "/print", "/share/")


@app.middleware("http")
async def spa_middleware(request: Request, call_next):
    """Serve index.html for HTML navigations to client-side routes, mirroring
    the Vite dev proxy's /billing bypass. API fetches send Accept: */* or application/json
    (never pure text/html), so they still hit the JSON routes."""
    if request.method == "GET" and _spa_index() is not None:
        accept = request.headers.get("accept", "")
        path = request.url.path
        if "application/json" not in accept and "text/html" in accept and (
            path in SPA_HTML_ROUTES or path.startswith(SPA_HTML_PREFIXES)
        ):
            return FileResponse(SPA_DIST_DIR / "index.html", media_type="text/html")
    return await call_next(request)


app.include_router(webhooks.router)
# P5.1: domain routers (paths unchanged — mounted without prefixes).
app.include_router(billing_router.router)
app.include_router(courses_router.router)
app.include_router(quiz_router.router)
app.include_router(content_router.router)
app.include_router(tutor_router.router)

# Log the full detail of any unhandled exception server-side, but never leak
# raw exception text to clients.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger("norai").exception(
        "unhandled_exception",
        extra={"extra": {"path": request.url.path, "method": request.method}},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── CORS Configuration ────────────────────────────────────────────────────────
cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",   # vite preview
    "http://127.0.0.1:4173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Allow custom production domains via comma-separated NORAI_ALLOWED_ORIGINS
if extra_origins := os.environ.get("NORAI_ALLOWED_ORIGINS"):
    cors_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

# If running on Render, automatically add the external staging URL
if render_url := os.environ.get("RENDER_EXTERNAL_URL"):
    cors_origins.append(render_url.strip())

# P1.4 fail-closed: no wildcard origin regexes — only the explicit list above,
# NORAI_ALLOWED_ORIGINS, and RENDER_EXTERNAL_URL may be granted CORS access.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# P1.2/P1.3: inbound abuse protection. Starlette applies middleware
# outside-in from last-added to first, so SecurityHeaders (added last) wraps
# everything — including the rate limiter's 429 responses.
from backend.middleware import RateLimitMiddleware, SecurityHeadersMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

# Only image assets may be served under /static. Everything else that lives in
# outputs/ (transcripts, assessment answer keys, checkpoints.sqlite, Chroma
# DBs, backend.log) is never exposed over HTTP.
STATIC_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


def resolve_static_path(rest: str, base_dir: Optional[Path] = None) -> Path:
    """Resolve a /static/... path against the outputs dir with a strict allowlist."""
    base = (base_dir or Path("outputs")).resolve()
    target = (base / rest).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if target.suffix.lower() not in STATIC_ALLOWED_EXTENSIONS or not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return target


@app.get("/static/{rest:path}")
async def static_artifact(rest: str):
    return FileResponse(resolve_static_path(rest))



# ── Upload & Processing ──────────────────────────────────────────────────────

NORAI_DEV_ACCESS = (
    os.environ.get("NORAI_DEV_ACCESS", "0") == "1"
    or os.environ.get("NORAI_DEV_INSECURE_AUTH", "0") == "1"
)

# Fail closed: this flag silently bypasses lecture ownership checks. It must
# never be active when the process claims to run in production.
if is_prod and NORAI_DEV_ACCESS:
    raise RuntimeError(
        "Refusing to start: NORAI_DEV_ACCESS=1 disables lecture ownership "
        "checks and must never be set while NORAI_ENV=production."
    )


ALLOWED_SOURCE_TYPES = {"youtube", "gdrive", "upload"}

ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

# P1.5: magic-byte signatures per allowed extension. mp4/mov share the ISO
# BMFF 'ftyp' box; mkv/webm share the EBML header; avi is RIFF/AVI.
_MAGIC_CHECKS = {
    ".mp4": lambda h: len(h) >= 8 and h[4:8] == b"ftyp",
    ".mov": lambda h: len(h) >= 8 and h[4:8] == b"ftyp",
    ".mkv": lambda h: h.startswith(b"\x1a\x45\xdf\xa3"),
    ".webm": lambda h: h.startswith(b"\x1a\x45\xdf\xa3"),
    ".avi": lambda h: h.startswith(b"RIFF"),
}

MAX_UPLOAD_BYTES = int(os.environ.get("NORAI_MAX_UPLOAD_BYTES", str(2 * 1024**3)))  # default 2 GB
UPLOAD_CHUNK_BYTES = 1024 * 1024  # 1 MB


@app.post("/estimate")
async def estimate_cost(
    source_type: str = Form(...),
    url: str | None = Form(None),
    duration: float | None = Form(None),
    file: UploadFile | None = None,
):
    """Pre-flight estimate of Gemini calls + wall-clock time (P1.8).

    Probes the source duration cheaply (yt-dlp metadata-only for YouTube,
    ~2s; browser-reported duration for uploads), then returns the estimated
    call/time counts plus whether the lecture fits the free trial. Fails
    soft: when the duration can't be probed, returns {"available": false}
    and the frontend simply hides the estimate.
    """
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported source_type {source_type!r}")
    if source_type == "youtube":
        if not url or not is_youtube_url(url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        probed = probe_video_metadata(url)
        if not probed:
            return {"available": False, "reason": "Could not probe duration"}
        duration_min = probed["duration_sec"] / 60.0
        est = estimate_pipeline(duration_min, source_type="youtube")
        est.update({"available": True, "title": probed.get("title")})
        return est
    if source_type == "gdrive":
        if not url or not is_gdrive_url(url):
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL")
        # Drive durations can't be probed without downloading — no estimate.
        return {"available": False, "reason": "Google Drive durations are not probeable"}
    if source_type == "upload":
        if not file and duration is None:
            return {"available": False, "reason": "No file or duration provided"}
        if duration is None or duration <= 0:
            return {"available": False, "reason": "Could not read video duration"}
        est = estimate_pipeline(duration, source_type="upload")
        est.update({"available": True})
        return est
    raise HTTPException(status_code=400, detail="Unsupported source_type")


@app.post("/process")
async def start_processing(
    request: Request,
    source_type: str = Form(...),
    url: str | None = Form(None),
    file: UploadFile | None = None,
    duration: float | None = Form(None),
    course_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── P1.1: guest abuse cap (before any resource is consumed) ────────────
    if _is_guest(user):
        guest_ip = request.client.host if request.client else "unknown"
        if not _GUEST_LECTURES_DAILY.check_and_increment(guest_ip):
            raise HTTPException(
                status_code=429,
                detail="Free-trial limit reached (3 lectures per day per device). "
                       "Please sign up to continue.",
            )

    # ── Input validation (before any resource is consumed) ─────────────────
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported source_type {source_type!r}")
    if source_type == "upload":
        if not file:
            raise HTTPException(status_code=400, detail="source_type 'upload' requires a file")
    else:
        if not url:
            raise HTTPException(status_code=400, detail=f"source_type {source_type!r} requires a url")
        if source_type == "youtube" and not is_youtube_url(url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        if source_type == "gdrive" and not is_gdrive_url(url):
            raise HTTPException(status_code=400, detail="Invalid Google Drive URL")

    # ── Pre-download quota + free-trial enforcement (P2.2) ─────────────────
    # Check FIRST, then consume resources. The orchestrator's post-download
    # duration gate stays as a defense-in-depth backstop.
    # Dev escape hatch: NORAI_DEV_ACCESS=1 skips quota + duration limits for
    # local development (no paid plan needed to test long lectures).
    probed_sec = None
    if source_type == "youtube" and url:
        probed = probe_video_metadata(url)
        if probed:
            probed_sec = probed["duration_sec"]
    elif source_type == "upload" and duration and duration > 0:
        probed_sec = duration * 60.0

    if not NORAI_DEV_ACCESS:
        result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
        sub = result.scalar_one_or_none()
        # P0 fix: roll the billing period forward BEFORE comparing usage.
        # Rollover used to run only on pipeline completion — unreachable once
        # this gate 429s — which permanently locked expired-period users out.
        if sub is not None and rollover_if_needed(sub):
            await db.commit()
        quota = sub.monthly_minutes_quota if sub else 15
        used = sub.used_minutes_this_month if sub else 0
        if used >= quota:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly quota of {quota} lecture minutes reached. Please upgrade to Starter or Pro to continue processing.",
            )

        if probed_sec:
            import math as _math
            needed = _math.ceil(probed_sec / 60.0)
            free_limit_min = int(os.environ.get("MAX_FREE_DURATION_MIN", "15"))
            if probed_sec > free_limit_min * 60:
                raise HTTPException(
                    status_code=429,
                    detail=f"Lecture duration ({probed_sec / 60:.1f} mins) exceeds the free-trial limit "
                           f"of {free_limit_min} minutes. Please upgrade to Starter or Pro.",
                )
            if used + needed > quota:
                raise HTTPException(
                    status_code=429,
                    detail=f"This lecture needs ~{needed} of your {quota} monthly minutes "
                           f"({used} already used). Please upgrade to continue.",
                )

    task_id = str(uuid.uuid4())

    file_path = None
    if file:
        raw_name = Path(file.filename or "upload.mp4").name
        ext = Path(raw_name).suffix.lower()
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type {ext!r}. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
            )

        upload_dir = Path("outputs/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_name)
        file_path = upload_dir / f"{task_id}_{safe_filename}"

        # Stream-write in chunks (no full-file RAM buffer), enforcing a hard cap
        # even when Content-Length is absent.
        written = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                    )
                f.write(chunk)

        # P1.5: content sniffing — extension alone lets any payload through.
        with open(file_path, "rb") as f:
            head = f.read(16)
        if not _MAGIC_CHECKS[ext](head):
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=415,
                detail="File content doesn't match its extension. Please upload a real video file.",
            )

    # Record lecture in database (auth is now required). Status 'queued': the
    # P4.1 supervisor claims it, runs the pipeline in the worker pool, and owns
    # upload cleanup + progress/status persistence.
    lecture_record = Lecture(
        id=task_id,
        user_id=user.id,
        title="New Lecture",
        source_type=source_type,
        source_url=url or (str(file_path) if file_path else None),
        duration_seconds=int(probed_sec or 0),
        status="queued",
        queued_at=datetime.now(timezone.utc),
    )
    db.add(lecture_record)
    await db.commit()

    # P6.4: file the new lecture into the caller's course when one is given.
    if course_id:
        cresult = await db.execute(
            select(Course).where(Course.id == course_id, Course.user_id == user.id)
        )
        if cresult.scalar_one_or_none() is not None:
            max_pos = await db.execute(
                select(func.coalesce(func.max(CourseLecture.position), 0)).where(
                    CourseLecture.course_id == course_id
                )
            )
            db.add(
                CourseLecture(
                    course_id=course_id,
                    lecture_id=task_id,
                    position=max_pos.scalar_one() + 1,
                )
            )
            await db.commit()

    return {"task_id": task_id}

@app.get("/lectures")
async def get_lectures(
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """List lectures.

    Returns the unified list of all available lectures.
    Merges DB ownership records with on-disk lecture artifacts and seeded demo lectures.
    """
    registry_list = list_lectures()
    registry_map = {lec.get("lecture_id"): lec for lec in registry_list}
    seen_ids = set()
    out = []

    # 1. Always include the 3 permanent public demo workspaces
    for demo in DEMO_LECTURES:
        lid = str(demo["lecture_id"])
        seen_ids.add(lid)
        meta = registry_map.get(lid, {})
        out.append({
            "lecture_id": lid,
            "title": demo["title"],
            "status": "completed",
            "source_type": demo.get("source_type", "youtube"),
            "duration_seconds": demo["duration_seconds"],
            "chapter_count": meta.get("chapter_count", demo["chapter_count"]),
            "created_at": meta.get("created_at") or "2026-08-16T00:00:00Z",
            "output_dir": str(Path("outputs") / lid),
            "is_demo": True,
            "category": demo.get("category", "Demo"),
        })

    # 2. Fetch from DB if authenticated
    if user is not None:
        try:
            result = await db.execute(
                select(Lecture)
                .where(Lecture.user_id == user.id)
                .order_by(Lecture.created_at.desc())
            )
            rows = result.scalars().all()
            for row in rows:
                row_id = str(row.id)
                if row_id not in seen_ids:
                    seen_ids.add(row_id)
                    meta = registry_map.get(row_id, {})
                    out.append({
                        "lecture_id": row_id,
                        "title": meta.get("title") or row.title,
                        "status": row.status,
                        "source_type": row.source_type,
                        "duration_seconds": row.duration_seconds,
                        "chapter_count": meta.get("chapter_count", 0),
                        "created_at": meta.get("created_at") or (
                            row.created_at.isoformat() if row.created_at else None
                        ),
                        "output_dir": meta.get("output_dir"),
                        "is_demo": False,
                    })
        except Exception as exc:
            logging.getLogger("norai").warning("DB query failed in get_lectures: %s", exc)

    # 3. In dev mode or when unauthenticated, merge remaining disk registry lectures
    if user is None or NORAI_DEV_ACCESS:
        for lec in registry_list:
            lid = lec.get("lecture_id")
            if lid and lid not in seen_ids:
                seen_ids.add(lid)
                out.append(lec)

    # Sort newest first, keeping demos accessible
    return out




@app.get("/lectures/{lecture_id}")
async def get_lecture_info(
    lecture_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    try:
        clean_id = sanitize_lecture_id(lecture_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lecture_id format")
    await ensure_lecture_access(clean_id, user, db)
    info = get_lecture(clean_id)
    if not info:
        raise HTTPException(status_code=404, detail="Lecture not found")
    # P6.3: merge DB source fields so the frontend knows whether a YouTube
    # embed is possible (the registry itself only stores id/title/output_dir).
    row = (
        await db.execute(select(Lecture).where(Lecture.id == clean_id))
    ).scalar_one_or_none()
    info["source_type"] = row.source_type if row else None
    info["source_url"] = row.source_url if row else None
    info["status"] = row.status if row else None
    info["duration_seconds"] = row.duration_seconds if row else None
    return info


_PIPELINE_ERR_PATH_RE = re.compile(r"(?:[A-Za-z]:)?(?:/|\\)[^\s'\"`)\],]+")


def _sanitize_pipeline_error(message) -> str:
    """Scrub filesystem paths and internals from pipeline errors before they
    reach clients (raw tracebacks stay in logs only)."""
    text = str(message or "").strip()
    if not text:
        return ""
    text = _PIPELINE_ERR_PATH_RE.sub("[path]", text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return (lines[-1] if lines else "Pipeline failed.")[:300]


async def _assert_task_access(task_id: str, user: Optional[User], db: AsyncSession) -> None:
    """Ownership gate for pipeline task state (P6.4 hardening).

    Demo lectures stay public; DB-tracked lectures are visible to their owner
    or via a valid share link; legacy filesystem-only lectures (no Lecture row)
    keep working as before.
    """
    if task_id in (None, "", "default") or task_id in DEMO_LECTURE_IDS:
        return
    if NORAI_DEV_ACCESS and (
        get_lecture(task_id) is not None or (Path("outputs") / task_id).exists()
    ):
        return
    result = await db.execute(select(Lecture.id).where(Lecture.id == task_id))
    if result.scalar_one_or_none() is None:
        return  # legacy/local-registry lecture — no owner row to check
    if user is None:
        await _assert_shared_or_404(task_id, db)
        return
    owned = await db.execute(
        select(Lecture.id).where(Lecture.id == task_id, Lecture.user_id == user.id)
    )
    if owned.scalar_one_or_none() is None:
        await _assert_shared_or_404(task_id, db)


@app.get("/process/{task_id}/status")
async def get_task_status(
    task_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Return current progress as a single JSON object (P4.1 DB-backed)."""
    await _assert_task_access(task_id, user, db)
    try:
        status = await jobs.get_job_status(task_id)
    except Exception as exc:
        logging.getLogger("norai").warning("Error resolving status for task %s: %s", task_id, exc)
        status = None

    if status is None:
        if jobs.check_disk_completed(task_id):
            return {"stage": "complete", "message": "All done!", "progress": 100}
        raise HTTPException(status_code=404, detail="Task not found")

    # Map the DB lifecycle onto the legacy {stage, message, progress} contract
    # that ProcessingPage.tsx polls on ('complete'/'error' are terminal).
    if status.get("status") == "completed" or (status.get("progress") and status["progress"] >= 100):
        return {"stage": "complete", "message": "All done!", "progress": 100}
    if status.get("status") in ("failed", "cancelled"):
        return {
            "stage": "error",
            "message": _sanitize_pipeline_error(status.get("error_message")) or "Pipeline failed.",
            "progress": status.get("progress") or 0,
        }
    return {
        "stage": status.get("stage", "processing"),
        "message": status.get("message", "Processing…"),
        "progress": status.get("progress") or 0,
    }


@app.post("/process/{task_id}/cancel")
async def cancel_processing_task(
    task_id: str,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Request cancellation of a queued/running pipeline (P4.1)."""
    # Cancel is a destructive write: owner only (share viewers may watch, not stop).
    if task_id not in (None, "", "default") and task_id not in DEMO_LECTURE_IDS:
        if not NORAI_DEV_ACCESS:
            owned = await db.execute(
                select(Lecture.id).where(
                    Lecture.id == task_id,
                    Lecture.user_id == (user.id if user else "__anonymous__"),
                )
            )
            if owned.scalar_one_or_none() is None:
                raise HTTPException(status_code=404, detail="Task not found")
    cancelled = await jobs.request_cancel(task_id)
    if not cancelled:
        # P2.1: distinguish "no such task" from "already finished — nothing
        # to cancel" instead of lying with a success body either way.
        row = await db.get(Lecture, task_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if row.status in ("completed", "failed", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"This lecture already finished (status: {row.status}) — nothing to cancel.",
            )
        raise HTTPException(status_code=404, detail="Task not found")
    return {"cancelled": True}

# ── SPA fallback (P5.4) ───────────────────────────────────────────────────────
# Serve built frontend assets under /assets etc. when a production build is
# present; everything else is handled by the API routes + spa_middleware.

@app.get("/{path:path}", include_in_schema=False)
async def spa_assets(path: str):
    if _spa_index() is not None:
        candidate = (SPA_DIST_DIR / path).resolve()
        try:
            candidate.relative_to(SPA_DIST_DIR)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if candidate.is_file():
            mime_type, _ = mimetypes.guess_type(str(candidate))
            return FileResponse(candidate, media_type=mime_type or "application/octet-stream")
    raise HTTPException(status_code=404, detail="Not found")
