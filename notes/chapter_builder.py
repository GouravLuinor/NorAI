"""
chapter_builder.py

Reads lecture_outline.json + merged chunk objects.
Builds and saves one chapter_N.json per chapter.

No embeddings. No LLM. No clustering.
"""

import json
import logging
from pathlib import Path

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(
    __name__
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_list(value):
    """
    Safely coerce a field to list.

    None  -> []
    str   -> [str]   (LLM returned a string instead of a list)
    list  -> list    (correct case)
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Chapter(BaseModel):

    chapter_id: int

    lecture_title: str

    title: str

    start_chunk: int

    end_chunk: int

    chunk_ids: list[int]

    focus_concepts: list[str]

    topics: list[str]

    concepts: list[str]

    lecture_notes: list[str]

    visual_notes: list[str]

    important_information: list[str]

    inferred_knowledge: list[str]

    screenshots: list[str]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_outline(
    outline_path
):

    outline_path = Path(
        outline_path
    )

    if not outline_path.exists():

        raise FileNotFoundError(
            f"Outline not found: "
            f"{outline_path}"
        )

    with open(
        outline_path,
        "r",
        encoding="utf-8"
    ) as f:

        outline = json.load(f)

    logger.info(
        f"Loaded outline: "
        f"{len(outline.get('chapters', []))} chapters "
        f"from {outline_path}"
    )

    return outline


def load_merged_objects(
    merged_dir
):

    merged_dir = Path(
        merged_dir
    )

    if not merged_dir.exists():

        raise FileNotFoundError(
            f"Merged objects directory not found: "
            f"{merged_dir}"
        )

    files = sorted(
        merged_dir.glob(
            "chunk_*.json"
        )
    )

    if not files:

        raise ValueError(
            f"No chunk_*.json files found in: "
            f"{merged_dir}"
        )

    merged_objects = []

    for file_path in files:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            merged_objects.append(
                json.load(f)
            )

    merged_objects.sort(
        key=lambda x: x["chunk_id"]
    )

    logger.info(
        f"Loaded {len(merged_objects)} merged objects "
        f"from {merged_dir}"
    )

    return merged_objects


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_chapters(
    outline,
    merged_objects
):

    chunk_lookup = {
        obj["chunk_id"]: obj
        for obj in merged_objects
    }

    lecture_title = outline.get(
        "lecture_title",
        ""
    )

    chapters = []

    for chapter_entry in outline["chapters"]:

        chapter_id    = chapter_entry["chapter_id"]
        title         = chapter_entry["title"]
        start_chunk   = chapter_entry["start_chunk"]
        end_chunk     = chapter_entry["end_chunk"]
        focus_concepts = chapter_entry.get(
            "focus_concepts",
            []
        )

        chunk_ids = list(
            range(
                start_chunk,
                end_chunk + 1
            )
        )

        # Validate all required chunks are present
        missing = [
            cid
            for cid in chunk_ids
            if cid not in chunk_lookup
        ]

        if missing:

            logger.warning(
                f"Chapter {chapter_id} "
                f"('{title}'): "
                f"missing chunk IDs {missing} "
                f"— skipping those chunks."
            )

            chunk_ids = [
                cid
                for cid in chunk_ids
                if cid in chunk_lookup
            ]

        # Aggregate fields across chunks
        topics                = []
        concepts              = []
        lecture_notes         = []
        visual_notes          = []
        important_information = []
        inferred_knowledge    = []
        screenshots           = []

        for chunk_id in chunk_ids:

            obj = chunk_lookup[chunk_id]

            if topic := obj.get("topic"):
                topics.append(topic)

            concepts.extend(
                to_list(obj.get("concepts"))
            )

            important_information.extend(
                to_list(obj.get("important_information"))
            )

            inferred_knowledge.extend(
                to_list(obj.get("inferred_knowledge"))
            )

            screenshots.extend(
                to_list(obj.get("screenshots"))
            )

            # Preserve chronological order —
            # deduplication would destroy teaching flow
            lecture_notes.extend(
                to_list(obj.get("lecture_notes"))
            )

            visual_notes.extend(
                to_list(obj.get("visual_notes"))
            )

        # Deduplicate while preserving first-seen order
        chapter = Chapter(

            chapter_id=chapter_id,

            lecture_title=lecture_title,

            title=title,

            start_chunk=start_chunk,

            end_chunk=end_chunk,

            chunk_ids=chunk_ids,

            focus_concepts=focus_concepts,

            topics=list(
                dict.fromkeys(topics)
            ),

            concepts=list(
                dict.fromkeys(concepts)
            ),

            lecture_notes=lecture_notes,

            visual_notes=visual_notes,

            important_information=list(
                dict.fromkeys(important_information)
            ),

            inferred_knowledge=list(
                dict.fromkeys(inferred_knowledge)
            ),

            screenshots=list(
                dict.fromkeys(screenshots)
            ),
        )

        chapters.append(chapter)

        logger.info(
            f"Chapter {chapter_id}: "
            f"{start_chunk} -> {end_chunk} "
            f"| '{title}'"
        )

    logger.info(
        f"Built {len(chapters)} chapters total."
    )

    return chapters


# ---------------------------------------------------------------------------
# Saver
# ---------------------------------------------------------------------------

def save_chapters(
    chapters,
    output_dir
):

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    for chapter in chapters:

        output_path = (
            output_dir
            /
            f"chapter_{chapter.chapter_id}.json"
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                chapter.model_dump(),
                f,
                indent=4,
                ensure_ascii=False
            )

        logger.info(
            f"Saved: "
            f"{output_path}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    outline = load_outline(
        "outputs/notes/lecture_outline.json"
    )

    merged_objects = load_merged_objects(
        "outputs/merged_objects"
    )

    chapters = build_chapters(
        outline,
        merged_objects
    )

    save_chapters(
        chapters,
        "outputs/chapters"
    )

    logger.info(
        "Chapter building complete."
    )


if __name__ == "__main__":
    main()