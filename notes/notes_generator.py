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
import random
import re
from pathlib import Path
import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from notes.notes_prompt import NOTES_PROMPT
load_dotenv()

from backend.ratelimit import rate_limiter as _limiter

logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

#constants

from config import MODEL_NAME, DEFAULT_MAX_RETRIES

MAX_RETRIES = DEFAULT_MAX_RETRIES
NOTES_DIR = Path(
        "outputs/notes"
)
CHAPTER_DIR = Path(
        "outputs/chapters"
)
MAX_WORKERS = 4
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
            _limiter.wait()
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

        time.sleep(5 * (attempt + 1) + random.uniform(0.5, 3.0))

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

    # ── Guard: skip if the chapter JSON was never built ────────────────────
    chapter_file = CHAPTER_DIR / f"chapter_{chapter_id}.json"
    if not chapter_file.exists():
        logger.warning(
            f"Skipping chapter {chapter_id}: chapter JSON not found"
        )
        return

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

def generate_study_notes(
    chapters_dir: str,
    outline_path: str,
    output_dir: str,
    max_workers: int = 7,
) -> dict:
    """
    Generate study notes for all chapters.

    Args:
        chapters_dir: directory containing chapter_*.json files.
        outline_path: path to lecture_outline.json.
        output_dir:   directory where chapter_*.md and notes.md will be saved.
        max_workers:  number of parallel LLM calls.

    Returns:
        { "notes_dir": str, "num_chapters": int }
    """
    notes_dir = Path(output_dir) / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Point the global NOTES_DIR to the lecture‑scoped directory
    import notes.notes_generator as _nsg
    _nsg.NOTES_DIR = notes_dir
    _nsg.CHAPTER_DIR = Path(chapters_dir)

    chapters = load_chapters(chapters_dir)
    outline = load_outline(outline_path)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_chapter, ch, outline, outline)
            for ch in chapters
        ]
        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Chapter worker failed: {e}")
            completed += 1
            logger.info(f"Progress: {completed}/{total}")

    combine_notes()   # still writes to NOTES_DIR (now lecture‑scoped)

    return {
        "notes_dir": str(notes_dir),
        "num_chapters": len(chapters),
    }


# ── Task 2.3: Consolidated Chapter Artifact Generator ─────────────────────────
from pydantic import BaseModel, Field
from cache_util import outputs_current, write_marker
from assessment.assessment_models import Question
from flashcards.generate_flashcards import convert_assessment_to_flashcards
from revision_notes.revision_generator import render_revision_markdown


from typing import Literal


class CoreConceptItem(BaseModel):
    concept: str
    explanation: str


class StudyNoteSection(BaseModel):
    section_type: Literal["definition", "callout", "table", "list", "code", "prose"] = Field(
        description="Type of UI card: 'definition' for core concepts/overview, 'callout' for key insights/observations, 'table' for comparisons, 'list' for takeaways/applications, 'code' for code snippets, 'prose' for general deep dives."
    )
    title: str = Field(description="Section heading title (e.g. '1. INTRODUCTION TO NETWORK INFRASTRUCTURE')")
    content_markdown: str = Field(description="Markdown content body for this section. Include tables, bullet points, code blocks, or math ($...$) when applicable. Do NOT include markdown image tags.")


class MergedChapterArtifactsModel(BaseModel):
    chapter_id: int
    incomplete: bool = Field(default=False, description="Set to true if content generation was degraded")
    study_notes_title: str = Field(description="Chapter title heading")
    study_notes_sections: list[StudyNoteSection] = Field(description="Structured UI sections/cards for the chapter notes. Scale section count and content depth strictly based on information density.")
    revision_summary: list[str] = Field(description="3 to 5 key exam takeaways for this chapter.")
    core_concepts_breakdown: list[CoreConceptItem] = Field(description="List of key concepts with brief 1-2 sentence explanations.")
    assessment_questions: list[Question] = Field(description="Quiz questions with embedded flashcard_front/back/explanation fields.")


