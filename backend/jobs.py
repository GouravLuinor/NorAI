"""
backend/jobs.py

P4.1 — DB-backed pipeline job queue + in-process worker pool.

Lifecycle (on the `lectures` row):

    queued -> processing -> completed
                        |-> queued (transient failure, attempts left)
                        |-> cancelled (user cancelled mid-run)
                        |-> failed (retries exhausted)

A supervisor thread (started once at app startup) polls the DB and:
  * recovers jobs stuck in 'processing' (stale heartbeat -> re-queue or fail),
  * claims 'queued' jobs within a global + per-user concurrency cap,
  * runs each claimed job in a bounded ThreadPoolExecutor,
  * applies retry-with-backoff on failure.

Because pipeline stages are cache-first (P1.3/P1.4), a re-run after a crash is
~0 Gemini calls — so recovering a stuck job is effectively a cheap resume.

All DB access uses a fresh per-call async engine (NullPool), the same pattern
as backend/usage.py, so it is safe to call from the worker threads.
"""

import asyncio
import logging
import re
import shutil
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import (
    DEMO_LECTURE_IDS,
    MAX_CONCURRENT_PIPELINES,
    MAX_PER_USER_PIPELINES,
    ORPHAN_DIR_GC_AGE_DAYS,
    PIPELINE_HEARTBEAT_INTERVAL_SEC,
    PIPELINE_MAX_ATTEMPTS,
    PIPELINE_MAX_RUNTIME_SEC,
    PIPELINE_POLL_INTERVAL_SEC,
    PIPELINE_STUCK_TIMEOUT_SEC,
    UPLOAD_GC_AGE_HOURS,
)
from backend.db.database import DATABASE_URL, get_engine_kwargs
from backend.db.models import Lecture
from backend.orchestrator import PipelineCancelled, TerminalPipelineError, run_pipeline
from backend.timeutil import ensure_utc as _normalize

logger = logging.getLogger(__name__)

_DEFAULT_UPLOAD_DIR = Path("outputs") / "uploads"
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


# P3.1: engine construction is not free and the 1.5s status poll used to pay
# it on every tick. Engines are cached per (running event loop, DATABASE_URL):
# an async engine's connections are bound to the loop that created them, and
# helpers here run under asyncio.run() from worker threads (a fresh loop per
# call), so a single module-level engine would be wrong — but the hot path
# (FastAPI's main loop) gets a stable cache hit. NullPool stays: pooled
# connections would outlive their creating loop.
_engine_cache_lock = threading.Lock()
_engine_cache: "OrderedDict[tuple[int, str], AsyncEngine]" = OrderedDict()
_ENGINE_CACHE_MAX = 16


def _get_engine() -> AsyncEngine:
    try:
        loop = asyncio.get_running_loop()
        key = (id(loop), DATABASE_URL)
    except RuntimeError:
        key = None  # no running loop → transient engine, nothing to reuse

    if key is None:
        return create_async_engine(DATABASE_URL, poolclass=NullPool, **get_engine_kwargs(DATABASE_URL))

    with _engine_cache_lock:
        eng = _engine_cache.get(key)
        if eng is None:
            eng = create_async_engine(DATABASE_URL, poolclass=NullPool, **get_engine_kwargs(DATABASE_URL))
            _engine_cache[key] = eng
            while len(_engine_cache) > _ENGINE_CACHE_MAX:
                _engine_cache.popitem(last=False)
        else:
            _engine_cache.move_to_end(key)
        return eng


