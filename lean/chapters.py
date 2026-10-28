"""
lean/chapters.py — ONE multimodal call per chapter.

Input: the chapter's timestamped transcript (ground truth) + up to
MAX_FRAMES keyframes from the chapter's time span at MEDIA_RESOLUTION_LOW
(~270 tokens/frame, same OCR quality on slides/diagrams as the default).
Output, in the layout the API/tutor already read:
  notes/chapter_N.{md,json}  (each section carries start_sec for seeking)
  revision/, assessment/, flashcards/  (questions validated one by one —
                                        a bad question is dropped, not fatal)
  screenshots/selected/chapter_N_screenshots.json
  visual_objects/visual_analysis_chN.json  (per-frame OCR for tutor/indexing)

Replaces the legacy visual analysis, screenshot selection and notes calls.
The legacy notes call was fed an LLM paraphrase of the transcript that was
larger than the transcript itself and carried invented `inferred_knowledge`;
here the model writes straight from what the lecturer said.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from assessment.assessment_models import Question
from backend.gemini_client import get_client, invoke_with_policy
from backend.rate_limit_handler import GeminiDailyQuotaExceededException
from backend.usage_ledger import record_generate_usage
from cache_util import outputs_current, write_marker
from config import MODEL_NAME
from lean.structure import fmt_ts
from notes.notes_generator import CoreConceptItem, write_chapter_artifacts, write_degraded_chapter
from transcription.gemini_transcriber import _parse_ts

logger = logging.getLogger(__name__)

PROMPT_VERSION = "chapter-v3"
MAX_FRAMES = 12          # keyframes sent per chapter (evenly sampled in time)
MAX_SELECTED = 4         # screenshots placed in the notes per chapter
MIN_SELECTED_IMPORTANCE = 6
MAX_WORKERS = 3
# Notes length target: about half the chapter's spoken words (the legacy
# pipeline's ratio), within these bounds.
NOTES_WORDS_RATIO = 0.5
NOTES_WORDS_MIN, NOTES_WORDS_MAX = 300, 2200


def notes_word_target(transcript_words: int) -> int:
    target = int(transcript_words * NOTES_WORDS_RATIO) // 50 * 50
    return max(NOTES_WORDS_MIN, min(NOTES_WORDS_MAX, target))


# ── Schema ────────────────────────────────────────────────────────────────────

class LeanSection(BaseModel):
    section_type: Literal["definition", "callout", "table", "list", "code", "prose"]
    title: str
    content_markdown: str = Field(description="Markdown body. Tables, bullets, code and $math$ where natural. No image tags.")
    start: str = Field(description="The [m:ss] transcript timestamp where this section's material begins, e.g. '4:12'.")


class FrameNote(BaseModel):
    frame: int = Field(description="The frame's number as labelled in the input.")
    visual_type: Literal["slide", "diagram", "equation", "code", "animation", "demo", "talking_head", "other"]
    ocr_text: str = Field(description="All legible on-screen text and equations; empty if none.")
    description: str = Field(description="One sentence on what the frame shows.")
    importance: int = Field(description="1-10: how useful this frame is to a student revising the chapter.")
    include_in_notes: bool
    section: str = Field(description="Title of the notes section this frame belongs to.")


class _ChapterBody(BaseModel):
    study_notes_title: str
    study_notes_sections: list[LeanSection]
    revision_summary: list[str]
    core_concepts_breakdown: list[CoreConceptItem]


class LeanChapterOut(_ChapterBody):
    """Response schema. Questions and frames are parsed item by item
    (clean_questions / parse_frames) so one malformed entry can't sink the
    whole chapter."""
    assessment_questions: list[Question]
    frames: list[FrameNote]


# ── Inputs ────────────────────────────────────────────────────────────────────

def chapter_span(chapter: dict, chunks: list[dict], lecture_end: float) -> tuple[float, float]:
    """[start, end) of a chapter: its first chunk's start (0 for chapter 1, so
    title frames before the first word count) to the next chapter's start."""
    by_id = {c["chunk_id"]: c for c in chunks}
    start = 0.0 if chapter["start_chunk"] == 0 else float(by_id[chapter["start_chunk"]]["start"])
    nxt = by_id.get(chapter["end_chunk"] + 1)
    end = float(nxt["start"]) if nxt else max(lecture_end, float(by_id[chapter["end_chunk"]]["end"]))
    return start, end


