"""
notes_generator.py
├── Config
├── Gemini Client
├── load_chapters()
├── build_prompt()
├── generate_chapter_notes()
├── save_chapter_markdown()
├── process_chapter()
├── combine_notes()
└── main()
"""


from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)
import json
import logging
import re
from pathlib import Path
import os
import time
from google import genai
from dotenv import load_dotenv
from notes.notes_prompt import NOTES_PROMPT
load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

#constants

MAX_RETRIES = 5
MODEL_NAME = "gemma-4-26b-a4b-it"
NOTES_DIR = Path(
        "outputs/notes"
)
CHAPTER_DIR = Path(
        "outputs/chapters"
)
MAX_WORKERS = 7
# LLM Setup


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


# Load Chapters

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


def load_outline(
    outline_path
):

    with open(
        outline_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)
    

def get_outline_chapter(
    chapter_id,
    outline
):

    for chapter in (
        outline["chapters"]
    ):

        if (
            chapter["chapter_id"]
            ==
            chapter_id
        ):

            return chapter

    raise ValueError(
        f"Outline chapter "
        f"{chapter_id} "
        f"not found."
    )


#building prompt

def build_prompt(
chapter,
outline_chapter,
lecture_outline,
previous_outline=None,
next_outline=None
):

    lecture_map = []

    for ch in lecture_outline["chapters"]:

        lecture_map.append({

            "chapter_id":
            ch["chapter_id"],

            "title":
            ch["title"],

            "focus_concepts":
            ch["focus_concepts"]
        })

    previous_title = (
        previous_outline["title"]
        if previous_outline
        else "None"
    )

    next_title = (
        next_outline["title"]
        if next_outline
        else "None"
    )

    chapter_context = {

        "chapter_id":
        chapter["chapter_id"],

        "chapter_title":
        chapter["title"],

        "focus_concepts":
        chapter["focus_concepts"],

        "topics":
        chapter["topics"],

        "concepts":
        chapter["concepts"],

        "lecture_notes":
        chapter["lecture_notes"],

        "visual_notes":
        chapter["visual_notes"],

        "important_information":
        chapter[
            "important_information"
        ],

        "inferred_knowledge":
        chapter[
            "inferred_knowledge"
        ]
    }

    return f"""
    {NOTES_PROMPT}

    ==================================================

    LECTURE STRUCTURE

    Previous Chapter:
    {previous_title}

    Current Chapter:
    {outline_chapter["title"]}

    Next Chapter:
    {next_title}

    ==================================================



    FULL LECTURE STRUCTURE

    The complete lecture is organized
    into the following chapters:

    {json.dumps(
        lecture_map,
        indent=4,
        ensure_ascii=False
    )}

    Use this structure to understand:

    - what concepts belong to each chapter
    - what concepts have already been covered
    - what concepts will be covered later

    Avoid stealing content from other chapters.

    Focus primarily on the concepts owned
    by the CURRENT chapter.

    ==================================================

    PRIMARY RESPONSIBILITY OF THIS CHAPTER

    The chapter should focus heavily on:

    {json.dumps(
        outline_chapter["focus_concepts"],
        indent=4,
        ensure_ascii=False
    )}

    Most of the explanation should revolve
    around these concepts.

    Avoid spending significant space on concepts
    outside this list.

    If concepts outside this list appear in the
    source material, reference them briefly and
    return focus to the concepts owned by this chapter.

    ==================================================

    REQUIRED NOTE STRUCTURE

    # Chapter Title

    ## Core Concepts

    ## Detailed Explanation

    ## Important Observations

    ## Applications

    ## Key Takeaways

    Only include sections that are useful.

    Do not force sections that have little content.

    ==================================================

    IMPORTANT

    This chapter is part of a larger study guide.

    Assume previous chapters have already been read.

    Do not re-introduce concepts that belong
    to previous chapters unless absolutely necessary.

    Do not write a standalone article.

    Focus primarily on the chapter's focus concepts.

    If a concept appears in the source material
    but is not central to this chapter,
    mention it briefly instead of re-explaining it.

    Avoid repeating material that naturally belongs
    to previous chapters.

    Avoid introducing material that naturally belongs
    to later chapters.

    ==================================================

    SOURCE MATERIAL

    {json.dumps(
        chapter_context,
        indent=4,
        ensure_ascii=False
    )}

    ==================================================

    FINAL INSTRUCTIONS

    Generate notes for the CURRENT CHAPTER ONLY.

    Use the provided chapter title.

    Do not generate a different title.

    Do not create a lecture-wide introduction.

    Do not create a lecture-wide conclusion.

    The notes should feel like one chapter of a
    larger textbook or study guide.

    Return markdown only.

    Do not return JSON.

    Do not wrap the response inside markdown
    code fences.
    """





