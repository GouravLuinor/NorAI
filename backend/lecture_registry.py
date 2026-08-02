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
        if not REGISTRY_PATH.exists():
            return {}
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)


def _save(data: dict):
    with _registry_lock:
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

    data = _load()
    if lecture_id not in data:
        data[lecture_id] = {
            "lecture_id": lecture_id,
            "title": title,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "output_dir": str(lecture_dir),
        }
        _save(data)

    return lecture_dir


def get_lecture(lecture_id: str) -> Optional[dict]:
    return _load().get(lecture_id)


def list_lectures() -> list[dict]:
    lectures = list(_load().values())
    for lec in lectures:
        outline_path = Path(lec.get("output_dir", "")) / "notes" / "lecture_outline.json"
        if outline_path.exists():
            try:
                with open(outline_path, encoding="utf-8") as f:
                    lec["chapter_count"] = len(json.load(f).get("chapters", []))
            except Exception:
                lec["chapter_count"] = 0
        else:
            lec["chapter_count"] = 0
            
    return sorted(lectures, key=lambda x: x.get("created_at", ""), reverse=True)