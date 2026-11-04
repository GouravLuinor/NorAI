"""
documents/adapter.py — turn extracted document text into transcript JSON.

The content stages (lean/) work on timestamped segments. A document has no
time, so each segment gets a synthetic one from its word offset at
WORDS_PER_MINUTE, plus a `loc` label ("p. 4", "Slide 7", a heading) that the
prompts, notes and tutor citations show instead of the time. Words ÷ 150 is
also the quota unit: a 6,000-word PDF counts as a 40-minute lecture.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from documents.kind import DOCUMENT

WORDS_PER_MINUTE = 150
SEGMENT_WORDS = 40          # target words per segment
SEGMENT_MAX_WORDS = 60      # a single sentence longer than this is split


@dataclass
class Block:
    """One run of text at one location (a page, a slide, a section)."""
    text: str
    loc: str


_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+")


def _pieces(text: str) -> list[str]:
    """Split a block into ~SEGMENT_WORDS-word pieces on sentence boundaries."""
    words_total = len(text.split())
    if words_total <= SEGMENT_MAX_WORDS:
        return [text] if words_total else []
    out: list[str] = []
    cur: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        words = sentence.split()
        while len(words) > SEGMENT_MAX_WORDS:  # run-on text (tables, lists without stops)
            if cur:
                out.append(" ".join(cur))
                cur = []
            out.append(" ".join(words[:SEGMENT_WORDS]))
            words = words[SEGMENT_WORDS:]
        if cur and len(cur) + len(words) > SEGMENT_WORDS:
            out.append(" ".join(cur))
            cur = []
        cur.extend(words)
    if cur:
        out.append(" ".join(cur))
    return out


def blocks_to_segments(blocks: list[Block]) -> list[dict]:
    segments: list[dict] = []
    offset = 0  # words so far
    for block in blocks:
        for piece in _pieces(" ".join(block.text.split())):
            n = len(piece.split())
            start = offset * 60.0 / WORDS_PER_MINUTE
            offset += n
            end = offset * 60.0 / WORDS_PER_MINUTE
            segments.append({
                "segment_id": len(segments),
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "text": piece,
                "loc": block.loc,
            })
    return segments


def word_count(blocks: list[Block]) -> int:
    return sum(len(b.text.split()) for b in blocks)


def quota_minutes(words: int) -> int:
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def write_document_transcript(blocks: list[Block], output_dir: str | Path, *, title: str,
                              doc_type: str, source_type: str, source_url: str | None = None,
                              pages: int | None = None) -> dict:
    """Write `transcripts/document.{json,txt}`. Returns {"transcript_path",
    "duration_sec", "words", "title"}."""
    segments = blocks_to_segments(blocks)
    if not segments:
        raise ValueError("No readable text found in this document.")
    duration = segments[-1]["end"]
    words = sum(len(s["text"].split()) for s in segments)
    source = {
        "title": title,
        "source_type": source_type,
        "source_kind": DOCUMENT,
        "doc_type": doc_type,
        "duration": duration,
        "words": words,
        "pages": pages,
        "source_url": source_url,
    }
    tdir = Path(output_dir) / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    path = tdir / "document.json"
    path.write_text(json.dumps({
        "source": source,
        "transcription": {"language": None, "method": f"extract:{doc_type}"},
        "segments": segments,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    (tdir / "document.txt").write_text(
        "\n".join(f"[{s['loc']}] {s['text']}" for s in segments), encoding="utf-8",
    )
    return {"transcript_path": str(path), "duration_sec": duration, "words": words, "title": title}
