"""
backend/test_jobs_restart.py — P4 DoD offline test: the pipeline survives a
backend restart.

Simulates a worker crash + supervisor restart against a temp SQLite DB, with
NO Gemini / network calls (the pipeline runner is stubbed out):

  1. A job is stuck in 'processing' with a stale heartbeat (worker died
     mid-run / server restarted).
  2. The recovered supervisor re-queues it (attempt +1).
  3. A fresh supervisor pass claims it again and a re-run completes it.
  4. A job whose attempts are exhausted is failed instead of re-queued.
  5. A job with a FRESH heartbeat is left alone (not falsely recovered).
  6. A re-run that fails again is re-queued (retry semantics) until attempts
     are exhausted.

Run:
    python backend/test_jobs_restart.py
"""

import asyncio
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.jobs as jobs  # noqa: E402
from backend.db.database import Base  # noqa: E402
from backend.db.models import Lecture  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

PASSED = 0
FAILED = 0


def check(cond, label):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"PASS {label}")
    else:
        FAILED += 1
        print(f"FAIL {label}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _create_schema(url: str):
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _insert_lecture(factory, **fields):
    async with factory() as session:
        session.add(Lecture(**fields))
        await session.commit()


async def _get(factory, lecture_id: str):
    async with factory() as session:
        return await session.get(Lecture, lecture_id)


def _mk_url(tmp: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp}/jobs_test.db"


# ── Stubbed pipeline runners (no Gemini calls) ───────────────────────────────

def _ok_pipeline(task_id, source_type, url=None, file_path=None, user_id=None,
                 *, on_progress=None, should_cancel=None):
    if on_progress:
        on_progress("chunking", "Chunking transcript", 50)
    return {"ok": True}


def _fail_pipeline(task_id, source_type, url=None, file_path=None, user_id=None,
                   *, on_progress=None, should_cancel=None):
    raise RuntimeError("simulated transcription failure")


# ── Test 1: restart survival (P4 DoD) ────────────────────────────────────────

def test_restart_survival():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        url = _mk_url(tmp)
        asyncio.run(_create_schema(url))

        original_url, original_timeout = jobs.DATABASE_URL, jobs.PIPELINE_STUCK_TIMEOUT_SEC
        jobs.DATABASE_URL = url
        jobs.PIPELINE_STUCK_TIMEOUT_SEC = 0  # any heartbeat older than "now" is stale
        try:
            factory = jobs._make_session_factory()
            asyncio.run(_insert_lecture(
                factory,
                id="lec-1", user_id="u1", title="Test",
                source_type="youtube", source_url="https://example.com/vid.mp4",
                status="processing", attempts=0, stage="transcription",
                stage_message="Transcribing…", progress=30,
                queued_at=_utcnow() - timedelta(seconds=100),
                heartbeat_at=_utcnow() - timedelta(seconds=10),  # stale: worker died
            ))

            # Supervisor pass 1 after restart: recover the stuck job.
            recovered = asyncio.run(jobs._recover_stale_once(factory))
            check(recovered == 1, "restart: stale 'processing' job recovered")
            lec = asyncio.run(_get(factory, "lec-1"))
            check(lec.status == "queued", "restart: recovered job re-queued")
            check(lec.attempts == 1, "restart: attempts incremented on recovery")
            check(lec.started_at is None and lec.heartbeat_at is None,
                  "restart: started_at/heartbeat cleared on recovery")

            # Supervisor pass 2: claim + re-run it to completion.
            claimed = asyncio.run(jobs._claim_queued_once(factory))
            check(claimed == ["lec-1"], "restart: recovered job re-claimed")
            lec = asyncio.run(_get(factory, "lec-1"))
            check(lec.status == "processing" and lec.heartbeat_at is not None,
                  "restart: re-claimed job marked processing + heartbeating")

            original_pipeline = jobs.run_pipeline
            jobs.run_pipeline = _ok_pipeline  # stub the pipeline (no Gemini)
            try:
                jobs._run_job("lec-1")
            finally:
                jobs.run_pipeline = original_pipeline
            lec = asyncio.run(_get(factory, "lec-1"))
            check(lec.status == "completed", "restart: re-run completed after crash")
            check(lec.stage == "chunking" and lec.progress == 50,
                  "restart: progress persisted across crash+resume")
        finally:
            jobs.DATABASE_URL = original_url
            jobs.PIPELINE_STUCK_TIMEOUT_SEC = original_timeout


# ── Test 2: exhausted attempts → failed ──────────────────────────────────────

def test_attempts_exhausted_fails():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        url = _mk_url(tmp)
        asyncio.run(_create_schema(url))

        original_url, original_timeout = jobs.DATABASE_URL, jobs.PIPELINE_STUCK_TIMEOUT_SEC
        original_max = jobs.PIPELINE_MAX_ATTEMPTS
        jobs.DATABASE_URL = url
        jobs.PIPELINE_STUCK_TIMEOUT_SEC = 0
        jobs.PIPELINE_MAX_ATTEMPTS = 2
        try:
            factory = jobs._make_session_factory()
            asyncio.run(_insert_lecture(
                factory,
                id="lec-2", user_id="u1", title="Test",
                source_type="youtube", source_url="https://example.com/vid.mp4",
                status="processing", attempts=2,  # == PIPELINE_MAX_ATTEMPTS
                queued_at=_utcnow() - timedelta(seconds=100),
                heartbeat_at=_utcnow() - timedelta(seconds=10),
            ))
            recovered = asyncio.run(jobs._recover_stale_once(factory))
            check(recovered == 1, "exhausted: stale job surfaced")
            lec = asyncio.run(_get(factory, "lec-2"))
            check(lec.status == "failed", "exhausted: attempts exhausted → failed")
            check(lec.error_message and "interrupted" in lec.error_message,
                  "exhausted: failure reason recorded")
        finally:
            jobs.DATABASE_URL = original_url
            jobs.PIPELINE_STUCK_TIMEOUT_SEC = original_timeout
            jobs.PIPELINE_MAX_ATTEMPTS = original_max


# ── Test 3: fresh heartbeat is NOT falsely recovered ─────────────────────────

def test_fresh_heartbeat_not_recovered():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        url = _mk_url(tmp)
        asyncio.run(_create_schema(url))

        original_url, original_timeout = jobs.DATABASE_URL, jobs.PIPELINE_STUCK_TIMEOUT_SEC
        jobs.DATABASE_URL = url
        jobs.PIPELINE_STUCK_TIMEOUT_SEC = 3600  # huge timeout → live job must NOT be stale
        try:
            factory = jobs._make_session_factory()
            asyncio.run(_insert_lecture(
                factory,
                id="lec-3", user_id="u1", title="Test",
                source_type="youtube", source_url="https://example.com/vid.mp4",
                status="processing", attempts=0,
                heartbeat_at=_utcnow(),  # fresh — healthy worker
            ))
            recovered = asyncio.run(jobs._recover_stale_once(factory))
            check(recovered == 0, "fresh: live job not recovered")
            lec = asyncio.run(_get(factory, "lec-3"))
            check(lec.status == "processing" and lec.attempts == 0,
                  "fresh: live job left untouched")
        finally:
            jobs.DATABASE_URL = original_url
            jobs.PIPELINE_STUCK_TIMEOUT_SEC = original_timeout


# ── Test 4: failure mid-run re-queues while attempts remain ──────────────────

def test_failure_requeues_until_attempts_exhausted():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        url = _mk_url(tmp)
        asyncio.run(_create_schema(url))

        original_url, original_timeout = jobs.DATABASE_URL, jobs.PIPELINE_STUCK_TIMEOUT_SEC
        original_max = jobs.PIPELINE_MAX_ATTEMPTS
        jobs.DATABASE_URL = url
        jobs.PIPELINE_STUCK_TIMEOUT_SEC = 0
        jobs.PIPELINE_MAX_ATTEMPTS = 2
        try:
            factory = jobs._make_session_factory()
            asyncio.run(_insert_lecture(
                factory,
                id="lec-4", user_id="u1", title="Test",
                source_type="youtube", source_url="https://example.com/vid.mp4",
                status="queued", attempts=1,  # one prior (recovered) attempt
                queued_at=_utcnow() - timedelta(seconds=10),
            ))

            claimed = asyncio.run(jobs._claim_queued_once(factory))
            check(claimed == ["lec-4"], "retry: queued job claimed")

            original_pipeline = jobs.run_pipeline
            jobs.run_pipeline = _fail_pipeline
            try:
                jobs._run_job("lec-4")
            finally:
                jobs.run_pipeline = original_pipeline

            lec = asyncio.run(_get(factory, "lec-4"))
            check(lec.status == "queued", "retry: failure re-queued (attempts remain)")
            check(lec.attempts == 2, "retry: attempts incremented on failure")

            # Run it again to exhaust attempts → failed.
            claimed = asyncio.run(jobs._claim_queued_once(factory))
            check(claimed == ["lec-4"], "retry: re-claimed after failure")
            jobs.run_pipeline = _fail_pipeline
            try:
                jobs._run_job("lec-4")
            finally:
                jobs.run_pipeline = original_pipeline

            lec = asyncio.run(_get(factory, "lec-4"))
            check(lec.status == "failed", "retry: attempts exhausted → failed")
            check(lec.error_message and "simulated" in lec.error_message,
                  "retry: final error message recorded")
        finally:
            jobs.DATABASE_URL = original_url
            jobs.PIPELINE_STUCK_TIMEOUT_SEC = original_timeout
            jobs.PIPELINE_MAX_ATTEMPTS = original_max


if __name__ == "__main__":
    import traceback

    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except Exception:
                FAILED += 1
                print(f"FAIL {name} (exception)")
                traceback.print_exc()

    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