def _make_session_factory():
    return async_sessionmaker(
        bind=_get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def _run_in_session(fn):
    factory = _make_session_factory()
    async with factory() as session:
        return await fn(session)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Progress / status persistence (called from the worker thread) ────────────

_live_progress: dict[str, dict] = {}
_live_progress_lock = threading.Lock()


def _update_live_progress(
    lecture_id: str,
    stage: str | None = None,
    message: str | None = None,
    percent: float | None = None,
    status: str | None = None,
    error_message: str | None = None,
):
    with _live_progress_lock:
        current = _live_progress.get(lecture_id, {})
        if stage is not None:
            current["stage"] = stage
        if message is not None:
            current["message"] = message
        if percent is not None:
            current["progress"] = percent
        if status is not None:
            current["status"] = status
        if error_message is not None:
            current["error_message"] = error_message
        current["updated_at"] = time.time()
        _live_progress[lecture_id] = current


def _get_live_progress(lecture_id: str) -> dict | None:
    with _live_progress_lock:
        return _live_progress.get(lecture_id)


_disk_completed_lock = threading.Lock()
# P3.1: artifact completion is terminal — once notes + chroma exist on disk
# they stay (there is no lecture-output deletion endpoint), so the 1.5s status
# poll can skip the three Path.exists stats after the first hit.
_disk_completed: set[str] = set()


def _invalidate_disk_completed(lecture_id: str):
    with _disk_completed_lock:
        _disk_completed.discard(lecture_id)


def check_disk_completed(lecture_id: str) -> bool:
    """Check if lecture artifacts are complete on disk."""
    if lecture_id in _disk_completed:
        return True
    lec_dir = Path("outputs") / lecture_id
    if not lec_dir.is_dir():
        return False
    notes_md = lec_dir / "notes" / "notes.md"
    outline_json = lec_dir / "notes" / "lecture_outline.json"
    chroma_db = lec_dir / "tutor" / "chroma" / "chroma.sqlite3"
    if (notes_md.exists() or outline_json.exists()) and chroma_db.exists():
        with _disk_completed_lock:
            _disk_completed.add(lecture_id)
        return True
    return False


def update_job_progress(lecture_id: str, stage: str | None, message: str | None, percent: float | None):
    """Persist stage/message/percent + refresh heartbeat. `stage=None` is a
    heartbeat-only refresh (long single stages must not look stuck). A None
    percent leaves the displayed progress untouched."""
    _update_live_progress(
        lecture_id,
        stage=stage,
        message=message,
        percent=percent,
        status="processing",
    )
    now = _utcnow()

    async def _do(session):
        lecture = await session.get(Lecture, lecture_id)
        if lecture is None:
            return
        if stage is not None:
            lecture.stage = stage
            if message is not None:
                lecture.stage_message = message[:4000]
            lecture.progress = percent
        lecture.heartbeat_at = now
        await session.commit()

    try:
        asyncio.run(_run_in_session(_do))
    except Exception as exc:
        logger.warning("Failed to persist progress for %s: %s", lecture_id, exc)


def _set_status(lecture_id: str, status: str, **fields):
    """Force a status + optional field updates on the Lecture row."""
    stage = "complete" if status == "completed" else ("error" if status in ("failed", "cancelled") else None)
    msg = "All done!" if status == "completed" else fields.get("error_message")
    pct = 100.0 if status == "completed" else None
    _update_live_progress(
        lecture_id,
        stage=stage,
        message=msg,
        percent=pct,
        status=status,
        error_message=fields.get("error_message"),
    )

    async def _do(session):
        lecture = await session.get(Lecture, lecture_id)
        if lecture is None:
            return
        lecture.status = status
        for key, value in fields.items():
            setattr(lecture, key, value)
        if status in ("completed", "failed", "cancelled"):
            lecture.heartbeat_at = _utcnow()
        await session.commit()

    try:
        asyncio.run(_run_in_session(_do))
    except Exception as exc:
        logger.warning("Failed to set status %r for %s: %s", status, lecture_id, exc)
    with _cancel_lock:
        _cancel_flags.pop(lecture_id, None)


# ── Cancellation ─────────────────────────────────────────────────────────────

_cancel_flags: dict[str, bool] = {}
_cancel_lock = threading.Lock()


def _is_cancel_requested(lecture_id: str) -> bool:
    with _cancel_lock:
        return _cancel_flags.get(lecture_id, False)


_TERMINAL_STATUSES = ("completed", "failed", "cancelled")


async def request_cancel(lecture_id: str) -> bool:
    """Persist cancel_requested + set the in-memory flag (async endpoint).

    P2.1: refuses to mark already-terminal jobs — a cancel against a
    completed/failed/cancelled lecture must not pretend it did anything.
    Returns True only when the cancel request was actually recorded.
    """
    async def _do(session):
        lecture = await session.get(Lecture, lecture_id)
        if lecture is None:
            return False
        if lecture.status in _TERMINAL_STATUSES:
            return False
        lecture.cancel_requested = True
        await session.commit()
        return True

    ok = await _run_in_session(_do)
    if ok:
        with _cancel_lock:
            _cancel_flags[lecture_id] = True
    return ok


# ── Supervisor: recovery + claiming ──────────────────────────────────────────

async def _recover_stale_once(session_factory) -> int:
    """Re-queue or fail 'processing' jobs whose heartbeat is stale."""
    cutoff = _utcnow() - timedelta(seconds=PIPELINE_STUCK_TIMEOUT_SEC)
    async with session_factory() as session:
        result = await session.execute(select(Lecture).where(Lecture.status == "processing"))
        recovered = 0
        for lecture in result.scalars():
            hb = _normalize(lecture.heartbeat_at)
            if hb is not None and hb >= cutoff:
                continue
            if (lecture.attempts or 0) < PIPELINE_MAX_ATTEMPTS:
                lecture.attempts = (lecture.attempts or 0) + 1
                lecture.status = "queued"
                lecture.started_at = None
                lecture.heartbeat_at = None
                logger.warning(
                    "Pipeline %s stalled (no heartbeat > %ss) — re-queued (attempt %d/%d)",
                    lecture.id, PIPELINE_STUCK_TIMEOUT_SEC, lecture.attempts, PIPELINE_MAX_ATTEMPTS,
                )
            else:
                lecture.status = "failed"
                lecture.error_message = (
                    f"Pipeline interrupted (server restart or timeout) after {PIPELINE_MAX_ATTEMPTS} attempts."
                )
                logger.error("Pipeline %s gave up after %d attempts", lecture.id, PIPELINE_MAX_ATTEMPTS)
            recovered += 1
        await session.commit()
    return recovered


async def _claim_queued_once(session_factory) -> list[str]:
    """Claim queued jobs that fit the global + per-user concurrency caps."""
    async with session_factory() as session:
        result = await session.execute(
            select(Lecture).where(Lecture.status == "queued").order_by(Lecture.queued_at)
        )
        queued = list(result.scalars())
        if not queued:
            return []

        run_result = await session.execute(select(Lecture).where(Lecture.status == "processing"))
        running = list(run_result.scalars())
        global_running = len(running)
        per_user: dict[str, int] = {}
        for lecture in running:
            per_user[lecture.user_id] = per_user.get(lecture.user_id, 0) + 1

        claimed = []
        now = _utcnow()
        for lecture in queued:
            if global_running >= MAX_CONCURRENT_PIPELINES:
                break
            if per_user.get(lecture.user_id, 0) >= MAX_PER_USER_PIPELINES:
                continue
            lecture.status = "processing"
            lecture.started_at = now
            lecture.heartbeat_at = now
            lecture.cancel_requested = False
            global_running += 1
            per_user[lecture.user_id] = per_user.get(lecture.user_id, 0) + 1
            claimed.append(lecture.id)
        await session.commit()
    return claimed


# ── Worker ───────────────────────────────────────────────────────────────────

async def _load_lecture(lecture_id: str):
    async def _do(session):
        return await session.get(Lecture, lecture_id)

    return await _run_in_session(_do)


def _resolve_upload_path(job) -> str | None:
    """Reconstruct the upload file path from source_url (only under outputs/uploads)."""
    if not job.source_url:
        return None
    path = Path(job.source_url)
    if _DEFAULT_UPLOAD_DIR not in path.parents and not str(path).startswith(str(_DEFAULT_UPLOAD_DIR)):
        return None
    return str(path) if path.exists() else None


def _heartbeat(lecture_id: str, stop: threading.Event):
    """Refresh the heartbeat while the pipeline runs.

    P2.1: heartbeats carry percent=None (never reset live progress to 0), and
    stop entirely once PIPELINE_MAX_RUNTIME_SEC has elapsed — a hung stage
    then looks stale to the supervisor, which re-queues or fails the job
    instead of holding a worker slot forever.
    """
    started = time.monotonic()
    capped = False
    while not stop.wait(PIPELINE_HEARTBEAT_INTERVAL_SEC):
        if not capped and time.monotonic() - started > PIPELINE_MAX_RUNTIME_SEC:
            capped = True
            logger.error(
                "Pipeline %s exceeded the %ss wall-clock cap — stopping heartbeats so "
                "the supervisor can recover it",
                lecture_id, PIPELINE_MAX_RUNTIME_SEC,
            )
        if capped:
            continue
        update_job_progress(lecture_id, None, None, None)


def _run_job(lecture_id: str):
    """Execute one lecture's pipeline in the executor; then finalise status."""
    from backend.logging_config import bind, clear_context
    bind(task_id=lecture_id, lecture_id=lecture_id)
    try:
        job = asyncio.run(_load_lecture(lecture_id))
        if job is None:
            logger.warning("Job %s disappeared before it could run", lecture_id)
            return

        url = job.source_url if job.source_type != "upload" else None
        file_path = _resolve_upload_path(job)

        stop = threading.Event()
        hb_thread = threading.Thread(target=_heartbeat, args=(lecture_id, stop), daemon=True)
        hb_thread.start()
        try:
            run_pipeline(
                lecture_id,
                job.source_type,
                url,
                file_path,
                job.user_id,
                on_progress=lambda s, m, p: update_job_progress(lecture_id, s, m, p),
                should_cancel=lambda: _is_cancel_requested(lecture_id),
            )
            _set_status(lecture_id, "completed")
            logger.info("Pipeline %s completed", lecture_id)
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning("Failed to delete upload %s: %s", file_path, e)
        except PipelineCancelled:
            _set_status(lecture_id, "cancelled", error_message="cancelled")
            logger.info("Pipeline %s cancelled by user", lecture_id)
            if file_path:
                try:
                    Path(file_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning("Failed to delete upload %s: %s", file_path, e)
        except Exception as exc:
            _handle_failure(lecture_id, exc, file_path=file_path)
        finally:
            stop.set()
            clear_context()
    except Exception as exc:
        logger.exception("Job runner crashed for %s: %s", lecture_id, exc)
        clear_context()


def _handle_failure(lecture_id: str, exc: Exception, file_path: str | None = None):
    from backend.rate_limit_handler import (
        GeminiCooldownTracker,
        GeminiDailyQuotaExceededException,
        is_daily_quota_exhausted,
    )
    if isinstance(exc, GeminiDailyQuotaExceededException) or is_daily_quota_exhausted(exc):
        GeminiCooldownTracker.record_daily_exhaustion()
        msg = "DAILY_QUOTA_EXHAUSTED: Free-tier daily limit reached. Service resumes at midnight Pacific Time."
        update_job_progress(lecture_id, "error", msg, 0.0)
        _set_status(lecture_id, "failed", error_message=msg)
        logger.error("Pipeline %s aborted due to Gemini daily quota limit: %s", lecture_id, exc)
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Failed to delete upload %s: %s", file_path, e)
        return

    # P2.1: validation errors can never succeed on retry — fail immediately
    # instead of burning PIPELINE_MAX_ATTEMPTS full paid re-runs.
    if isinstance(exc, TerminalPipelineError):
        update_job_progress(
            lecture_id,
            "error",
            exc.friendly[:4000],
            0.0,
        )
        _set_status(lecture_id, "failed", error_message=exc.friendly[:4000])
        logger.error("Pipeline %s failed terminally (no retry): %s", lecture_id, exc)
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Failed to delete upload %s: %s", file_path, e)
        return

    attempts = 0
    async def _get():
        async def _do(session):
            lecture = await session.get(Lecture, lecture_id)
            return lecture if lecture else None
        return await _run_in_session(_do)
    try:
        lecture_row = asyncio.run(_get())
        attempts = (lecture_row.attempts or 0) if lecture_row is not None else 0
    except Exception as db_exc:
        # P2.1: fail closed. If we cannot read the attempt counter, assume the
        # worst so an exhausted job can never loop through requeues forever.
        logger.error(
            "Could not read attempts for %s (%s) — treating as exhausted",
            lecture_id, db_exc,
        )
        attempts = PIPELINE_MAX_ATTEMPTS

    if attempts < PIPELINE_MAX_ATTEMPTS:
        update_job_progress(
            lecture_id,
            "retrying",
            f"Temporary issue encountered. Re-queuing (attempt {attempts + 1}/{PIPELINE_MAX_ATTEMPTS})…",
            0.0,
        )
        _set_status(lecture_id, "queued", attempts=attempts + 1, started_at=None, heartbeat_at=None)
        logger.info(
            "Pipeline %s failed (attempt %d/%d) — re-queued: %s",
            lecture_id, attempts + 1, PIPELINE_MAX_ATTEMPTS, exc,
        )
    else:
        update_job_progress(
            lecture_id,
            "error",
            str(exc)[:4000],
            0.0,
        )
        _set_status(lecture_id, "failed", error_message=str(exc)[:4000])
        logger.error("Pipeline %s failed permanently after %d attempts: %s", lecture_id, PIPELINE_MAX_ATTEMPTS, exc)
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning("Failed to delete upload %s: %s", file_path, e)


# ── GC (P4.2) ────────────────────────────────────────────────────────────────

async def _all_lecture_ids() -> set[str]:
    async def _do(session):
        result = await session.execute(select(Lecture.id))
        return {row[0] for row in result}

    return await _run_in_session(_do)


def gc_sweep():
    """Remove stale uploads and lecture dirs orphaned from the DB. Runs at boot."""
    now = _utcnow()

    if _DEFAULT_UPLOAD_DIR.exists():
        for f in _DEFAULT_UPLOAD_DIR.iterdir():
            try:
                if f.is_file() and now - datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) > timedelta(hours=UPLOAD_GC_AGE_HOURS):
                    f.unlink(missing_ok=True)
            except Exception as e:
                logger.warning("GC: failed to remove upload %s: %s", f, e)

    try:
        known = asyncio.run(_all_lecture_ids())
    except Exception as exc:
        logger.warning("GC: could not list lectures — skipping orphan sweep: %s", exc)
        return

    outputs = Path("outputs")
    if not outputs.exists():
        return
    for d in outputs.iterdir():
        if not d.is_dir() or not _UUID_RE.match(d.name):
            continue
        # The permanent public demo workspaces have no DB row by design — never GC them.
        if d.name in DEMO_LECTURE_IDS:
            continue
        if d.name in known:
            continue
        try:
            if now - datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc) > timedelta(days=ORPHAN_DIR_GC_AGE_DAYS):
                shutil.rmtree(d)
                logger.info("GC: removed orphaned lecture dir %s", d)
        except Exception as e:
            logger.warning("GC: failed to remove orphaned dir %s: %s", d, e)