def process_chapter_artifacts_merged(chapter_json: dict, outline: dict, output_dir: str):
    """
    Generate Study Notes, Revision Notes, Assessment Questions, and Flashcards
    for 1 chapter in 1 consolidated LLM call.
    """
    chapter_id = chapter_json.get("chapter_id", 1)
    chapter_title = chapter_json.get("title", f"Chapter {chapter_id}")

    prompt = f"""
Generate comprehensive learning artifacts for Chapter {chapter_id}: "{chapter_title}".

Chapter Content JSON:
{json.dumps(chapter_json, indent=2)}

Produce a valid JSON object matching MergedChapterArtifactsModel:
1. study_notes_title: Professional chapter title heading.
2. study_notes_sections: Array of structured StudyNoteSection cards covering all topics, definitions, mechanisms, and examples present in the chapter content.
   - DENSITY & LENGTH: Scale depth strictly based on information density. Dense, multi-concept chapters must be written in comprehensive depth across 3 to 6 structured sections (800–1200+ words total); narrower topics should be concise without filler.
   - SECTION TYPES: Choose appropriate section_type ('definition' for concepts/overview, 'callout' for key insights, 'table' for comparisons, 'list' for takeaways, 'code' for code, 'prose' for deep dives).
   - FORMATTING: Incorporate comparison tables, bullet points, code snippets, and LaTeX math ($...$ for inline, $$...$$ for display math) whenever naturally applicable.
   - IMAGES: Do NOT include inline markdown image tags (e.g. ![...](...)).
3. revision_summary: 3-5 concise bullet points for exam revision.
4. core_concepts_breakdown: Key concepts with short explanations.
5. assessment_questions: 3 quiz questions (MCQ/Short Answer) with flashcard_front/back/explanation fields.
"""

    notes_dir = Path(output_dir) / "notes"
    revision_dir = Path(output_dir) / "revision"
    assessment_dir = Path(output_dir) / "assessment"
    flashcards_dir = Path(output_dir) / "flashcards"

    for d in (notes_dir, revision_dir, assessment_dir, flashcards_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── Cache: skip this chapter when its artifacts already exist for the
    # ── same inputs (re-runs cost ~0 API calls). See ROADMAP P1.4.
    chapter_outputs = [
        notes_dir / f"chapter_{chapter_id}.md",
        notes_dir / f"chapter_{chapter_id}.json",
        revision_dir / f"revision_chapter_{chapter_id}.md",
        assessment_dir / f"assessment_chapter_{chapter_id}.json",
        flashcards_dir / f"flashcards_chapter_{chapter_id}.json",
    ]
    marker = notes_dir / f".artifacts_ch{chapter_id}.sha256"
    if outputs_current(marker, chapter_outputs, chapter_json):
        logger.info(
            f"Chapter {chapter_id} consolidated artifacts: up to date, skipping"
        )
        return

    for attempt in range(MAX_RETRIES):
        try:
            _limiter.wait()
            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    response_schema=MergedChapterArtifactsModel,
                )
            )
            if not response or not response.text:
                raise ValueError("Gemini returned empty or blocked response (response.text is None)")
            data = json.loads(response.text)
            model = MergedChapterArtifactsModel(**data)

            # 1a. Render & Save Unified Markdown for chapter_N.md (for RAG tutor, combine_notes, etc.)
            md_lines = [f"# {model.study_notes_title}\n"]
            for sec in model.study_notes_sections:
                if sec.title:
                    md_lines.append(f"## {sec.title}")
                md_lines.append(f"{sec.content_markdown}\n")
            full_notes_md = "\n\n".join(md_lines)

            notes_file = notes_dir / f"chapter_{chapter_id}.md"
            with open(notes_file, "w", encoding="utf-8") as f:
                f.write(full_notes_md)

            # 1b. Save Structured JSON for 100% deterministic frontend card rendering
            notes_json_file = notes_dir / f"chapter_{chapter_id}.json"
            notes_json_data = {
                "chapter_id": chapter_id,
                "title": model.study_notes_title,
                "sections": [s.model_dump() for s in model.study_notes_sections]
            }
            with open(notes_json_file, "w", encoding="utf-8") as f:
                json.dump(notes_json_data, f, indent=4, ensure_ascii=False)

            # 2. Render & Save Revision Markdown
            rev_md = render_revision_markdown(
                chapter_id=chapter_id,
                chapter_title=chapter_title,
                revision_summary=model.revision_summary,
                core_concepts_breakdown=model.core_concepts_breakdown,
            )
            rev_file = revision_dir / f"revision_chapter_{chapter_id}.md"
            with open(rev_file, "w", encoding="utf-8") as f:
                f.write(rev_md)

            # 3. Save Assessment Questions JSON
            questions_dicts = [q.model_dump() for q in model.assessment_questions]
            ass_data = {
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "questions": questions_dicts,
            }
            ass_file = assessment_dir / f"assessment_chapter_{chapter_id}.json"
            with open(ass_file, "w", encoding="utf-8") as f:
                json.dump(ass_data, f, indent=4, ensure_ascii=False)

            # 4. Save Flashcards JSON (0-call transformation)
            cards = convert_assessment_to_flashcards(questions_dicts)
            cards_data = {
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "flashcards": cards,
            }
            cards_file = flashcards_dir / f"flashcards_chapter_{chapter_id}.json"
            with open(cards_file, "w", encoding="utf-8") as f:
                json.dump(cards_data, f, indent=4, ensure_ascii=False)

            logger.info(f"Chapter {chapter_id} consolidated artifacts generated successfully.")
            write_marker(marker, chapter_json)
            return
        except Exception as e:
            logger.warning(f"Chapter {chapter_id} consolidated artifacts attempt {attempt+1} failed: {e}")
            time.sleep(2 * (attempt + 1))

    # Graceful degradation: write fallback files for all 4 artifacts with incomplete: true
    logger.error(f"Chapter {chapter_id} consolidated artifacts failed after 3 retries. Marking incomplete.")
    notes_file = notes_dir / f"chapter_{chapter_id}.md"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write(f"# Chapter {chapter_id}: {chapter_title}\n\n*Note: Content generation was partially degraded for this chapter.*")

    rev_file = revision_dir / f"revision_chapter_{chapter_id}.md"
    with open(rev_file, "w", encoding="utf-8") as f:
        f.write(f"# Revision Notes — Chapter {chapter_id}: {chapter_title}\n\n*Note: Content generation was partially degraded for this chapter.*")

    ass_file = assessment_dir / f"assessment_chapter_{chapter_id}.json"
    with open(ass_file, "w", encoding="utf-8") as f:
        json.dump({"chapter_id": chapter_id, "chapter_title": chapter_title, "incomplete": True, "questions": []}, f, indent=4)

    cards_file = flashcards_dir / f"flashcards_chapter_{chapter_id}.json"
    with open(cards_file, "w", encoding="utf-8") as f:
        json.dump({"chapter_id": chapter_id, "chapter_title": chapter_title, "incomplete": True, "flashcards": []}, f, indent=4)

    write_marker(marker, chapter_json)


def generate_consolidated_chapter_artifacts(
    chapters_dir: str,
    outline_path: str,
    output_dir: str,
    max_workers: int = 3,
) -> dict:
    """
    Generate all chapter artifacts (Study Notes, Revision Notes, Assessment, Flashcards)
    in parallel 1-call per chapter batches.
    """
    chapters = load_chapters(chapters_dir)
    outline = load_outline(outline_path)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_chapter_artifacts_merged, ch, outline, output_dir)
            for ch in chapters
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Merged chapter artifact worker failed: {e}")

    # Combine notes & revision files into main summary files
    import notes.notes_generator as _nsg
    _nsg.NOTES_DIR = Path(output_dir) / "notes"
    _nsg.CHAPTER_DIR = Path(chapters_dir)
    combine_notes()

    return {
        "output_dir": output_dir,
        "num_chapters": len(chapters),
    }


if __name__ == "__main__":

    main()