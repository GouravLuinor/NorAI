"""
backend/orchestrator.py

Complete NorAI pipeline: runs every stage for a single video source,
emitting real‑time progress via SSE queues.
"""

import os
import json as json_lib
import asyncio
import hashlib
import subprocess
import threading
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field


from backend.lecture_registry import create_lecture, update_lecture_title

# P1.8: call/batch counters + metrics recording for self-calibration.
from backend.ratelimit import snapshot_llm_calls
from tutor.embedding import snapshot_embed_batches
from backend.estimator import estimate_pipeline, record_metrics
# P2: persist Lecture status + meter quota minutes for the owning user.
from backend.usage import record_pipeline_outcome

# ── All pipeline imports ────────────────────────────────────────────────────
from ingest.ingest import process_source
from transcription.transcribe import transcribe_audio
from chunking.chunk import chunk_transcript
from extract.extractor import extract_all_chunks
from visual.extract_frames import extract_frames
from visual.scene_detector import detect_scenes
from visual.mapper import create_chunk_screenshot_mapping
from visual.visual_extractor import process_all_chunks as process_visual_chunks
from extract.merger import merge_all_chunks
from notes.chapter_builder import build_chapters_pipeline
from notes.notes_generator import generate_study_notes, generate_consolidated_chapter_artifacts
from notes.screenshot_selector import select_screenshots_for_lecture
from notes.outline_generator import generate_lecture_outline

import logging
logger = logging.getLogger(__name__)

# ── Progress tracking ───────────────────────────────────────────────────────

@dataclass
class TaskProgress:
    task_id: str
    stage: str = "starting"
    message: str = "Initialising…"
    percent: float = 0.0
    finished: bool = False
    error: str | None = None
    _queues: list[asyncio.Queue] = field(default_factory=list)

    def register_queue(self, q: asyncio.Queue):
        self._queues.append(q)

    def remove_queue(self, q: asyncio.Queue):
        self._queues = [x for x in self._queues if x is not q]


_progress: dict[str, TaskProgress] = {}
_sync_lock = threading.Lock()

# Event loop reference for thread-safe broadcasting
_event_loop = None

def _get_event_loop():
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
    return _event_loop


def get_or_create_task_sync(task_id: str) -> TaskProgress:
    with _sync_lock:
        if task_id not in _progress:
            _progress[task_id] = TaskProgress(task_id=task_id)
        return _progress[task_id]


def update_progress_sync(task_id: str, stage: str, message: str, percent: float):
    tp = get_or_create_task_sync(task_id)
    tp.stage = stage
    tp.message = message
    tp.percent = percent
    loop = _get_event_loop()
    for q in tp._queues:
        asyncio.run_coroutine_threadsafe(q.put({
            "stage": stage, "message": message, "progress": percent,
        }), loop)


def mark_error_sync(task_id: str, message: str):
    tp = get_or_create_task_sync(task_id)
    tp.error = message
    tp.finished = True
    loop = _get_event_loop()
    for q in tp._queues:
        asyncio.run_coroutine_threadsafe(q.put({
            "stage": "error", "message": message, "progress": tp.percent,
        }), loop)


def mark_complete_sync(task_id: str):
    tp = get_or_create_task_sync(task_id)
    tp.finished = True
    loop = _get_event_loop()
    for q in tp._queues:
        asyncio.run_coroutine_threadsafe(q.put({
            "stage": "complete",
            "message": "All done! Your workspace is ready.",
            "progress": 100,
        }), loop)


    
# ── Pipeline runner (SYNCHRONOUS — runs in a background thread) ─────────────