# ── Supervisor thread ────────────────────────────────────────────────────────

_supervisor_thread: threading.Thread | None = None
_supervisor_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def start_supervisor():
    """Idempotently start the supervisor + executor. Call once from app startup."""
    global _supervisor_thread, _executor
    with _supervisor_lock:
        if _supervisor_thread is not None and _supervisor_thread.is_alive():
            return
        _executor = ThreadPoolExecutor(max_workers=max(1, MAX_CONCURRENT_PIPELINES))
        _supervisor_thread = threading.Thread(
            target=_supervisor_loop, daemon=True, name="pipeline-supervisor"
        )
        _supervisor_thread.start()
        logger.info(
            "Pipeline supervisor started (max concurrent=%d, max per user=%d, attempts=%d)",
            MAX_CONCURRENT_PIPELINES, MAX_PER_USER_PIPELINES, PIPELINE_MAX_ATTEMPTS,
        )


def _supervisor_loop():
    # NOTE: single-process assumption. Multiple uvicorn workers would each start
    # a supervisor; add a DB claim-lock if the app ever runs --workers > 1.
    next_gc = time.monotonic()
    while True:
        try:
            recovered = asyncio.run(_recover_stale_once(_make_session_factory()))
            if recovered:
                logger.info("Supervisor recovered %d stalled pipeline(s)", recovered)
            claimed = asyncio.run(_claim_queued_once(_make_session_factory()))
            for lecture_id in claimed:
                logger.info("Supervisor: starting pipeline %s", lecture_id)
                if _executor is not None:
                    _executor.submit(_run_job, lecture_id)
            if time.monotonic() - next_gc >= 86400:
                next_gc = time.monotonic()
                gc_sweep()
        except Exception as exc:
            logger.exception("Supervisor loop error: %s", exc)
        time.sleep(PIPELINE_POLL_INTERVAL_SEC)


