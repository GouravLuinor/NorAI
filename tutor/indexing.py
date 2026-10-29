"""
indexing.py — build a lecture's tutor index (tutor/index/, see vector_store.py).

Three doc kinds, one embedding pass:
  notes       — study-note sections (chunker.py), as before;
  transcript  — overlapping ~45 s windows of the timestamped transcript. These
                are what the lecturer actually said: the notes are an LLM
                summary that drops details (names, numbers, asides) and adds
                inferred material, so a tutor grounded only in notes says "the
                lecture doesn't mention X" about things the lecturer said;
  screenshot  — selected screenshots, embedded by caption + OCR text.

Ids are content hashes, so re-indexing unchanged content embeds nothing.

CLI (backfill / rebuild an existing lecture):
    venv/bin/python -m tutor.indexing outputs/<lecture-id> [...]
"""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import sys
from pathlib import Path

from tutor.vector_store import VectorStore, index_dir

logger = logging.getLogger(__name__)

WINDOW_MIN_WORDS = 90
WINDOW_MAX_SECONDS = 45.0


def _h(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def fmt_ts(sec: float) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── transcript windows ────────────────────────────────────────────────────────

def load_segments(lecture_dir: Path) -> list[dict]:
    files = sorted((lecture_dir / "transcripts").glob("*.json"))
    if not files:
        return []
    data = json.loads(files[0].read_text(encoding="utf-8"))
    return [s for s in data.get("segments", []) if str(s.get("text", "")).strip()]


def chapter_ranges(lecture_dir: Path) -> list[tuple[int, float, float]]:
    from backend.video_map import build_video_map

    out = []
    for ch in build_video_map(lecture_dir)["chapters"]:
        if ch.get("start_sec") is not None and ch.get("end_sec") is not None:
            out.append((int(ch["chapter_id"]), float(ch["start_sec"]), float(ch["end_sec"])))
    return out


def _chapter_at(t: float, ranges: list[tuple[int, float, float]]) -> int:
    for cid, start, end in ranges:
        if start <= t <= end:
            return cid
    if not ranges:
        return -1
    # Gaps between chunk ranges: nearest chapter by start time.
    return min(ranges, key=lambda r: abs(r[1] - t))[0]


def transcript_windows(segments: list[dict], ranges: list[tuple[int, float, float]]) -> list[dict]:
    """Group segments into windows of >= WINDOW_MIN_WORDS words or
    WINDOW_MAX_SECONDS, each overlapping the previous by one segment so an
    answer that straddles a boundary is still retrievable in one piece."""
    windows: list[dict] = []
    i = 0
    while i < len(segments):
        j, words = i, 0
        while j < len(segments):
            words += len(str(segments[j]["text"]).split())
            j += 1
            span = float(segments[j - 1]["end"]) - float(segments[i]["start"])
            if words >= WINDOW_MIN_WORDS or span >= WINDOW_MAX_SECONDS:
                break
        group = segments[i:j]
        start, end = float(group[0]["start"]), float(group[-1]["end"])
        windows.append({
            "text": " ".join(str(s["text"]).strip() for s in group),
            "start": start,
            "end": end,
            "chapter_id": _chapter_at((start + end) / 2, ranges),
        })
        if j >= len(segments):
            break
        i = j - 1 if j - 1 > i else j
    return windows


# ── build ─────────────────────────────────────────────────────────────────────

def _section_starts(lecture_dir: Path) -> dict[tuple[int, str], float]:
    """(chapter_id, section title) → start second, from the lean pipeline's
    notes/chapter_N.json. Legacy notes have no start_sec and give {}."""
    starts: dict[tuple[int, str], float] = {}
    for f in glob.glob(str(lecture_dir / "notes" / "chapter_*.json")):
        try:
            data = json.loads(Path(f).read_text(encoding="utf-8"))
            for s in data.get("sections", []):
                if s.get("start_sec") is not None and s.get("title"):
                    starts[(int(data["chapter_id"]), s["title"].strip())] = float(s["start_sec"])
        except Exception:  # noqa: BLE001
            continue
    return starts


def _note_docs(lecture_dir: Path):
    from tutor.chunker import chunk_glob

    chunks = chunk_glob(str(lecture_dir / "notes" / "chapter_*.md"))
    starts = _section_starts(lecture_dir)
    ids = [f"note_{_h(c['text'])}" for c in chunks]
    docs = [c["text"] for c in chunks]
    metas = []
    for c in chunks:
        chapter_id = c.get("chapter_id") if c.get("chapter_id") is not None else -1
        meta = {
            "heading": c["heading"],
            "heading_path": c["heading_path"],
            "chapter_id": chapter_id,
            "source": c["source"],
        }
        start = starts.get((chapter_id, str(c["heading"]).strip()))
        if start is not None:
            meta["start"] = start
        metas.append(meta)
    return ids, docs, metas


def _transcript_docs(lecture_dir: Path):
    wins = transcript_windows(load_segments(lecture_dir), chapter_ranges(lecture_dir))
    ids = [f"tx_{int(w['start'])}_{_h(w['text'], 10)}" for w in wins]
    docs = [w["text"] for w in wins]
    metas = [{
        "heading": f"Transcript {fmt_ts(w['start'])}",
        "heading_path": f"Transcript {fmt_ts(w['start'])}–{fmt_ts(w['end'])}",
        "chapter_id": w["chapter_id"],
        "start": round(w["start"], 2),
        "end": round(w["end"], 2),
    } for w in wins]
    return ids, docs, metas


def _frame_ocr(lecture_dir: Path) -> dict[str, str]:
    ocr: dict[str, str] = {}
    for f in glob.glob(str(lecture_dir / "visual_objects" / "visual_analysis_ch*.json")):
        try:
            for path, info in json.loads(Path(f).read_text(encoding="utf-8")).get("frames", {}).items():
                if info.get("ocr_text"):
                    ocr[Path(path).name] = info["ocr_text"]
        except Exception:  # noqa: BLE001
            continue
    return ocr


def _screenshot_docs(lecture_dir: Path):
    ocr = _frame_ocr(lecture_dir)
    ids, docs, metas = [], [], []
    for f in sorted(glob.glob(str(lecture_dir / "screenshots" / "selected" / "chapter_*_screenshots.json"))):
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        chapter_id = data.get("chapter_id")
        for shot in data.get("screenshots", []):
            caption = shot.get("reason", "")
            text = caption
            if ocr.get(Path(shot["path"]).name):
                text += f"\nOn-screen text: {ocr[Path(shot['path']).name]}"
            ids.append(f"shot_ch{chapter_id}_{Path(shot['path']).stem}_{_h(text, 8)}")
            docs.append(text)
            metas.append({
                "path": shot["path"],
                "section": shot.get("section", ""),
                "importance": shot.get("importance", 0),
                "chapter_id": chapter_id if chapter_id is not None else -1,
            })
    return ids, docs, metas


def build_lecture_index(lecture_dir: str | Path, embed=None) -> dict:
    """Sync the lecture's index with its current notes, transcript and
    screenshots. Returns per-kind (added, removed) counts."""
    lecture_dir = Path(lecture_dir)
    if embed is None:
        from tutor.embedding import GeminiEmbeddingFunction
        embed = GeminiEmbeddingFunction(role="document")

    store = VectorStore.open(index_dir(lecture_dir))
    report = {}
    for kind, build in (("notes", _note_docs), ("transcript", _transcript_docs),
                        ("screenshot", _screenshot_docs)):
        try:
            ids, docs, metas = build(lecture_dir)
        except Exception as e:  # noqa: BLE001
            logger.error("index: building %s docs failed: %s", kind, e)
            continue
        report[kind] = store.sync(kind, ids, docs, metas, embed)
        store.save()  # keep paid-for embeddings even if a later kind fails
    logger.info("Tutor index %s: %d docs %s", lecture_dir.name, len(store), report)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for d in sys.argv[1:]:
        print(d, build_lecture_index(d))