def chapter_segments(chapter: dict, chunks: list[dict], segments: list[dict]) -> list[dict]:
    wanted = {
        sid for c in chunks
        if chapter["start_chunk"] <= c["chunk_id"] <= chapter["end_chunk"]
        for sid in c.get("segment_ids", [])
    }
    return [s for s in segments if s["segment_id"] in wanted]


def sample_frames(keyframes: list[dict], start: float, end: float, cap: int = MAX_FRAMES,
                  last: bool = False) -> list[dict]:
    """Keyframes inside [start, end) (end inclusive for the last chapter),
    evenly thinned to at most `cap`."""
    inside = [
        k for k in keyframes
        if start <= float(k["timestamp"]) < end or (last and float(k["timestamp"]) == end)
    ]
    inside.sort(key=lambda k: float(k["timestamp"]))
    if len(inside) <= cap:
        return inside
    if cap == 1:
        return [inside[0]]
    picks = sorted({round(i * (len(inside) - 1) / (cap - 1)) for i in range(cap)})
    return [inside[i] for i in picks]


def transcript_lines(segments: list[dict]) -> str:
    return "\n".join(f"[{fmt_ts(s['start'])}] {s['text'].strip()}" for s in segments if s["text"].strip())


# ── Output cleanup ────────────────────────────────────────────────────────────

_OPTION_TYPES = {"MCQ", "True/False"}


def _match_option(answer: str, options: list[str]) -> str | None:
    if answer in options:
        return answer
    low = answer.strip().lower()
    for o in options:
        if o.strip().lower() == low:
            return o
    # "B" / "B)" / "B. text" → option index
    letter = low[:1]
    if letter in "abcdefgh" and (len(low) == 1 or low[1] in ").: "):
        idx = "abcdefgh".index(letter)
        if idx < len(options):
            return options[idx]
    return None


def clean_questions(raw: list, chapter_id: int) -> list[dict]:
    """Validate questions one by one: repair what is mechanically fixable,
    drop the rest, renumber from 1."""
    out: list[dict] = []
    for q in raw if isinstance(raw, list) else []:
        if not isinstance(q, dict):
            continue
        q = {**q, "chapter_id": chapter_id, "question_id": len(out) + 1}
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        answer = str(q.get("answer", "")).strip()
        if q.get("type") == "True/False":
            options = options or ["True", "False"]
            if answer.lower() in ("true", "false"):
                answer = answer.capitalize()
        if q.get("type") in _OPTION_TYPES:
            answer = _match_option(answer, options) or answer
        else:
            options = []
        q["options"], q["answer"] = options, answer
        try:
            out.append(Question.model_validate(q).model_dump())
        except ValidationError as e:
            logger.warning("Chapter %s: dropping invalid question: %s", chapter_id, e.errors()[0].get("msg"))
    return out


def parse_frames(raw: list) -> list[FrameNote]:
    frames = []
    for f in raw if isinstance(raw, list) else []:
        try:
            frames.append(FrameNote.model_validate(f))
        except ValidationError:
            continue
    return frames


def section_start(raw: str, span: tuple[float, float]) -> float | None:
    try:
        sec = _parse_ts(raw.strip().strip("[]"))
    except (ValueError, AttributeError):
        return None
    return round(min(max(sec, span[0]), span[1]), 2)


def select_screenshots(frames: list[FrameNote], sent: list[dict]) -> list[dict]:
    chosen = [
        f for f in frames
        if 1 <= f.frame <= len(sent) and f.include_in_notes
        and f.importance >= MIN_SELECTED_IMPORTANCE and f.visual_type != "talking_head"
    ]
    chosen.sort(key=lambda f: (-f.importance, float(sent[f.frame - 1]["timestamp"])))
    seen, shots = set(), []
    for f in chosen:
        k = sent[f.frame - 1]
        if k["image_path"] in seen:
            continue
        seen.add(k["image_path"])
        shots.append({
            "path": k["image_path"],
            "reason": f.description,
            "section": f.section,
            "importance": f.importance,
            "timestamp": float(k["timestamp"]),
        })
    return shots[:MAX_SELECTED]


# ── The call ──────────────────────────────────────────────────────────────────

