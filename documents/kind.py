"""
documents/kind.py — a lecture's source kind ("video" or "document") and the
wording each kind uses in prompts.

The kind is stored in the transcript JSON's `source.source_kind` (written by
documents/adapter.py). Transcripts without it are videos, which covers every
lecture made before documents existed.
"""

from __future__ import annotations

import json
from pathlib import Path

VIDEO = "video"
DOCUMENT = "document"

# Prompt wording per kind. Keys are used as str.format fields, so a prompt
# says "{source}" / "{author}" / "{text}" and reads naturally for both.
TERMS: dict[str, dict[str, str]] = {
    VIDEO: {
        "source": "lecture",
        "Source": "Lecture",
        "text": "transcript",
        "TEXT": "TRANSCRIPT",
        "author": "the lecturer",
        "Author": "The lecturer",
        "authors": "the lecturer's",
        "said": "said",
        "says": "says",
        "loc": "timestamp",
        "loc_example": "3:42",
        "loc_example2": "4:12",
        "excerpt": "transcript excerpt",
    },
    DOCUMENT: {
        "source": "document",
        "Source": "Document",
        "text": "document text",
        "TEXT": "DOCUMENT TEXT",
        "author": "the author",
        "Author": "The author",
        "authors": "the author's",
        "said": "wrote",
        "says": "writes",
        "loc": "location tag",
        "loc_example": "p. 4",
        "loc_example2": "p. 7",
        "excerpt": "document excerpt",
    },
}


def terms(kind: str | None) -> dict[str, str]:
    return TERMS.get(kind or VIDEO, TERMS[VIDEO])


_KIND_CACHE: dict[str, str] = {}


def transcript_source(lecture_dir: str | Path) -> dict:
    files = sorted((Path(lecture_dir) / "transcripts").glob("*.json"))
    if not files:
        return {}
    try:
        return json.loads(files[0].read_text(encoding="utf-8")).get("source") or {}
    except (OSError, ValueError):
        return {}


def lecture_source_kind(lecture_dir: str | Path | None) -> str:
    """"document" or "video" for a lecture dir. Only a found transcript is
    cached, so asking before the transcript exists doesn't pin "video"."""
    if not lecture_dir:
        return VIDEO
    key = str(Path(lecture_dir).resolve())
    if key in _KIND_CACHE:
        return _KIND_CACHE[key]
    source = transcript_source(lecture_dir)
    if not source:
        return VIDEO
    kind = DOCUMENT if source.get("source_kind") == DOCUMENT else VIDEO
    _KIND_CACHE[key] = kind
    return kind
