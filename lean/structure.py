"""
lean/structure.py — ONE call that turns the chunked transcript into the
lecture outline.

Replaces the legacy per-chunk knowledge extraction (1 call per chunk), the
outline call, the knowledge merge and the chapter build. The model sees the
whole transcript tagged by chunk (`[chunk 3 | 4:12]`) and returns the lecture
title plus contiguous chapter ranges over those chunks; everything else in the
outline is derived locally.

Writes `notes/lecture_outline.json`:
    {"lecture_title", "chapters": [{chapter_id, title, focus_concepts, summary,
     chunk_ids, start_chunk, end_chunk}], "chunks": [{chunk_id, start, end}]}
The top-level `chunks` list is what backend/video_map reads for seek times
(the legacy pipeline used merged_objects/ for that).
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from google.genai import types
from pydantic import BaseModel, Field

from backend.gemini_client import generate_nonempty, get_client
from backend.usage_ledger import record_generate_usage
from cache_util import outputs_current, write_marker
from config import MODEL_NAME
from documents.kind import VIDEO, terms

logger = logging.getLogger(__name__)

# Bump when the prompt or schema changes so cached outlines are rebuilt.
PROMPT_VERSION = "structure-v2"


class ChapterPlan(BaseModel):
    title: str = Field(description="Specific chapter title naming what this part covers.")
    start_chunk: int
    end_chunk: int
    focus_concepts: list[str] = Field(description="3-6 concepts actually discussed in this chapter.")
    summary: str = Field(description="1-2 sentences on what this chapter covers.")


class LecturePlan(BaseModel):
    lecture_title: str
    chapters: list[ChapterPlan]


def fmt_ts(sec: float) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chapter_count_range(duration_min: float, num_chunks: int) -> tuple[int, int, int]:
    """(min, target, max) chapters: about one per 4 minutes (the legacy
    pipeline's 3 / 4 / 7 for 9 / 16 / 71 min), capped at 10 and never more
    chapters than chunks."""
    lo = 1 if duration_min < 6 else max(2, math.ceil(duration_min / 12))
    hi = max(lo, min(10, math.ceil(duration_min / 4)))
    target = min(max(round(duration_min / 4), lo), hi)
    return tuple(min(x, num_chunks) for x in (lo, target, hi))


def tagged_transcript(chunks: list[dict]) -> str:
    """Chunks tagged with their start: a time for videos, the location label
    ("p. 4", "Slide 7") for documents."""
    return "\n\n".join(
        f"[chunk {c['chunk_id']} | {c.get('loc') or fmt_ts(c['start'])}]\n" + " ".join(c["text"].split())
        for c in chunks
    )


def repair_plan(plan: LecturePlan, num_chunks: int) -> list[ChapterPlan]:
    """Make the chapter ranges contiguous, ordered and covering every chunk.

    The model's boundaries are kept where they are consistent; overlaps and
    gaps are resolved by moving each chapter's start to the previous end + 1.
    """
    if num_chunks <= 0:
        return []
    chapters = sorted(
        (c for c in plan.chapters if c.title.strip()),
        key=lambda c: (c.start_chunk, c.end_chunk),
    )
    fixed: list[ChapterPlan] = []
    next_start = 0
    for c in chapters:
        start = next_start
        end = min(max(c.end_chunk, start), num_chunks - 1)
        if start > num_chunks - 1:
            break
        fixed.append(c.model_copy(update={"start_chunk": start, "end_chunk": end}))
        next_start = end + 1
    if not fixed:
        return [ChapterPlan(
            title=plan.lecture_title or "Full Lecture",
            start_chunk=0, end_chunk=num_chunks - 1, focus_concepts=[], summary="",
        )]
    if fixed[-1].end_chunk < num_chunks - 1:
        fixed[-1] = fixed[-1].model_copy(update={"end_chunk": num_chunks - 1})
    return fixed


def build_outline(lecture_title: str, chapters: list[ChapterPlan], chunks: list[dict]) -> dict:
    return {
        "lecture_title": lecture_title.strip() or "Untitled Lecture",
        "chapters": [
            {
                "chapter_id": i,
                "title": c.title.strip(),
                "focus_concepts": c.focus_concepts,
                "summary": c.summary,
                "chunk_ids": list(range(c.start_chunk, c.end_chunk + 1)),
                "start_chunk": c.start_chunk,
                "end_chunk": c.end_chunk,
            }
            for i, c in enumerate(chapters, 1)
        ],
        "chunks": [
            {"chunk_id": c["chunk_id"], "start": c["start"], "end": c["end"]}
            for c in chunks
        ],
    }


_PROMPT = """\
Below is the full {text} of a {source}{title_hint}, split into numbered chunks
(chunk {last} is the last). Divide the {source} into about {target} chapters (anything
from {lo} to {hi} is fine) that follow how {author} actually moves between topics.

Rules:
- Each chapter is a contiguous range of chunks (start_chunk..end_chunk, inclusive).
  Chapters are in order, do not overlap, and together cover chunk 0 to chunk {last}.
- Titles, focus_concepts and summaries describe ONLY what {author} {says} in that
  range. Do not add topics {author} does not discuss.
- lecture_title: a clear, specific title for the whole {source}.

{TEXT}:
{transcript}
"""


def generate_outline(chunks_path: str, output_dir: str, *, source_title: str = "",
                     duration_sec: float | None = None, source_kind: str = VIDEO) -> dict:
    """Run the structure call (cached on inputs) and write the outline."""
    chunks = json.loads(Path(chunks_path).read_text(encoding="utf-8"))["chunks"]
    if not chunks:
        raise ValueError("No transcript chunks to structure")
    notes_dir = Path(output_dir) / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    outline_path = notes_dir / "lecture_outline.json"
    marker = notes_dir / ".lean_outline.sha256"

    # Document chunks are tagged with their location labels, so the cache key
    # already differs from any video's.
    transcript = tagged_transcript(chunks)
    if outputs_current(marker, [outline_path], PROMPT_VERSION, transcript, source_title):
        logger.info("Lean outline: up to date, skipping")
        return json.loads(outline_path.read_text(encoding="utf-8"))

    duration_min = (duration_sec or chunks[-1]["end"]) / 60.0
    lo, target, hi = chapter_count_range(duration_min, len(chunks))
    t = terms(source_kind)
    prompt = _PROMPT.format(
        text=t["text"] if source_kind == VIDEO else "text", source=t["source"], author=t["author"],
        says=t["says"], TEXT=t["TEXT"],
        title_hint=f' (published as "{source_title}")' if source_title else "",
        last=len(chunks) - 1, lo=lo, target=target, hi=hi, transcript=transcript,
    )

    def _call():
        resp = get_client().models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=LecturePlan,
            ),
        )
        record_generate_usage("outline", MODEL_NAME, resp)
        return resp

    try:
        plan = LecturePlan.model_validate_json(generate_nonempty(_call, node="Lean structure").text)
        fallback = False
    except ValueError as e:
        # Unparseable plan: one chapter over the whole lecture still yields
        # a usable workspace (the chapter call does the real work).
        logger.error("Lean structure call failed, using a single chapter: %s", e)
        plan = LecturePlan(lecture_title=source_title or "Untitled Lecture", chapters=[])
        fallback = True

    outline = build_outline(plan.lecture_title or source_title, repair_plan(plan, len(chunks)), chunks)
    outline_path.write_text(json.dumps(outline, indent=2, ensure_ascii=False), encoding="utf-8")
    if not fallback:  # a fallback plan is re-asked on the next run
        write_marker(marker, PROMPT_VERSION, transcript, source_title)
    logger.info("Lean outline: %d chapters over %d chunks", len(outline["chapters"]), len(chunks))
    return outline