#generate chapter notes


def generate_chapter_notes(
    chapter,
    outline_chapter,
    lecture_outline,
    previous_outline=None,
    next_outline=None
):
    """
    Generate markdown notes.
    """

    prompt = build_prompt(
        chapter,
        outline_chapter,
        lecture_outline,
        previous_outline,
        next_outline
    )

    for attempt in range(
        MAX_RETRIES
    ):
        logger.info(
            f"Chapter "
            f"{chapter['chapter_id']} "
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

            markdown = (
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

            return markdown

        except Exception as e:

            logger.warning(
                f"Chapter "
                f"{chapter['chapter_id']} "
                f"Attempt "
                f"{attempt+1} "
                f"failed: {e}"
            )

            time.sleep(
                5 * (
                    attempt + 1
                )
            )

    raise RuntimeError(
        f"Failed chapter "
        f"{chapter['chapter_id']}"
    )


#SAVE CHAPTER MARKDOWN

def save_chapter_markdown(
    chapter_id,
    markdown
):
    """
    Save markdown file.
    """

    output_path = (
        NOTES_DIR
        /
        f"chapter_{chapter_id}.md"
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


#PROCESS CHAPTER

def process_chapter(
    chapter,
    outline,
    lecture_outline
):
    """
    Process one chapter.
    """

    outline_chapter = (
        get_outline_chapter(
            chapter["chapter_id"],
            outline
        )
    )

    chapter_id = chapter["chapter_id"]

    previous_outline = None
    next_outline = None

    if chapter_id > 1:

        previous_outline = (
            get_outline_chapter(
                chapter_id - 1,
                outline
            )
        )

    if chapter_id < len(
        outline["chapters"]
    ):

        next_outline = (
            get_outline_chapter(
                chapter_id + 1,
                outline
            )
        )

    output_path = (
        NOTES_DIR
        /
        f"chapter_{chapter_id}.md"
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

    markdown = (
        generate_chapter_notes(
            chapter,
            outline_chapter,
            lecture_outline,
            previous_outline,
            next_outline
        )
    )

    save_chapter_markdown(
        chapter_id,
        markdown
    )

    logger.info(
        f"Finished "
        f"chapter "
        f"{chapter_id}"
    )


#comibines notes

def combine_notes():
    """
    Combine all markdown files.
    """

    markdown_files = sorted(

        NOTES_DIR.glob(
            "chapter_*.md"
        ),

        key=lambda x:
        int(
            x.stem.split(
                "_"
            )[1]
        )
    )

    final_notes = []

    for file_path in (
        markdown_files
    ):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            final_notes.append(
                f.read()
            )

    output_path = (
        NOTES_DIR
        /
        "notes.md"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n\n---\n\n".join(
                final_notes
            )
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )

def main():

    logger.info(
        f"Using model: "
        f"{MODEL_NAME}"
        )
    
    NOTES_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    chapters = (
        load_chapters(
            CHAPTER_DIR
        )
    )
    outline = (
        load_outline(
        "outputs/notes/lecture_outline.json"
        )
    )
    with ThreadPoolExecutor(
        max_workers=
        MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                process_chapter,
                chapter,
                outline,
                outline
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

    combine_notes()

    logger.info(
        "Notes generation complete."
    )


if __name__ == "__main__":

    main()