_PROMPT = """\
You are writing study materials for chapter {n} of {total} of the lecture "{lecture_title}".
Chapter: "{title}". {summary}
Focus concepts: {concepts}.{neighbours}

You get this chapter's timestamped transcript (what the lecturer said: the ONLY source
of truth) and {k} frames captured from the video during the chapter.

GROUNDING (most important):
- Every statement in the notes, revision points, concepts and quiz must be supported by
  the transcript or be clearly visible in a frame.
- Do NOT add facts, definitions, formulas, complexities, examples, names, numbers or
  history that the lecturer did not give, even if they are true and relevant. If the
  lecturer is informal or vague about something, stay at that level.
- Within that limit be THOROUGH: keep every step of the lecturer's reasoning, every
  example, number, analogy and caveat they give. A student should be able to study
  from the notes instead of rewatching. You may reorganise, clarify wording, and write
  spoken math as LaTeX ($...$ inline, $$...$$ display).

Produce:
1. study_notes_title: the chapter title.
2. study_notes_sections: 3-8 cards covering everything the lecturer teaches here, in
   lecture order, AT LEAST {words} words in total (the transcript has {transcript_words}).
   Spend that length on the lecturer's own specifics (the concrete values they plug in,
   intermediate steps, analogies, asides on why it matters), never on outside material.
   section_type: definition | callout | table | list | code | prose. start: the [m:ss]
   transcript timestamp where that section's material begins. No markdown image tags.
3. revision_summary: 3-5 key takeaways for exam revision.
4. core_concepts_breakdown: the key concepts, each with a 1-2 sentence explanation.
5. assessment_questions: 4-5 questions answerable from this chapter's transcript.
   question_id from 1, chapter_id {n}. MCQ: 4 options and `answer` copied exactly from
   one of them. True/False: options ["True", "False"]. Every other type: options [].
   flashcard_front <= 15 words, flashcard_back <= 20 words, flashcard_explanation <= 30 words.
6. frames: exactly {k} entries, one per frame (frame = 1..{k}), even for frames you would
   not show. include_in_notes = true only for frames showing teaching content (a slide,
   diagram, equation, code or worked example) worth placing in the notes.

TRANSCRIPT:
{transcript}
"""


def _neighbours(outline: dict, idx: int) -> str:
    chs = outline["chapters"]
    parts = []
    if idx > 0:
        parts.append(f'the previous chapter covers "{chs[idx - 1]["title"]}"')
    if idx + 1 < len(chs):
        parts.append(f'the next covers "{chs[idx + 1]["title"]}"')
    return f"\n(For context: {'; '.join(parts)}. Do not repeat their material.)" if parts else ""


def _contents(prompt: str, frames: list[dict]) -> list:
    contents: list = [prompt]
    for i, k in enumerate(frames, 1):
        contents.append(f"Frame {i} (at {fmt_ts(float(k['timestamp']))}):")
        contents.append(types.Part.from_bytes(
            data=Path(k["image_path"]).read_bytes(), mime_type="image/jpeg",
        ))
    return contents


def _outputs(out: Path, n: int) -> list[Path]:
    return [
        out / "notes" / f"chapter_{n}.md",
        out / "notes" / f"chapter_{n}.json",
        out / "revision" / f"revision_chapter_{n}.md",
        out / "assessment" / f"assessment_chapter_{n}.json",
        out / "flashcards" / f"flashcards_chapter_{n}.json",
        out / "screenshots" / "selected" / f"chapter_{n}_screenshots.json",
        out / "visual_objects" / f"visual_analysis_ch{n}.json",
    ]