# ── Status (async, for the /process/{id}/status endpoint) ───────────────────

async def get_job_status(lecture_id: str) -> dict | None:
    # 1. P2.1: the DB row is the source of truth. A job cancelled or failed
    # after artifacts landed on disk must report its real status, so disk
    # checks only apply when there is no row (legacy/demo lectures) or the
    # DB is unreachable.
    try:
        async def _do(session):
            lecture = await session.get(Lecture, lecture_id)
            if lecture is None:
                return None
            return {
                "status": lecture.status,
                "stage": lecture.stage,
                "message": lecture.stage_message,
                "progress": lecture.progress,
                "error_message": lecture.error_message,
            }

        status = await _run_in_session(_do)
        if status:
            if status.get("status") == "completed" or (
                status.get("status") != "failed"
                and status.get("status") != "cancelled"
                and status.get("progress")
                and status["progress"] >= 100.0
            ):
                status["status"] = "completed"
                status["stage"] = "complete"
                status["message"] = "All done!"
                status["progress"] = 100.0
            return status
    except Exception as exc:
        logger.warning("DB get_job_status failed for %s: %s", lecture_id, exc)

    # 2. No DB row (or DB down): fall back to artifact completion on disk.
    if check_disk_completed(lecture_id):
        return {
            "status": "completed",
            "stage": "complete",
            "message": "All done!",
            "progress": 100.0,
            "error_message": None,
        }

    # 3. Try in-memory live progress
    live = _get_live_progress(lecture_id)
    if live:
        status_val = live.get("status", "processing")
        stage_val = live.get("stage", "processing")
        if status_val == "completed" or (live.get("progress") and live["progress"] >= 100.0):
            status_val = "completed"
            stage_val = "complete"
        return {
            "status": status_val,
            "stage": stage_val,
            "message": live.get("message", "Processing…"),
            "progress": live.get("progress", 0.0),
            "error_message": live.get("error_message"),
        }

    # 4. Check registry or directory presence
    lec_dir = Path("outputs") / lecture_id
    if lec_dir.is_dir():
        outline = lec_dir / "notes" / "lecture_outline.json"
        if outline.exists():
            return {
                "status": "completed",
                "stage": "complete",
                "message": "All done!",
                "progress": 100.0,
                "error_message": None,
            }

    return None
