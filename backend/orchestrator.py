"""
backend/orchestrator.py

Complete NorAI pipeline: runs every stage for a single video source,
emitting real‑time progress via SSE queues.
"""

import asyncio
import subprocess
import threading
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from backend.lecture_registry import create_lecture

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
from notes.notes_generator import generate_study_notes
from notes.screenshot_selector import select_screenshots_for_lecture
from revision_notes.revision_generator import generate_revision_notes_for_lecture
from assessment.assessment_generator import generate_assessment_for_lecture
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


    
def update_lecture_title(lecture_id: str, title: str):
    """Update the title of a lecture in lectures.json."""
    import json as _json
    registry_path = Path("outputs/lectures.json")
    if not registry_path.exists():
        return
    with open(registry_path, encoding="utf-8") as f:
        lectures = _json.load(f)
    if lecture_id in lectures:
        lectures[lecture_id]["title"] = title
        with open(registry_path, "w", encoding="utf-8") as f:
            _json.dump(lectures, f, indent=2)

# ── Pipeline runner (SYNCHRONOUS — runs in a background thread) ─────────────

def run_pipeline(
    task_id: str,
    source_type: str,
    url: str | None = None,
    file_path: str | None = None,
):
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

        # ── Stage 2: Transcription ─────────────────────────────────────────
        update_progress_sync(task_id, "transcription", "Transcribing lecture…", 8)
        tr = transcribe_audio(audio_path, meta_path, output_dir=out)
        transcript_json = tr["transcript_json_path"]

        # ── Stage 3: Chunking ──────────────────────────────────────────────
        update_progress_sync(task_id, "chunking", "Chunking transcript…", 14)
        ch = chunk_transcript(transcript_json, output_dir=out)
        chunks_path = ch["chunks_path"]

        # ── Stage 4: Knowledge Extraction ──────────────────────────────────
        update_progress_sync(task_id, "knowledge_extraction", "Extracting knowledge…", 20)
        ke = extract_all_chunks(chunks_path, output_dir=out)
        objects_dir = ke["objects_dir"]

        # ── Stage 5: Frame Extraction ──────────────────────────────────────
        update_progress_sync(task_id, "frame_extraction", "Extracting frames…", 26)
        raw_dir = str(lecture_dir / "screenshots" / "raw")
        fe = extract_frames(video_path, raw_dir)
        frames_meta = fe["metadata_file"]

        # ── Stage 6: Scene Detection ───────────────────────────────────────
        update_progress_sync(task_id, "scene_detection", "Detecting key scenes…", 32)
        keyframes_dir = str(lecture_dir / "screenshots" / "keyframes")
        detect_scenes(frames_meta, keyframes_dir)
        keyframes_meta = str(Path(keyframes_dir) / "metadata.json")

        # ── Stage 7: Chunk‑to‑Screenshot Mapping ───────────────────────────
        update_progress_sync(task_id, "mapping", "Mapping screenshots to chunks…", 35)
        mappings_dir = str(lecture_dir / "mappings")
        Path(mappings_dir).mkdir(parents=True, exist_ok=True)
        mapping_path = str(Path(mappings_dir) / "chunk_screenshot_mapping.json")
        create_chunk_screenshot_mapping(chunks_path, keyframes_meta, mapping_path)

        # ── Stage 8: Visual Knowledge ──────────────────────────────────────
        update_progress_sync(task_id, "visual_knowledge", "Understanding visuals…", 42)
        visual_objects_dir = str(lecture_dir / "visual_objects")
        try:
            process_visual_chunks(mapping_path, visual_objects_dir)
        except Exception as e:
            logger.error(f"Visual knowledge failed (continuing): {e}")

        # ── Stage 9: Knowledge Merging ─────────────────────────────────────
        update_progress_sync(task_id, "knowledge_merging", "Merging knowledge…", 50)
        merged_dir = str(lecture_dir / "merged_objects")
        try:
            merge_all_chunks(objects_dir, visual_objects_dir, merged_dir)
        except Exception as e:
            logger.error(f"Knowledge merging failed (continuing): {e}")

        # ── Stage 10: Outline Generation ───────────────────────────────────
        update_progress_sync(task_id, "outline", "Generating lecture outline…", 54)
        chapters_dir = str(lecture_dir / "chapters")
        notes_dir    = str(lecture_dir / "notes")
        Path(chapters_dir).mkdir(parents=True, exist_ok=True)
        Path(notes_dir).mkdir(parents=True, exist_ok=True)
        try:
            outline_result = generate_lecture_outline(merged_dir, out)
            outline_path   = str(Path(notes_dir) / "lecture_outline.json")
        except Exception as e:
            logger.error(f"Outline generation failed (continuing): {e}")
            # Minimal fallback outline – one chapter that covers all chunks
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
            update_lecture_title(task_id, real_title)
        except Exception:
            pass

        # ── Stage 11: Chapter Building ─────────────────────────────────────
        update_progress_sync(task_id, "chapter_building", "Building chapters…", 58)
        try:
            build_chapters_pipeline(outline_path, merged_dir, chapters_dir)
        except Exception as e:
            logger.error(f"Chapter building failed (continuing): {e}")

        # ── Stage 12: Study Notes ──────────────────────────────────────────
        update_progress_sync(task_id, "study_notes", "Writing study notes…", 64)
        try:
            generate_study_notes(chapters_dir, outline_path, out)
        except Exception as e:
            logger.error(f"Study notes generation failed (continuing): {e}")

        # ── Stage 13: Screenshot Selection ─────────────────────────────────
        update_progress_sync(task_id, "screenshot_selection", "Selecting screenshots…", 70)
        try:
            select_screenshots_for_lecture(chapters_dir, out)
        except Exception as e:
            logger.error(f"Screenshot selection failed (continuing): {e}")

        # ── Stage 14: Revision Notes ───────────────────────────────────────
        update_progress_sync(task_id, "revision_notes", "Writing revision notes…", 76)
        try:
            generate_revision_notes_for_lecture(notes_dir, outline_path, out)
        except Exception as e:
            logger.error(f"Revision notes generation failed (continuing): {e}")

        # ── Stage 15: Assessment ───────────────────────────────────────────
        update_progress_sync(task_id, "assessment", "Creating assessment…", 82)
        try:
            generate_assessment_for_lecture(notes_dir, out)
        except Exception as e:
            logger.error(f"Assessment generation failed (continuing): {e}")

        # ── Stage: Flashcards ─────────────────────────────────────────────
        update_progress_sync(task_id, "flashcards", "Generating flashcards…", 86)
        try:
            import flashcards.generate_flashcards as fg
            from pathlib import Path as _Path
            lecture_dir = _Path(out)
            fg.ASSESSMENT_DIR = lecture_dir / "assessment"
            fg.FLASHCARDS_DIR = lecture_dir / "flashcards"
            fg.FLASHCARDS_DIR.mkdir(parents=True, exist_ok=True)
            fg.main()
        except Exception as e:
            logger.error(f"Flashcards generation failed (continuing): {e}")

        # REMOVED: PDFs are now generated on-demand when user clicks download

        # ── Stage 17: Tutor Index ──────────────────────────────────────────
        update_progress_sync(task_id, "tutor_index", "Indexing for tutor…", 96)
        try:
            import chromadb
            from pathlib import Path as _Path
            from tutor.chunker import chunk_glob
            from tutor.embedding import GeminiEmbeddingFunction

            lecture_dir = _Path(out)
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
                for i, c in enumerate(chunks):
                    collection.upsert(
                        ids=[f"chunk_{i}"],
                        documents=[c["text"]],
                        metadatas=[{
                            "heading": c["heading"],
                            "heading_path": c["heading_path"],
                            "chapter_id": c.get("chapter_id", -1),
                            "source": c["source"],
                        }]
                    )
                logger.info(f"  Tutor index: {collection.count()} documents indexed")
        except Exception as e:
            logger.error(f"Tutor index failed (continuing): {e}")

        # ── Stage 18: Screenshot Index ─────────────────────────────────────
        update_progress_sync(task_id, "screenshot_index", "Indexing screenshots…", 99)
        try:
            import json as _json, glob as _glob
            import chromadb
            from pathlib import Path as _Path
            from tutor.embedding import GeminiEmbeddingFunction

            lecture_dir = _Path(out)
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
                total = 0
                for json_path in json_files:
                    with open(json_path) as f:
                        data = _json.load(f)
                    chapter_id = data.get("chapter_id")
                    screenshots = data.get("screenshots", [])
                    for shot in screenshots:
                        shot_id = f"ch{chapter_id}_{_Path(shot['path']).stem}"
                        collection.upsert(
                            ids=[shot_id],
                            documents=[shot.get("reason", "")],
                            metadatas=[{
                                "path": shot["path"],
                                "section": shot.get("section", ""),
                                "importance": shot.get("importance", 0),
                                "chapter_id": chapter_id,
                            }]
                        )
                        total += 1
                logger.info(f"  Screenshot index: {total} screenshots indexed")
        except Exception as e:
            logger.error(f"Screenshot index failed (continuing): {e}")

        # ── Stage 19: Cleanup Temporary Files ──────────────────────────────
        update_progress_sync(task_id, "cleanup", "Cleaning up temporary files…", 99.5)
        import shutil
        from pathlib import Path

        lecture_dir = Path(out)
        if (lecture_dir / "notes").exists() and (lecture_dir / "tutor" / "chroma").exists():
            temp_dirs = [
                "videos", "audio", "screenshots/raw", "chunks", 
                "objects", "visual_objects", "merged_objects", "mappings",
                "metadata"
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
        mark_complete_sync(task_id)

    except Exception as exc:
        mark_error_sync(task_id, str(exc))