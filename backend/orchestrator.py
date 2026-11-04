"""
backend/orchestrator.py

Complete NorAI pipeline for one source: intake (video download, or document
fetch + text extraction in documents/), plan limits, the lean content stages
(lean/pipeline.py), the tutor index, metering and cleanup.
Runs synchronously inside a worker thread owned by the P4.1 job queue
(backend/jobs.py). Progress is reported through the `on_progress` callback
(which persists to the Lecture row in the DB); cancellation is signalled by
`should_cancel` (checked between stages).

P4.5 — the old SSE scaffolding (`_queues` / `run_coroutine_threadsafe` against
a never-started event loop) is gone; the frontend polls `/process/{id}/status`,
which now reads the DB.
"""

import os
import json as json_lib
import shutil
import time
from pathlib import Path
from typing import Any


from backend.lecture_registry import create_lecture, update_lecture_title

# P1.8: call/batch counters + metrics recording for self-calibration.
from backend.ratelimit import snapshot_llm_calls
from tutor.embedding import snapshot_embed_batches
from backend.estimator import estimate_pipeline, record_metrics
# P2: persist Lecture status + meter quota minutes for the owning user.
from backend.usage import record_pipeline_outcome
# P6.5: per-stage ledger deltas feed one UsageLog row per stage.
from backend.usage_ledger import snapshot_usage, diff_usage

from documents.extract import DocumentError
from documents.fetch import FetchError
from documents.intake import prepare_source
from documents.kind import DOCUMENT
from lean.pipeline import run_content_stages, run_lean_stages
from config import dev_access
from backend.db.database import mark_lecture_dir

import logging
logger = logging.getLogger(__name__)


class PipelineCancelled(Exception):
    """Raised when the user requests cancellation and a stage boundary is hit."""


class TerminalPipelineError(ValueError):
    """P2.1: a validation error that retrying can never fix (e.g. lecture
    duration over the free-trial ceiling). The job queue must fail the run
    immediately instead of burning paid re-runs."""
    def __init__(self, message: str, friendly: str | None = None):
        super().__init__(message)
        self.friendly = friendly or message


# ── Cleanup (P4.2) ───────────────────────────────────────────────────────────

# Transient dirs always removed after a run, on success OR failure.
_TEMP_DIRS = ("videos", "audio", "screenshots/raw", "chunks", "metadata", "downloads")


def cleanup_lecture_dir(lecture_dir: Path) -> None:
    """Remove transient pipeline directories.

    `transcripts/`, `notes/`, `screenshots/keyframes/`, `visual_objects/` and
    `tutor/` are KEPT: they hold the hash-of-inputs cache markers + outputs
    that make re-runs cost ~0 API calls and give failed runs cheap retryable
    state.
    """
    try:
        for d in _TEMP_DIRS:
            target = Path(lecture_dir) / d
            if target.exists():
                shutil.rmtree(target)
        logger.info("Cleaned transient dirs under %s", lecture_dir)
    except Exception as e:
        logger.warning(f"Failed to clean intermediate dirs under {lecture_dir}: {e}")


# ── Plan limits ──────────────────────────────────────────────────────────────

def _enforce_plan_limits(duration_sec: float, user_id: str | None, prep) -> None:
    """Plan-aware caps (backend/plans.py), checked on the real length before
    any Gemini content call: /process can only check a probed length, and the
    probe fails on some videos (and never runs for documents)."""
    from backend.usage import meter_minutes, plan_limits

    enforce = (
        os.environ.get("ENFORCE_FREE_TRIAL_DURATION", "true").lower() == "true"
        and not dev_access()
    )
    if not enforce:
        return
    max_lecture_min, remaining_min = plan_limits(user_id)
    max_duration_sec = max_lecture_min * 60
    needed = meter_minutes(duration_sec)
    if prep.kind == DOCUMENT:
        what = f"This document ({prep.words:,} words) counts as {needed} lecture minutes"
    else:
        what = f"This lecture is {duration_sec / 60:.1f} minutes long"
    fix = "split the document" if prep.kind == DOCUMENT else "trim the video"
    if needed > remaining_min:
        raise TerminalPipelineError(
            f"Lecture needs {needed} quota minutes; {remaining_min} left.",
            friendly=(f"{what}, but you have {remaining_min} lecture minutes left this "
                      f"period. Get more time or {fix}."),
        )
    if duration_sec > max_duration_sec:
        raise TerminalPipelineError(
            f"Lecture duration ({duration_sec / 60:.1f} mins) exceeds the plan limit "
            f"of {max_duration_sec / 60:.0f} minutes.",
            friendly=(f"{what}, over your plan's {max_duration_sec / 60:.0f}-minute limit "
                      f"per lecture. Upgrade your plan or {fix}."),
        )


