import json
import logging
import os
import time
from pathlib import Path

from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# constants

MAX_RETRIES = 5

MODEL_NAME = "gemini-2.5-flash"

NOTES_DIR = Path(
        "outputs/notes"
)

OUTLINE_PATH = Path(
        "outputs/notes/lecture_outline.json"
)

REVIEW_PATH = Path(
        "outputs/notes/outline_review.json"
)


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


client = load_llm()


# Models


class Overlap(BaseModel):

    chapter_a: int

    chapter_b: int

    concept: str

    severity: str


class MergeSuggestion(BaseModel):

    chapters: list[int]

    reason: str


class SplitSuggestion(BaseModel):

    chapter: int

    reason: str


class OwnershipConflict(BaseModel):

    concept: str

    owned_by: list[int]

    recommended_owner: int

    confidence: float


class TransitionSuggestion(BaseModel):

    chapter_a: int

    chapter_b: int

    suggestion: str


class OutlineReview(BaseModel):

    strengths: list[str]

    overlaps: list[Overlap]

    merge_suggestions: list[MergeSuggestion]

    split_suggestions: list[SplitSuggestion]

    ownership_conflicts: list[OwnershipConflict]

    transition_suggestions: list[TransitionSuggestion]

    overall_score: int


# Prompt


OUTLINE_REVIEW_PROMPT = """
You are an expert curriculum designer.

Review this lecture outline.

Your task is NOT to rewrite it.

Identify:

1. Chapters that overlap heavily.
2. Concepts owned by multiple chapters.
3. Chapters that should be merged.
4. Chapters that should be split.
5. Missing transitions.
6. Chapters whose focus concepts are too broad.
7. Chapters whose focus concepts are too narrow.

IMPORTANT

Do not invent problems.

If the outline is already well-structured,
return empty arrays for those categories.

Only report meaningful issues.
Lecture outline:

{outline_json}

Return JSON only.

Match this schema exactly:

{{
  "strengths": ["..."],
  "overlaps": [
    {{"chapter_a": 0, "chapter_b": 0, "concept": "..."}}
  ],
  "merge_suggestions": [
    {{"chapters": [0, 0], "reason": "..."}}
  ],
  "split_suggestions": [
    {{"chapter": 0, "reason": "..."}}
  ],
  "ownership_conflicts": [
    {{"concept": "...", "owned_by": [0, 0], "recommended_owner": 0}}
  ],
  "transition_suggestions": [
    {{"chapter_a": 0, "chapter_b": 0, "suggestion": "..."}}
  ],
  "overall_score": 0
}}
"""


# Functions


def load_outline(

    path

):
    """
    Load lecture_outline.json from disk.
    """

    with open(

        path,
        "r",
        encoding="utf-8"

    ) as f:

        return json.load(

            f

        )


def build_prompt(

    outline

):
    """
    Build the review prompt for a given outline.
    """

    outline_json = (

        json.dumps(

            outline,
            indent=2,
            ensure_ascii=False
        )
    )

    return OUTLINE_REVIEW_PROMPT.format(

        outline_json=outline_json

    )


def generate_review(

    outline

):
    """
    Call the LLM and return raw response text.
    """

    prompt = (

        build_prompt(

            outline

        )
    )

    last_error = None

    for attempt in range(

        MAX_RETRIES

    ):

        try:

            response = (

                client.models.generate_content(

                    model=MODEL_NAME,
                    contents=prompt
                )
            )

            return response.text

        except Exception as e:

            last_error = e

            logger.error(

                f"Attempt "
                f"{attempt + 1}"
                f"/"
                f"{MAX_RETRIES}"
                f" failed: "
                f"{e}"
            )

            time.sleep(

                2 ** attempt

            )

    raise RuntimeError(

        f"All retries failed: "
        f"{last_error}"
    )


def parse_review(

    raw_text

):
    """
    Parse and validate the LLM response into an OutlineReview.
    """

    cleaned = (

        raw_text

        .strip()

        .removeprefix("```json")

        .removeprefix("```")

        .removesuffix("```")

        .strip()
    )

    data = json.loads(

        cleaned

    )

    return OutlineReview(

        **data

    )


def save_review(

    review

):
    """
    Save the review to outputs/notes/outline_review.json.
    """

    NOTES_DIR.mkdir(

        parents=True,
        exist_ok=True
    )

    with open(

        REVIEW_PATH,
        "w",
        encoding="utf-8"

    ) as f:

        json.dump(

            review.model_dump(),
            f,
            indent=2,
            ensure_ascii=False
        )

    logger.info(

        f"Saved review to "
        f"{REVIEW_PATH}"
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

    outline = (

        load_outline(

            OUTLINE_PATH

        )
    )

    try:

        raw_text = (

            generate_review(

                outline

            )
        )

        review = (

            parse_review(

                raw_text

            )
        )

        save_review(

            review

        )

    except Exception as e:

        logger.error(

            f"Failed: "
            f"{e}"
        )

        return

    logger.info(

        "Outline review complete."
    )


if __name__ == "__main__":

    main()