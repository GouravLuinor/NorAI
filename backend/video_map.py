"""
backend/video_map.py — P6.3: per-lecture seek map for click-to-video grounding.

Builds `{chapters: [...], chunks: [...]}` purely from on-disk artifacts, so the
frontend can jump the YouTube player to the exact moment:

  - `notes/lecture_outline.json`  → chapter → chunk_ids
  - `merged_objects/chunk_*.json` → chunk_id → start/end (seconds)

Deterministic, no LLM, read-only. A chapter with no resolvable timestamp gets
`start_sec`/`end_sec = None` and the frontend simply hides its seek chip.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _safe_float(value) -> Optional[float]:
    """Coerce to float, or None for missing/NaN/non-numeric values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def load_outline_chapters(base: Path) -> list[dict]:
    """
    Read `notes/lecture_outline.json` and return the chapter list. Returns []
    when the outline is missing or unreadable.
    """
    base = Path(base)
    outline_path = base / "notes" / "lecture_outline.json"
    if not outline_path.exists():
        return []
    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            outline = json.load(f)
    except Exception as e:
        logger.info("video_map: outline unreadable (%s): %s", outline_path, e)
        return []
    return outline.get("chapters", [])


def load_chunk_times(base: Path) -> dict[int, dict]:
    """
    Read every `merged_objects/chunk_*.json` and map chunk_id → its recorded
    start/end seconds. Chunks without a numeric start/end are skipped.
    """
    base = Path(base)
    times: dict[int, dict] = {}
    merged_dir = base / "merged_objects"
    if not merged_dir.exists():
        return times
    for f in sorted(merged_dir.glob("chunk_*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                obj = json.load(fh)
            chunk_id = obj.get("chunk_id")
            if chunk_id is None:
                continue
            start = _safe_float(obj.get("start"))
            end = _safe_float(obj.get("end"))
            if start is None:
                continue
            times[int(chunk_id)] = {
                "start_sec": start,
                "end_sec": end,
            }
        except Exception as e:
            logger.info("video_map: chunk file skipped (%s): %s", f, e)
    return times


def build_video_map(lecture_dir) -> dict:
    """
    Build the seek map for a lecture directory. `lecture_dir` may be a str or
    Path. Returns:
        {
          "chapters": [
              {"chapter_id": int, "title": str, "chunk_ids": [int],
               "start_sec": float|None, "end_sec": float|None},
              ...
          ],
          "chunks": [{"chunk_id": int, "start_sec": float, "end_sec": float}, ...]
        }
    """
    base = Path(lecture_dir)
    chunk_times = load_chunk_times(base)

    chapters: list[dict] = []
    for ch in load_outline_chapters(base):
        chapter_id = ch.get("chapter_id")
        chunk_ids = [
            int(cid) for cid in (ch.get("chunk_ids") or [])
            if int(cid) in chunk_times
        ]
        starts = [chunk_times[cid]["start_sec"] for cid in chunk_ids]
        ends = [chunk_times[cid]["end_sec"] for cid in chunk_ids if chunk_times[cid]["end_sec"] is not None]
        chapters.append({
            "chapter_id": chapter_id,
            "title": ch.get("title") or f"Chapter {chapter_id}",
            "chunk_ids": chunk_ids,
            "start_sec": min(starts) if starts else None,
            "end_sec": max(ends) if ends else None,
        })

    chunks = [
        {"chunk_id": cid, **times}
        for cid, times in sorted(chunk_times.items())
    ]

    return {"chapters": chapters, "chunks": chunks}
