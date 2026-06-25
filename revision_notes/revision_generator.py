"""
revision_generator.py
├── Config
├── Gemini Client
├── load_outline()
├── load_chapter_notes()
├── build_prompt()
├── generate_revision()
├── save_revision()
├── process_chapter()
├── combine_revision_notes()
├── build_metadata()
└── main()
"""


from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)
import json
import logging
from pathlib import Path
import os
import time
from datetime import datetime, timezone
from google import genai
from dotenv import load_dotenv
from revision_notes.revision_prompts import REVISION_PROMPT
from revision_notes.revision_models import (
    RevisionMetadata,
    RevisionChapter,
    RevisionNotes
)
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Constants

MAX_RETRIES = 5
MODEL_NAME = "gemma-4-26b-a4b-it"
NOTES_DIR = Path(
    "outputs/notes"
)
REVISION_DIR = Path(
    "outputs/revision"
)
OUTLINE_PATH = (
    NOTES_DIR
    / "lecture_outline.json"
)
MAX_WORKERS = 7

# LLM Setup


def load_llm():
    """
    Load Gemini client.
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


client = load_llm()


# Load Outline

def load_outline(
    outline_path
):
    """
    Load lecture_outline.json.

    Used for:
    - lecture title
    - chapter titles
    - ordering
    """

    with open(
        outline_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# Load Chapter Notes

def load_chapter_notes(
    chapter_id
):
    """
    Load chapter markdown from notes dir.

    Returns str.
    """

    notes_path = (
        NOTES_DIR
        / f"chapter_{chapter_id}.md"
    )

    with open(
        notes_path,
        "r",
        encoding="utf-8"
    ) as f:

        return f.read()


# Build Prompt

def build_prompt(
    chapter_title,
    markdown
):
    """
    Build revision prompt.

    Receives chapter title and markdown.
    Returns REVISION_PROMPT + chapter markdown.
    """

    return f"""
    {REVISION_PROMPT}

    ==================================================

    CHAPTER TITLE

    {chapter_title}

    ==================================================

    STUDY NOTES

    {markdown}
    """


# Generate Revision

def generate_revision(
    chapter_id,
    chapter_title,
    markdown
):
    """
    Generate revision markdown for one chapter.
    """

    prompt = build_prompt(
        chapter_title,
        markdown
    )

    for attempt in range(
        MAX_RETRIES
    ):
        logger.info(
            f"Chapter "
            f"{chapter_id} "
            f"Prompt Size: "
            f"{len(prompt)} chars"
        )
        try:

            response = (
                client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[
                        prompt
                    ]
                )
            )

            revision_markdown = (
                response.text
                .replace(
                    "```markdown",
                    ""
                )
                .replace(
                    "```",
                    ""
                )
                .strip()
            )

            return revision_markdown

        except Exception as e:

            logger.warning(
                f"Chapter "
                f"{chapter_id} "
                f"Attempt "
                f"{attempt + 1} "
                f"failed: {e}"
            )

            time.sleep(
                5 * (
                    attempt + 1
                )
            )

    raise RuntimeError(
        f"Failed chapter "
        f"{chapter_id}"
    )


# Save Revision

def save_revision(
    chapter_id,
    markdown
):
    """
    Save revision markdown file.
    """

    output_path = (
        REVISION_DIR
        / f"revision_chapter_{chapter_id}.md"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            markdown
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )


# Process Chapter

def process_chapter(
    chapter,
):
    """
    Load notes → generate revision → save.
    """

    chapter_id = chapter["chapter_id"]
    chapter_title = chapter["title"]

    output_path = (
        REVISION_DIR
        / f"revision_chapter_{chapter_id}.md"
    )

    if output_path.exists():

        logger.info(
            f"Skipping "
            f"chapter "
            f"{chapter_id}"
        )

        return

    logger.info(
        f"Starting "
        f"chapter "
        f"{chapter_id}"
    )

    markdown = load_chapter_notes(
        chapter_id
    )

    revision = generate_revision(
        chapter_id,
        chapter_title,
        markdown
    )

    save_revision(
        chapter_id,
        revision
    )

    logger.info(
        f"Finished "
        f"chapter "
        f"{chapter_id}"
    )


# Combine Revision Notes

def combine_revision_notes():
    """
    Merge all revision chapter files
    into revision_notes.md.
    """

    revision_files = sorted(

        REVISION_DIR.glob(
            "revision_chapter_*.md"
        ),

        key=lambda x:
        int(
            x.stem.split(
                "_"
            )[-1]
        )
    )

    combined = []

    for file_path in (
        revision_files
    ):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            combined.append(
                f.read()
            )

    output_path = (
        REVISION_DIR
        / "revision_notes.md"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n\n---\n\n".join(
                combined
            )
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )

    return combined


# Build Metadata

def build_metadata(
    outline,
    combined
):
    """
    Build RevisionMetadata and RevisionNotes.
    Save revision_metadata.json.
    """

    full_text = "\n\n".join(
        combined
    )

    word_count = len(
        full_text.split()
    )

    estimated_read_time = max(
        1,
        word_count // 200
    )

    total_chapters = len(
        outline["chapters"]
    )

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    metadata = RevisionMetadata(
        lecture_title=
        outline["lecture_title"],
        total_chapters=
        total_chapters,
        estimated_read_time=
        estimated_read_time,
        word_count=
        word_count,
        generated_at=
        generated_at
    )

    chapters = []

    revision_files = sorted(

        REVISION_DIR.glob(
            "revision_chapter_*.md"
        ),

        key=lambda x:
        int(
            x.stem.split(
                "_"
            )[-1]
        )
    )

    for chapter_data, file_path in zip(
        outline["chapters"],
        revision_files
    ):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            chapter_markdown = f.read()

        chapters.append(
            RevisionChapter(
                chapter_id=
                chapter_data["chapter_id"],
                title=
                chapter_data["title"],
                markdown=
                chapter_markdown
            )
        )

    revision_notes = RevisionNotes(
        metadata=metadata,
        chapters=chapters
    )

    metadata_path = (
        REVISION_DIR
        / "revision_metadata.json"
    )

    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            revision_notes.model_dump_json(
                indent=4
            )
        )

    logger.info(
        f"Saved: "
        f"{metadata_path}"
    )

    return revision_notes


# Main

def main():

    logger.info(
        f"Using model: "
        f"{MODEL_NAME}"
    )

    REVISION_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    outline = load_outline(
        OUTLINE_PATH
    )

    chapters = outline["chapters"]

    logger.info(
        f"Loaded "
        f"{len(chapters)} chapters."
    )

    with ThreadPoolExecutor(
        max_workers=
        MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                process_chapter,
                chapter
            )

            for chapter
            in chapters
        ]

        completed = 0

        total = len(
            futures
        )

        for future in (
            as_completed(
                futures
            )
        ):

            try:

                future.result()

            except Exception as e:

                logger.error(
                    f"Failed: "
                    f"{e}"
                )

            completed += 1

            logger.info(
                f"Progress: "
                f"{completed}"
                f"/"
                f"{total}"
            )

    combined = combine_revision_notes()

    build_metadata(
        outline,
        combined
    )

    logger.info(
        "Revision generation complete."
    )

    from revision_notes.revision_pdf_builder import build_revision_pdf

    build_revision_pdf(
        REVISION_DIR / "revision_notes.md",
        REVISION_DIR / "revision_notes.pdf"
    )


if __name__ == "__main__":

    main()

    