def process_chapter(outline: dict, idx: int, chunks: list[dict], segments: list[dict],
                    keyframes: list[dict], output_dir: str, lecture_end: float) -> bool:
    """Generate and write one chapter's artifacts. Returns False if degraded."""
    out = Path(output_dir)
    ch = outline["chapters"][idx]
    n, title = ch["chapter_id"], ch["title"]
    span = chapter_span(ch, chunks, lecture_end)
    segs = chapter_segments(ch, chunks, segments)
    frames = [
        k for k in sample_frames(keyframes, *span, last=idx == len(outline["chapters"]) - 1)
        if Path(k["image_path"]).is_file()
    ]
    transcript = transcript_lines(segs)
    transcript_words = sum(len(s["text"].split()) for s in segs)

    marker = out / "notes" / f".lean_ch{n}.sha256"
    cache_key = (PROMPT_VERSION, ch, transcript, [k["image_path"] for k in frames],
                 outline.get("lecture_title", ""), _neighbours(outline, idx))
    if outputs_current(marker, _outputs(out, n), *cache_key):
        logger.info("Lean chapter %s: up to date, skipping", n)
        return True

    prompt = _PROMPT.format(
        n=n, total=len(outline["chapters"]), lecture_title=outline.get("lecture_title", ""),
        title=title, summary=ch.get("summary", ""),
        concepts=", ".join(ch.get("focus_concepts") or []) or "—",
        neighbours=_neighbours(outline, idx), k=len(frames), transcript=transcript,
        words=notes_word_target(transcript_words), transcript_words=transcript_words,
    )

    def _call():
        resp = get_client().models.generate_content(
            model=MODEL_NAME,
            contents=_contents(prompt, frames),
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=16384,
                response_mime_type="application/json",
                response_schema=LeanChapterOut,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            ),
        )
        record_generate_usage("notes", MODEL_NAME, resp)
        if not resp or not resp.text:
            raise ValueError("Chapter call returned an empty or blocked response")
        return resp

    try:
        data = json.loads(invoke_with_policy(_call, node=f"Lean chapter {n}").text)
        body = _ChapterBody.model_validate(data)
    except GeminiDailyQuotaExceededException:
        raise  # fail the run (not metered) instead of shipping placeholders
    except Exception as e:  # noqa: BLE001 — degrade this chapter, keep the lecture
        logger.error("Lean chapter %s failed, writing degraded placeholders: %s", n, e)
        write_degraded_chapter(output_dir, n, title)
        return False

    frame_notes = parse_frames(data.get("frames", []))
    sections = [
        {
            "section_type": s.section_type,
            "title": s.title,
            "content_markdown": s.content_markdown,
            "start_sec": section_start(s.start, span),
        }
        for s in body.study_notes_sections
    ]
    write_chapter_artifacts(
        output_dir,
        chapter_id=n,
        chapter_title=title,
        notes_title=body.study_notes_title or title,
        sections=sections,
        revision_summary=body.revision_summary,
        core_concepts_breakdown=body.core_concepts_breakdown,
        questions=clean_questions(data.get("assessment_questions", []), n),
    )

    shots_dir = out / "screenshots" / "selected"
    shots_dir.mkdir(parents=True, exist_ok=True)
    (shots_dir / f"chapter_{n}_screenshots.json").write_text(json.dumps(
        {"chapter_id": n, "screenshots": select_screenshots(frame_notes, frames)},
        indent=2, ensure_ascii=False,
    ), encoding="utf-8")

    vis_dir = out / "visual_objects"
    vis_dir.mkdir(parents=True, exist_ok=True)
    (vis_dir / f"visual_analysis_ch{n}.json").write_text(json.dumps({
        "chapter_id": n,
        "frames": {
            frames[f.frame - 1]["image_path"]: {
                "ocr_text": f.ocr_text,
                "importance_score": f.importance,
                "visual_type": f.visual_type,
                "include_in_notes": f.include_in_notes,
                "description": f.description,
            }
            for f in frame_notes if 1 <= f.frame <= len(frames)
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    write_marker(marker, *cache_key)
    logger.info(
        "Lean chapter %s: %d sections (%d words, target %d), %d/%d frames described, %d questions",
        n, len(sections), sum(len(s["content_markdown"].split()) for s in sections),
        notes_word_target(transcript_words), len(frame_notes), len(frames),
        len(json.loads((out / "assessment" / f"assessment_chapter_{n}.json").read_text())["questions"]),
    )
    return True


def generate_chapters(outline: dict, chunks_path: str, transcript_path: str,
                      keyframes_meta: str | None, output_dir: str) -> dict:
    """Run every chapter call (MAX_WORKERS in parallel)."""
    chunks = json.loads(Path(chunks_path).read_text(encoding="utf-8"))["chunks"]
    segments = json.loads(Path(transcript_path).read_text(encoding="utf-8"))["segments"]
    keyframes = []
    if keyframes_meta and Path(keyframes_meta).is_file():
        keyframes = json.loads(Path(keyframes_meta).read_text(encoding="utf-8"))
    lecture_end = max([float(s["end"]) for s in segments] + [float(chunks[-1]["end"])])

    degraded = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [
            pool.submit(process_chapter, outline, i, chunks, segments, keyframes, output_dir, lecture_end)
            for i in range(len(outline["chapters"]))
        ]
        for fut in as_completed(futures):
            if not fut.result():
                degraded += 1
    return {"num_chapters": len(outline["chapters"]), "degraded": degraded}
