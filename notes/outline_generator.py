import json
import logging
from pathlib import Path
import os

from google import genai
from dotenv import load_dotenv
from notes.outline_prompts import OUTLINE_PROMPT


load_dotenv()

from backend.ratelimit import rate_limiter as _limiter
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

        payload.append({

            "chapter_id":
            chapter["chapter_id"],

            "topics":
            chapter["topics"][:5],

            "concepts":
            chapter["concepts"][:10],

            "summary":
            " ".join(
                chapter[
                    "lecture_notes"
                ]
            )[:1000]
        })

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

        +

        "\n\n"

        +

        json.dumps(
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
            contents=[prompt],
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=LectureOutlineModel,
            )
        )
    )

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

def generate_lecture_outline(
    merged_objects_dir: str,
    output_dir: str,
) -> dict:
    """
    Generate the lecture outline from merged knowledge objects.
    Chunk ranges (start_chunk / end_chunk) are automatically assigned
    by dividing the available merged objects equally among chapters.
    """
    merged_dir = Path(merged_objects_dir)
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
            "concepts": obj.get("concepts", [])[:10],
            "lecture_notes": obj.get("lecture_notes", [])[:5],
        })

    outline_text = generate_outline(proto_chapters)
    outline = parse_outline(outline_text)

    chapters = outline.get("chapters", [])
    if not outline.get("lecture_title") and chapters and isinstance(chapters[0], dict) and chapters[0].get("title"):
        outline["lecture_title"] = chapters[0]["title"]

    target_chapters = max(3, min(8, max(3, total_chunks // 3)))
    if len(chapters) > target_chapters and target_chapters > 0:
        logger.info(f"Capping generated chapters from {len(chapters)} to target maximum of {target_chapters}.")
        chapters = chapters[:target_chapters]
        outline["chapters"] = chapters

    num_chapters = len(chapters)
    if num_chapters == 0:
        raise ValueError("Outline generation produced zero chapters.")

    # Assign chunk ranges evenly across the total merged objects
    per_chapter = max(1, total_chunks // num_chapters)
    
    for i, ch in enumerate(chapters):
        start = i * per_chapter
        end   = min((i + 1) * per_chapter - 1, total_chunks - 1)
        if i == num_chapters - 1:
            end = total_chunks - 1

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
        merged_objects_dir="outputs/merged_objects",
        output_dir="outputs",
    )
    logger.info(f"Outline generated: {result}")


if __name__ == "__main__":
    main()
