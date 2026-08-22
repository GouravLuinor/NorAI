"""
backend/lecture_registry.py

Simple file‑based registry mapping lecture_id → metadata.
Each lecture lives under outputs/{lecture_id}/.
"""

import json
import time
from pathlib import Path
from typing import Optional

import threading

REGISTRY_PATH = Path("outputs/lectures.json")
_registry_lock = threading.Lock()


def _load() -> dict:
    with _registry_lock:
        return _load_unlocked()


def _load_unlocked() -> dict:
    if not REGISTRY_PATH.exists():
        return {}
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with _registry_lock:
        _save_unlocked(data)


def _save_unlocked(data: dict):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_lecture(lecture_id: str, title: str = "Untitled Lecture") -> Path:
    """Create the lecture directory and register it. Returns the output dir."""
    lecture_dir = Path("outputs") / lecture_id
    lecture_dir.mkdir(parents=True, exist_ok=True)
    # ensure sub‑directories
    for sub in ("notes", "revision", "assessment", "screenshots/keyframes",
                "screenshots/selected", "flashcards", "pdfs", "tutor"):
        (lecture_dir / sub).mkdir(parents=True, exist_ok=True)

    # P2.3: read-modify-write must be atomic — separate locked load/save calls
    # let concurrent creates overwrite each other's entries.
    with _registry_lock:
        data = _load_unlocked()
        if lecture_id not in data:
            data[lecture_id] = {
                "lecture_id": lecture_id,
                "title": title,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "output_dir": str(lecture_dir),
            }
            _save_unlocked(data)

    return lecture_dir


def update_lecture_title(lecture_id: str, title: str):
    """Update lecture title in registry thread-safely (atomic RMW)."""
    if not title or title.strip() in ("", "Untitled Lecture"):
        return
    with _registry_lock:
        data = _load_unlocked()
        if lecture_id in data:
            data[lecture_id]["title"] = title.strip()
            _save_unlocked(data)


def get_lecture(lecture_id: str) -> Optional[dict]:
    return _load().get(lecture_id)


def list_lectures() -> list[dict]:
    # P2.3: one consistent snapshot; expensive per-lecture artifact scans run
    # OUTSIDE the lock; discovered titles are merged back under the lock so a
    # concurrent create/update is never clobbered.
    with _registry_lock:
        data = _load_unlocked()

    lectures = list(data.values())
    title_updates: dict[str, str] = {}

    for lec in lectures:
        output_dir = Path(lec.get("output_dir", ""))
        outline_path = output_dir / "notes" / "lecture_outline.json"
        real_title = None

        if outline_path.exists():
            try:
                with open(outline_path, encoding="utf-8") as f:
                    outline_data = json.load(f)
                    chapters = outline_data.get("chapters", [])
                    lec["chapter_count"] = len(chapters)
                    real_title = outline_data.get("lecture_title") or outline_data.get("title")
                    if not real_title and chapters and isinstance(chapters[0], dict) and chapters[0].get("title"):
                        real_title = chapters[0]["title"]
            except Exception:
                lec["chapter_count"] = 0
        else:
            lec["chapter_count"] = 0

        # Fallback to chapter_1.md header if title is missing/untitled
        if not real_title or real_title.strip() in ("Untitled Lecture", "New Lecture", ""):
            ch1_path = output_dir / "notes" / "chapter_1.md"
            if ch1_path.exists():
                try:
                    with open(ch1_path, encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line.startswith("#"):
                            real_title = first_line.lstrip("#").strip()
                except Exception:
                    pass

        if real_title and real_title.strip() and lec.get("title") in ("Untitled Lecture", "New Lecture", "", None):
            clean_t = real_title.strip()
            lec["title"] = clean_t
            if lec.get("lecture_id") in data:
                title_updates[lec["lecture_id"]] = clean_t

    if title_updates:
        with _registry_lock:
            fresh = _load_unlocked()
            for lid, clean_t in title_updates.items():
                if lid in fresh:
                    fresh[lid]["title"] = clean_t
            _save_unlocked(fresh)

    return sorted(lectures, key=lambda x: x.get("created_at", ""), reverse=True)