# ── Pipeline runner (SYNCHRONOUS — runs in a worker thread) ─────────────────

def run_pipeline(
    task_id: str,
    source_type: str,
    url: str | None = None,
    file_path: str | None = None,
    user_id: str | None = None,
    *,
    on_progress=None,
    should_cancel=None,
):
    """
    Run the full pipeline for a lecture. Raises PipelineCancelled on user
    cancellation, or the underlying exception on failure. `on_progress` is
    called with (stage, message, percent); `should_cancel()` is polled between
    stages.
    """
    # P1.8: snapshot counters + clock for the metrics record.
    _t_start = time.perf_counter()
    _llm_before = snapshot_llm_calls()
    _embed_before = snapshot_embed_batches()
    # P6.5: snapshot per-stage usage ledger before the run so we can diff after.
    _usage_before = snapshot_usage()
    _metrics: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lecture_id": task_id,
        "source_type": source_type,
        # Tags the entry for estimator calibration; entries without it came
        # from the retired legacy chain.
        "pipeline": "lean",
        "title": None,
        "duration_sec": None,
        "num_segments": None,
        "segments_per_chunk": None,
        "num_chunks": None,
        "num_chapters": None,
        "llm_calls": 0,
        "embed_batches": 0,
        "stage_seconds": {},
        "completed": False,
        "error": None,
        "planned": None,
    }

    def _write_metrics(completed: bool, error: str | None = None):
        _metrics["llm_calls"] = snapshot_llm_calls() - _llm_before
        _metrics["embed_batches"] = snapshot_embed_batches() - _embed_before
        _metrics["stage_seconds"]["pipeline"] = round(time.perf_counter() - _t_start, 2)
        _metrics["completed"] = completed
        _metrics["error"] = error
        try:
            record_metrics(_metrics)
        except Exception as e:
            logger.warning(f"Failed to record pipeline metrics: {e}")

    _last_percent = 0.0

    def _report(stage: str, message: str, percent: float):
        nonlocal _last_percent
        _last_percent = percent
        if on_progress:
            try:
                on_progress(stage, message, percent)
            except Exception as e:
                logger.warning(f"on_progress callback failed: {e}")

    def _check_cancel():
        if should_cancel and should_cancel():
            raise PipelineCancelled("Processing was cancelled by the user.")

    lecture_dir = None
    out: str | None = None
    try:
        # ── Create lecture directory ────────────────────────────────────────
        lecture_dir = create_lecture(task_id, title="New Lecture")
        mark_lecture_dir(lecture_dir)  # lets gc_sweep tell its own orphans apart
        out = str(lecture_dir)
        _check_cancel()

        # ── Stage 1: Intake (video download / document fetch + text extraction) ──
        _report("ingestion", "Downloading video…" if source_type == "youtube" else "Reading your file…", 2)
        try:
            prep = prepare_source(
                source_type, out, url=url,
                file_path=file_path if source_type == "upload" else None,
            )
        except (DocumentError, FetchError) as e:
            # Unreadable file / bad link: a retry can't fix it.
            raise TerminalPipelineError(str(e), friendly=str(e)) from e
        _check_cancel()
        _metrics["source_kind"] = prep.kind
        if prep.kind == DOCUMENT:
            duration_sec = float(prep.duration_sec or 0)
            _metrics.update(duration_sec=duration_sec, doc_type=prep.doc_type, words=prep.words)
        else:
            meta_path = prep.ingest["metadata_path"]
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    duration_sec = float(json_lib.load(f).get("duration", 0))
                _metrics["duration_sec"] = duration_sec
            except (OSError, ValueError, TypeError) as e:
                # Corrupt metadata is a warn-skip: the pipeline proceeds
                # without duration enforcement.
                logger.warning(f"Could not read video metadata ({meta_path}): {e}")
                duration_sec = None

        # ── Plan limits, on the real length (a document's words ÷ 150) ─────
        if duration_sec:
            _enforce_plan_limits(duration_sec, user_id, prep)

        # P1.8: record the pre-flight estimate (what /estimate would have shown).
        if _metrics["duration_sec"]:
            try:
                _metrics["planned"] = estimate_pipeline(
                    _metrics["duration_sec"] / 60.0,
                    source_type=source_type,
                    segments=_metrics["num_segments"],
                )
            except Exception as e:
                logger.warning(f"Failed to compute planned estimate: {e}")

        # ── Content: (transcription ∥ keyframes →) structure → chapters ─────
        if prep.kind == DOCUMENT:
            try:
                _metrics["num_segments"] = len(
                    json_lib.loads(Path(prep.transcript_path).read_text(encoding="utf-8"))["segments"]
                )
            except Exception:  # noqa: BLE001
                pass
            lean = run_content_stages(
                out, prep.transcript_path, None,
                source_title=prep.title, duration_sec=duration_sec, source_kind=DOCUMENT,
                report=_report, check_cancel=_check_cancel, metrics=_metrics,
            )
        else:
            ing = prep.ingest
            lean = run_lean_stages(
                out, ing["video_path"], ing["audio_path"], ing["metadata_path"],
                report=_report, check_cancel=_check_cancel, metrics=_metrics,
            )
        update_lecture_title(task_id, lean["outline"]["lecture_title"])

        # ── Tutor Index (notes + transcript + screenshots) ────
        _report("tutor_index", "Indexing for tutor…", 96)
        _check_cancel()
        _t_index = time.perf_counter()
        try:
            from tutor.indexing import build_lecture_index

            build_lecture_index(out)
        except Exception as e:
            logger.error(f"Tutor index failed (continuing): {e}")
        _metrics["stage_seconds"]["tutor_index"] = round(time.perf_counter() - _t_index, 2)

        # ── Done ───────────────────────────────────────────────────────────
        _write_metrics(completed=True)
        # P2: persist Lecture status + meter quota minutes (success only).
        try:
            record_pipeline_outcome(
                user_id=user_id,
                lecture_id=task_id,
                duration_sec=_metrics.get("duration_sec"),
                completed=True,
                title=_metrics.get("title"),
                output_dir=out,
                llm_calls=_metrics.get("llm_calls", 0),
                stage_usage=diff_usage(_usage_before),
            )
        except Exception as e:
            logger.warning(f"Failed to record pipeline usage outcome: {e}")
        _report("complete", "All done! Your workspace is ready.", 100)

    except PipelineCancelled as exc:
        _write_metrics(completed=False, error="cancelled")
        try:
            record_pipeline_outcome(
                user_id=user_id,
                lecture_id=task_id,
                duration_sec=_metrics.get("duration_sec"),
                completed=False,
                error_message="cancelled",
                output_dir=out,
            )
        except Exception as e:
            logger.warning(f"Failed to record pipeline cancellation outcome: {e}")
        raise

    except Exception as exc:
        _write_metrics(completed=False, error=str(exc))
        # P2: persist Lecture status='failed' (no quota metering on failure).
        try:
            record_pipeline_outcome(
                user_id=user_id,
                lecture_id=task_id,
                duration_sec=_metrics.get("duration_sec"),
                completed=False,
                error_message=str(exc)[:4000],
                output_dir=out,
            )
        except Exception as e:
            logger.warning(f"Failed to record pipeline failure outcome: {e}")
        raise

    finally:
        # P4.2: transient dirs are always removed (success, failure, or cancel).
        if lecture_dir is not None:
            cleanup_lecture_dir(lecture_dir)
