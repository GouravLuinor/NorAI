import json
import logging
from pathlib import Path
import os

from google import genai
from dotenv import load_dotenv
from notes.outline_prompts import OUTLINE_PROMPT


load_dotenv()

from backend.ratelimit import rate_limiter as _limiter
from backend.usage_ledger import record_generate_usage
from cache_util import outputs_current, write_marker

logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


from config import MODEL_NAME


def load_llm():
    """
    Load Gemini model.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found."
        )

    client = genai.Client(
        api_key=api_key
    )

    return client



# client = load_llm()


client = load_llm()



def load_chapters(
    chapter_dir
):
    """
    Load all chapter objects.
    """

    chapter_dir = Path(
        chapter_dir
    )

    chapters = []

    for file_path in sorted(
        chapter_dir.glob(
            "chapter_*.json"
        )
    ):

        if (
            file_path.stem
            == "chapter_groups"
        ):
            continue

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            chapter = json.load(
                f
            )

        chapters.append(
            chapter
        )

    chapters.sort(
        key=lambda x:
        x["chapter_id"]
    )

    logger.info(
        f"Loaded "
        f"{len(chapters)} chapters."
    )

    return chapters


def build_outline_payload(
    chapters
):
    payload = []
    for chapter in chapters:
        cid = chapter.get("chapter_id", chapter.get("chunk_id", 0))
        topics = chapter.get("topics", [])
        concepts = chapter.get("concepts", [])
        notes = chapter.get("lecture_notes", [])
        summary = " ".join(notes) if isinstance(notes, list) else str(notes)
        visual_notes = chapter.get("visual_notes", [])
        important_info = chapter.get("important_information", [])

        item = {
            "chunk_id": cid,
            "topics": topics,
            "concepts": concepts,
            "summary": summary,
        }
        if visual_notes:
            item["visual_notes"] = visual_notes
        if important_info:
            item["important_information"] = important_info

        payload.append(item)
    return payload


def build_prompt(
    chapters
):
    payload = (
        build_outline_payload(
            chapters
        )
    )

    return (
        OUTLINE_PROMPT
        + "\n\n"
        + json.dumps(
            payload,
            indent=4,
            ensure_ascii=False
        )
    )


from google.genai import types
from notes.notes_models import LectureOutlineModel

def generate_outline(
    chapters
):
    prompt = build_prompt(
        chapters
    )

    _limiter.wait()

    response = (
        client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=LectureOutlineModel,
                max_output_tokens=4096,
            )
        )
    )
    record_generate_usage("outline", MODEL_NAME, response)

    return (
        response.text
    )



def parse_outline(
    response_text
):

    response_text = (

        response_text

        .replace(
            "```json",
            ""
        )

        .replace(
            "```",
            ""
        )

        .strip()
    )

    return json.loads(
        response_text
    )


def save_outline(
    outline,
    output_path
):

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            outline,
            f,
            indent=4,
            ensure_ascii=False
        )


def main():

    chapters = (
        load_chapters(
            "outputs/chapters"
        )
    )

    outline_text = (
        generate_outline(
            chapters
        )
    )

    outline = (
        parse_outline(
            outline_text
        )
    )

    save_outline(
        outline,
        "outputs/notes/lecture_outline.json"
    )

    logger.info(
        "Outline generation complete."
    )      

def _valid_chapter_ranges(chapters, total_chunks):
    """Validate the LLM's per-chapter chunk ranges.

    Returns a list of (start, end) tuples only when the ranges form a complete,
    contiguous, non-overlapping partition of chunks 0..total_chunks-1 (each
    chapter ordered as returned). Returns None when any range is missing,
    malformed, out of bounds, or leaves gaps — the caller then falls back to an
    even split.
    """
    if total_chunks <= 0:
        return None
    ranges = []
    next_start = 0
    for ch in chapters:
        if not isinstance(ch, dict):
            return None
        start = ch.get("start_chunk")
        end = ch.get("end_chunk")
        if not isinstance(start, int) or not isinstance(end, int):
            return None
        if start != next_start or end < start or end >= total_chunks:
            return None
        ranges.append((start, end))
        next_start = end + 1
    if next_start != total_chunks:
        return None
    return ranges


def generate_lecture_outline(
    objects_dir: str,
    output_dir: str,
) -> dict:
    """
    Generate the lecture outline from per-chunk knowledge objects.
    Chunk ranges (start_chunk / end_chunk) are taken from the LLM when valid,
    otherwise assigned by dividing the available objects equally among chapters.
    """
    merged_dir = Path(objects_dir)
    objects = []
    object_files = []
    for f in sorted(merged_dir.glob("chunk_*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            objects.append(json.load(fh))
        object_files.append(str(f))
    total_chunks = len(objects)

    # Hash-of-inputs cache (ROADMAP P1.4): same merged objects → same outline,
    # so re-runs skip the LLM call entirely.
    outline_path = Path(output_dir) / "notes" / "lecture_outline.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    marker = outline_path.with_name(".outline.sha256")
    if outputs_current(marker, [outline_path], *object_files):
        logger.info("Outline generation: up to date, skipping LLM call.")
        with open(outline_path, "r", encoding="utf-8") as fh:
            outline = json.load(fh)
        return {
            "outline_path": str(outline_path),
            "num_chapters": len(outline.get("chapters", [])),
        }

    # Build proto‑chapters so the LLM has something to work with
    proto_chapters = []
    for obj in objects:
        proto_chapters.append({
            "chapter_id": obj.get("chunk_id", 0),
            "topics": [obj.get("topic", "")] if obj.get("topic") else [],
            "concepts": obj.get("concepts", []),
            "lecture_notes": obj.get("lecture_notes", ""),
        })

    outline_text = generate_outline(proto_chapters)
    outline = parse_outline(outline_text)

    chapters = outline.get("chapters", [])
    if not outline.get("lecture_title") and chapters and isinstance(chapters[0], dict) and chapters[0].get("title"):
        outline["lecture_title"] = chapters[0]["title"]

    # Tiered chapter cap mirroring the outline prompt's dynamic scaling tiers
    # (outline_prompts.py): short ≤4, medium ≤6, substantial ≤9, deep-dive ≤14.
    if total_chunks <= 12:
        target_chapters = 4
    elif total_chunks <= 25:
        target_chapters = 6
    elif total_chunks <= 45:
        target_chapters = 9
    else:
        target_chapters = 14

    if len(chapters) > target_chapters:
        logger.info(f"Capping generated chapters from {len(chapters)} to target maximum of {target_chapters}.")
        chapters = chapters[:target_chapters]
        outline["chapters"] = chapters

    num_chapters = len(chapters)
    if num_chapters == 0:
        raise ValueError("Outline generation produced zero chapters.")
    if num_chapters > total_chunks:
        logger.info(f"Clamping {num_chapters} chapters to {total_chunks} chunks.")
        chapters = chapters[:total_chunks]
        outline["chapters"] = chapters
        num_chapters = total_chunks

    # Honor the LLM's per-chapter chunk ranges when they form a valid, complete,
    # contiguous partition of all chunks; otherwise fall back to an even split.
    ranges = _valid_chapter_ranges(chapters, total_chunks)
    if ranges is None:
        logger.info("LLM chapter ranges invalid/incomplete; falling back to even chunk split.")
        per_chapter = max(1, total_chunks // num_chapters)
        ranges = []
        for i in range(num_chapters):
            start = i * per_chapter
            end = min((i + 1) * per_chapter - 1, total_chunks - 1)
            if i == num_chapters - 1:
                end = total_chunks - 1
            ranges.append((start, end))

    for i, (ch, (start, end)) in enumerate(zip(chapters, ranges)):
        ch["chapter_id"]   = i + 1               # renumber 1…N
        ch["start_chunk"]  = start
        ch["end_chunk"]    = end
        ch["chunk_ids"]    = list(range(start, end + 1))   # list of ints

    outline_path = Path(output_dir) / "notes" / "lecture_outline.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    save_outline(outline, outline_path)
    write_marker(marker, *object_files)

    return {
        "outline_path": str(outline_path),
        "num_chapters": num_chapters,
    }


def main():
    result = generate_lecture_outline(
        objects_dir="outputs/merged_objects",
        output_dir="outputs",
    )
    logger.info(f"Outline generated: {result}")


if __name__ == "__main__":
    main()