def run_pipeline(
    task_id: str,
    source_type: str,
    url: str | None = None,
    file_path: str | None = None,
    user_id: str | None = None,
):
    # P1.8: snapshot counters + clock for the metrics record.
    import time
    _t_start = time.perf_counter()
    _llm_before = snapshot_llm_calls()
    _embed_before = snapshot_embed_batches()
    _metrics = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lecture_id": task_id,
        "source_type": source_type,
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

    try:
        # ── Create lecture directory ────────────────────────────────────────
        lecture_dir = create_lecture(task_id, title="New Lecture")
        out = str(lecture_dir)

        # ── Stage 1: Ingestion ─────────────────────────────────────────────
        update_progress_sync(task_id, "ingestion", "Downloading video…", 2)
        source = file_path if (source_type == "upload" and file_path) else (url or "")
        ing = process_source(source, output_dir=out)
        video_path  = ing["video_path"]
        audio_path  = ing["audio_path"]
        meta_path   = ing["metadata_path"]

        # ── Duration check (Free Trial Limit: 15 mins) ────────────────────
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta_data = json_lib.load(f)
                duration_sec = float(meta_data.get("duration", 0))
            _metrics["duration_sec"] = duration_sec

            max_duration_sec = int(os.environ.get("MAX_FREE_DURATION_MIN", "15")) * 60
            if duration_sec > max_duration_sec and os.environ.get("ENFORCE_FREE_TRIAL_DURATION", "true").lower() == "true":
                raise ValueError(
                    f"Lecture duration ({duration_sec / 60:.1f} mins) exceeds the Free Trial limit "
                    f"of {max_duration_sec / 60:.0f} minutes. Please upgrade to Starter or Pro."
                )
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Could not verify video duration: {e}")

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


        # ── Stage 2-6: Parallel Processing (Text Branch & Visual Branch) ────
        from concurrent.futures import ThreadPoolExecutor

        def _run_text_branch():
            update_progress_sync(task_id, "transcription", "Transcribing lecture…", 8)
            _t_tr = time.perf_counter()
            tr = transcribe_audio(audio_path, meta_path, output_dir=out)
            _metrics["stage_seconds"]["transcription"] = round(time.perf_counter() - _t_tr, 2)
            t_json = tr["transcript_json_path"]
            try:
                with open(t_json, encoding="utf-8") as _f:
                    _tr = json_lib.load(_f)
                _metrics["num_segments"] = len(_tr.get("segments", []))
            except Exception:
                pass

            update_progress_sync(task_id, "chunking", "Chunking transcript…", 14)
            ch = chunk_transcript(t_json, output_dir=out)
            c_path = ch["chunks_path"]
            _metrics["num_chunks"] = ch.get("num_chunks")
            _metrics["segments_per_chunk"] = ch.get("segments_per_chunk")

            update_progress_sync(task_id, "knowledge_extraction", "Extracting knowledge…", 20)
            ke = extract_all_chunks(c_path, output_dir=out)
            o_dir = ke["objects_dir"]
            return c_path, o_dir

        def _run_visual_branch():
            update_progress_sync(task_id, "frame_extraction", "Extracting frames…", 26)
            raw_dir = str(lecture_dir / "screenshots" / "raw")
            fe = extract_frames(video_path, raw_dir)
            f_meta = fe["metadata_file"]

            update_progress_sync(task_id, "scene_detection", "Detecting key scenes…", 32)
            keyframes_dir = str(lecture_dir / "screenshots" / "keyframes")
            detect_scenes(f_meta, keyframes_dir)
            kf_meta = str(Path(keyframes_dir) / "metadata.json")
            return kf_meta

        with ThreadPoolExecutor(max_workers=2) as exec_pipe:
            fut_text = exec_pipe.submit(_run_text_branch)
            fut_visual = exec_pipe.submit(_run_visual_branch)
            chunks_path, objects_dir = fut_text.result()
            keyframes_meta = fut_visual.result()

        # ── Stage 7: Chunk‑to‑Screenshot Mapping ───────────────────────────
        update_progress_sync(task_id, "mapping", "Mapping screenshots to chunks…", 35)
        mappings_dir = str(lecture_dir / "mappings")
        Path(mappings_dir).mkdir(parents=True, exist_ok=True)
        mapping_path = str(Path(mappings_dir) / "chunk_screenshot_mapping.json")
        create_chunk_screenshot_mapping(chunks_path, keyframes_meta, mapping_path)

        # ── Stage 8: Outline Generation ───────────────────────────────────
        update_progress_sync(task_id, "outline", "Generating lecture outline…", 40)
        chapters_dir = str(lecture_dir / "chapters")
        notes_dir    = str(lecture_dir / "notes")
        Path(chapters_dir).mkdir(parents=True, exist_ok=True)
        Path(notes_dir).mkdir(parents=True, exist_ok=True)
        try:
            outline_result = generate_lecture_outline(objects_dir, out)
            outline_path   = str(Path(notes_dir) / "lecture_outline.json")
            _metrics["num_chapters"] = (outline_result or {}).get("num_chapters")
        except Exception as e:
            logger.error(f"Outline generation failed (continuing): {e}")
            import json as _json
            fallback = {
                "lecture_title": "Untitled Lecture",
                "chapters": [
                    {
                        "chapter_id": 1,
                        "title": "Full Lecture",
                        "start_chunk": 0,
                        "end_chunk": 0,
                        "focus_concepts": [],
                        "chunk_ids": [],
                    }
                ],
            }
            outline_path = str(Path(notes_dir) / "lecture_outline.json")
            Path(outline_path).parent.mkdir(parents=True, exist_ok=True)
            with open(outline_path, "w", encoding="utf-8") as f:
                _json.dump(fallback, f, indent=2)

        # Update lecture title in registry (works for both success and fallback)
        try:
            import json as _json
            with open(outline_path, encoding="utf-8") as f:
                outline_data = _json.load(f)
            real_title = outline_data.get("lecture_title", "Untitled Lecture")
            _metrics["title"] = real_title
            update_lecture_title(task_id, real_title)
        except Exception:
            pass

        # ── Stage 9: Visual Knowledge (Chapter-Aligned) ───────────────────
        update_progress_sync(task_id, "visual_knowledge", "Understanding visuals…", 46)
        visual_objects_dir = str(lecture_dir / "visual_objects")
        try:
            process_visual_chunks(mapping_path, visual_objects_dir, outline_path=outline_path)
        except Exception as e:
            logger.error(f"Visual knowledge failed (continuing): {e}")

        # ── Stage 10: Knowledge Merging ────────────────--------------------
        update_progress_sync(task_id, "knowledge_merging", "Merging knowledge…", 52)
        merged_dir = str(lecture_dir / "merged_objects")
        try:
            merge_all_chunks(objects_dir, visual_objects_dir, merged_dir)
        except Exception as e:
            logger.error(f"Knowledge merging failed (continuing): {e}")

        # ── Stage 11: Chapter Building ─────────────────────────────────────
        update_progress_sync(task_id, "chapter_building", "Building chapters…", 58)
        try:
            build_chapters_pipeline(outline_path, merged_dir, chapters_dir)
        except Exception as e:
            logger.error(f"Chapter building failed (continuing): {e}")

        # ── Stage 12: Screenshot Selection ─────────────────────────────────
        update_progress_sync(task_id, "screenshot_selection", "Selecting screenshots…", 64)
        try:
            select_screenshots_for_lecture(chapters_dir, out)
        except Exception as e:
            logger.error(f"Screenshot selection failed (continuing): {e}")

        # ── Stages 13–16: Consolidated Artifact Generation (Notes, Revision, Assessment, Cards) ─
        update_progress_sync(task_id, "chapter_artifacts", "Generating study notes, revision & assessment…", 75)
        try:
            generate_consolidated_chapter_artifacts(chapters_dir, outline_path, out)
        except Exception as e:
            logger.error(f"Consolidated chapter artifacts generation failed (continuing): {e}")

        # REMOVED: PDFs are now generated on-demand when user clicks download

        # ── Stage 17: Tutor Index ──────────────────────────────────────────
        update_progress_sync(task_id, "tutor_index", "Indexing for tutor…", 96)
        try:
            import chromadb
            from tutor.chunker import chunk_glob
            from tutor.embedding import GeminiEmbeddingFunction
            from tutor.build_index import upsert_batched

            lecture_dir = Path(out)
            notes_glob = str(lecture_dir / "notes" / "chapter_*.md")
            chroma_dir = lecture_dir / "tutor" / "chroma"
            chroma_dir.mkdir(parents=True, exist_ok=True)

            chunks = chunk_glob(notes_glob)
            logger.info(f"  Tutor index: found {len(chunks)} chunks")

            if chunks:
                client = chromadb.PersistentClient(path=str(chroma_dir))
                ef = GeminiEmbeddingFunction(role="document")
                collection = client.get_or_create_collection(
                    name="norai_notes",
                    embedding_function=ef,
                    metadata={"hnsw:space": "cosine"},
                )
                # Content-hashed ids: re-indexing identical notes is a no-op;
                # changed notes are diff-synced (no orphaned docs, no quadratic
                # re-embeds). See ROADMAP P1.2.
                ids = [
                    f"chunk_{hashlib.sha256(c['text'].encode('utf-8')).hexdigest()[:16]}"
                    for c in chunks
                ]
                documents = [c["text"] for c in chunks]
                metadatas = [{
                    "heading": c["heading"],
                    "heading_path": c["heading_path"],
                    "chapter_id": c.get("chapter_id", -1),
                    "source": c["source"],
                } for c in chunks]
                existing = set(collection.get(include=[])["ids"])
                expected = set(ids)
                to_add = expected - existing
                to_remove = existing - expected
                if to_add:
                    idx = [i for i, _id in enumerate(ids) if _id in to_add]
                    upsert_batched(
                        collection,
                        [ids[i] for i in idx],
                        [documents[i] for i in idx],
                        [metadatas[i] for i in idx],
                    )
                if to_remove:
                    collection.delete(ids=list(to_remove))
                logger.info(
                    f"  Tutor index: {collection.count()} docs "
                    f"(added {len(to_add)}, removed {len(to_remove)})"
                )
        except Exception as e:
            logger.error(f"Tutor index failed (continuing): {e}")

        # ── Stage 18: Screenshot Index ─────────────────────────────────────
        update_progress_sync(task_id, "screenshot_index", "Indexing screenshots…", 99)
        try:
            import json as _json, glob as _glob
            import chromadb
            from tutor.embedding import GeminiEmbeddingFunction
            from tutor.build_index import upsert_batched

            lecture_dir = Path(out)
            screenshot_glob = str(lecture_dir / "screenshots" / "selected" / "chapter_*_screenshots.json")
            chroma_dir = lecture_dir / "tutor" / "chroma"

            json_files = sorted(_glob.glob(screenshot_glob))
            logger.info(f"  Screenshot index: found {len(json_files)} files")

            if json_files:
                client = chromadb.PersistentClient(path=str(chroma_dir))
                ef = GeminiEmbeddingFunction(role="document")
                collection = client.get_or_create_collection(
                    name="screenshot_captions",
                    embedding_function=ef,
                    metadata={"hnsw:space": "cosine"},
                )
                ids = []
                documents = []
                metadatas = []
                for json_path in json_files:
                    with open(json_path) as f:
                        data = _json.load(f)
                    chapter_id = data.get("chapter_id")
                    screenshots = data.get("screenshots", [])
                    for shot in screenshots:
                        shot_id = f"ch{chapter_id}_{Path(shot['path']).stem}"
                        reason = shot.get("reason", "")
                        # Reason content-hash makes changed captions re-index
                        # instead of being wrongly skipped.
                        ids.append(f"{shot_id}__{hashlib.sha256(reason.encode('utf-8')).hexdigest()[:8]}")
                        documents.append(reason)
                        metadatas.append({
                            "path": shot["path"],
                            "section": shot.get("section", ""),
                            "importance": shot.get("importance", 0),
                            "chapter_id": chapter_id,
                        })
                existing = set(collection.get(include=[])["ids"])
                expected = set(ids)
                to_add = expected - existing
                to_remove = existing - expected
                if to_add:
                    idx = [i for i, _id in enumerate(ids) if _id in to_add]
                    upsert_batched(
                        collection,
                        [ids[i] for i in idx],
                        [documents[i] for i in idx],
                        [metadatas[i] for i in idx],
                    )
                if to_remove:
                    collection.delete(ids=list(to_remove))
                logger.info(
                    f"  Screenshot index: {collection.count()} screenshots indexed "
                    f"(added {len(to_add)}, removed {len(to_remove)})"
                )
        except Exception as e:
            logger.error(f"Screenshot index failed (continuing): {e}")

        # ── Stage 19: Cleanup Temporary Files ──────────────────────────────
        update_progress_sync(task_id, "cleanup", "Cleaning up temporary files…", 99.5)
        import shutil

        lecture_dir = Path(out)
        if (lecture_dir / "notes").exists() and (lecture_dir / "tutor" / "chroma").exists():
            temp_dirs = [
                "videos", "audio", "screenshots/raw", "chunks",
                "mappings", "metadata"
                # NOTE: "objects", "visual_objects", "merged_objects" are kept —
                # they hold the hash-of-inputs cache markers + outputs that make
                # re-runs cost ~0 API calls (ROADMAP P1.4/P1.3). Deleting them
                # silently wiped the caches every run.
            ]
            for d in temp_dirs:
                target = lecture_dir / d
                if target.exists():
                    try:
                        shutil.rmtree(target)
                    except Exception as e:
                        logger.warning(f"Failed to delete intermediate directory {target}: {e}")
        else:
            logger.warning("Skipping cleanup: Final notes or tutor index missing. Keeping intermediates for debugging.")

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
            )
        except Exception as e:
            logger.warning(f"Failed to record pipeline usage outcome: {e}")
        mark_complete_sync(task_id)

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
                output_dir=out if "out" in locals() else None,
            )
        except Exception as e:
            logger.warning(f"Failed to record pipeline failure outcome: {e}")
        mark_error_sync(task_id, str(exc))