"""
assessment_generator.py

Gemma 4 version: free-form generation + post-hoc Pydantic validation,
same pattern as notes_generator.py.

Why not response_schema: tested directly against this model
(gemma-4-26b-a4b-it) and the call hangs / never returns. Most likely
cause is that grammar-constrained decoding interacts badly with this
model's MoE routing — forcing the decoder onto a schema-compliant
token the router didn't naturally pick can push generation into a
stalled state. thinking_config (budget or level) is also rejected
outright by the API for this model ("not supported for this model").
Free-form generation + validate-after, exactly as done in
notes_generator.py and in this file's earlier version, is the
approach that's actually been reliable on this model — so that's
what this file does. No response_schema, no thinking_config.

Key normalization (_KEY_ALIASES + fuzzy fallback) is the main defense
against Gemma 4's inconsistent field naming (e.g. "answer_text"
instead of "answer", "rationale" instead of "explanation").

Retries are not blind repeats: on failure, the next attempt's prompt
has the previous error appended, so the model gets a concrete chance
to fix the specific thing that broke (bad escaping, wrong field name,
too few/many valid questions) instead of regenerating from the same
prompt and hoping for a different random outcome.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from assessment.assessment_prompts import ASSESSMENT_PROMPT
from assessment.assessment_models import (
    Assessment,
    AssessmentMetadata,
    Question,
    MIN_QUESTIONS_PER_CHAPTER,
    MAX_QUESTIONS_PER_CHAPTER,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_RETRIES = 5
MODEL_NAME = "gemma-4-26b-a4b-it"
NOTES_DIR = Path("outputs/notes")
ASSESSMENT_DIR = Path("outputs/assessment")
MAX_WORKERS = 7
MINUTES_PER_QUESTION = 1.5

# ---------------------------------------------------------------------------
# Key normalizer
#
# Gemma 4 invents its own field names in free-form generation (e.g.
# "answer_text" instead of "answer", "rationale" instead of
# "explanation"). This map covers every known alias seen so far; the
# difflib fuzzy fallback below catches plausible new ones we haven't
# explicitly listed yet.
#
# How to extend: if you see a new "Field required" error in the logs
# for a field like `foo`, check the raw response log for what key
# Gemma 4 actually used, then add  "that_key": "foo"  here.
# ---------------------------------------------------------------------------

_KEY_ALIASES: dict[str, str] = {
    # question
    "question_text":        "question",
    "text":                 "question",
    "stem":                 "question",
    "prompt":               "question",
    "q":                    "question",
    "question_stem":        "question",

    # explanation
    "rationale":            "explanation",
    "reasoning":            "explanation",
    "reason":               "explanation",
    "justification":        "explanation",
    "solution":             "explanation",
    "correct_explanation":  "explanation",
    "answer_explanation":   "explanation",
    "feedback":             "explanation",

    # answer
    "correct_answer":       "answer",
    "correct":               "answer",
    "ans":                  "answer",
    "answer_text":          "answer",
    "correct_option":       "answer",

    # options
    "choices":              "options",
    "answers":              "options",
    "possible_answers":     "options",

    # type
    "question_type":        "type",
    "qtype":                "type",

    # difficulty
    "level":                "difficulty",
    "diff":                 "difficulty",

    # concepts
    "tags":                 "concepts",
    "topics":               "concepts",
    "concept":              "concepts",

    # question_id
    "id":                   "question_id",
    "qid":                  "question_id",
    "num":                  "question_id",
    "number":               "question_id",
}

# Canonical field names a question dict should end up with. Used as the
# match pool for the fuzzy fallback below.
_CANONICAL_FIELDS = [
    "question_id", "chapter_id", "type", "difficulty",
    "concepts", "question", "options", "answer", "explanation",
]

# Below this similarity ratio, a key is treated as genuinely unknown
# rather than a plausible rename, and passed through untouched (where
# Pydantic will ignore it, or raise if it turns out to be required).
_FUZZY_MATCH_CUTOFF = 0.6


def _normalize_question(raw: dict, index: int) -> dict:
    """
    Remap Gemma 4's invented key names to the canonical names
    Question expects. Operates on a shallow copy so the original
    dict is never mutated (matters in retry loops).

    Resolution order per key:
      1. Exact match in _KEY_ALIASES.
      2. Fuzzy match against _CANONICAL_FIELDS (catches aliases we
         haven't explicitly listed yet, e.g. "answer_text").
      3. Pass through unchanged.

    Unknown keys are passed through untouched — Pydantic will
    ignore them (extra="ignore" is the default) rather than failing.
    """
    out = {}
    for k, v in raw.items():
        canonical = _KEY_ALIASES.get(k)
        if canonical is None:
            matches = difflib.get_close_matches(
                k, _CANONICAL_FIELDS, n=1, cutoff=_FUZZY_MATCH_CUTOFF
            )
            canonical = matches[0] if matches else k
        if canonical not in out:
            out[canonical] = v

    if "type" in out and isinstance(out["type"], str):
        out["type"] = _normalize_type_value(out["type"])

    if "difficulty" in out and isinstance(out["difficulty"], str):
        out["difficulty"] = _normalize_difficulty_value(out["difficulty"])

    return out


# ---------------------------------------------------------------------------
# Value normalizers for `type` and `difficulty`
#
# Separate problem from key-name drift above: here the *key* is right
# (the model did send "type" / "difficulty"), but the *value* doesn't
# match the Literal exactly — wrong case ("mcq" instead of "MCQ") or a
# snake_case variant of a multi-word type ("fill_in_the_blank" instead
# of "Fill in the Blank"). Both are semantically correct, just
# formatted differently, so they're worth normalizing rather than
# rejecting the whole question over a casing mismatch.
# ---------------------------------------------------------------------------

_TYPE_VALUE_ALIASES: dict[str, str] = {
    # snake_case / lowercase variants -> canonical Literal value.
    # Keys here are lowercased and have spaces/hyphens collapsed to
    # underscores before lookup (see _normalize_type_value), so e.g.
    # "Fill-in-the-Blank", "fill in the blank", and "FILL_IN_THE_BLANK"
    # all resolve the same way.
    "mcq":                  "MCQ",
    "true_false":           "True/False",
    "true/false":           "True/False",
    "fill_in_the_blank":    "Fill in the Blank",
    "short_answer":         "Short Answer",
    "long_answer":          "Long Answer",
    "conceptual":           "Conceptual",
    "application":          "Application",
    "code_tracing":         "Code Tracing",
    "complexity":           "Complexity",
    "scenario":             "Scenario",
}

_DIFFICULTY_VALUE_ALIASES: dict[str, str] = {
    "easy":   "Easy",
    "medium": "Medium",
    "hard":   "Hard",
}


def _normalize_type_value(value: str) -> str:
    """Map case/punctuation variants of a question type to the exact
    Literal string Question expects. Falls through unchanged if no
    match is found, so Pydantic's own error still fires (and still
    gets logged) for values that are genuinely unrecognized rather
    than just differently formatted."""
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _TYPE_VALUE_ALIASES.get(key, value)


def _normalize_difficulty_value(value: str) -> str:
    """Same idea as _normalize_type_value, for difficulty."""
    key = value.strip().lower()
    return _DIFFICULTY_VALUE_ALIASES.get(key, value)


# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------

def load_llm():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found.")
    return genai.Client(api_key=api_key)


client = load_llm()


# ---------------------------------------------------------------------------
# Load chapter notes
# ---------------------------------------------------------------------------

def load_chapter_notes(notes_dir):
    notes_dir = Path(notes_dir)
    chapter_files = sorted(
        notes_dir.glob("chapter_*.md"),
        key=lambda p: int(p.stem.split("_")[1]),
    )
    chapters = []
    for file_path in chapter_files:
        with open(file_path, "r", encoding="utf-8") as f:
            markdown = f.read()
        chapter_id = int(file_path.stem.split("_")[1])
        chapters.append({"chapter_id": chapter_id, "markdown": markdown})
    logger.info(f"Loaded {len(chapters)} chapter note files.")
    return chapters


def extract_chapter_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    logger.warning(f"No H1 title found, using fallback '{fallback}'.")
    return fallback


# ---------------------------------------------------------------------------
# Build prompt
# ---------------------------------------------------------------------------

def build_prompt(chapter_id: int, chapter_title: str, chapter_markdown: str) -> str:
    return ASSESSMENT_PROMPT.format(
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        chapter_markdown=chapter_markdown,
    )


# ---------------------------------------------------------------------------
# Parse and validate questions from raw text
# ---------------------------------------------------------------------------

def _parse_questions(raw_text: str, chapter_id: int) -> list[Question]:
    """
    1. Strip markdown fences (free-form generation, so the model may
       wrap its JSON in ```json ... ``` despite being asked not to).
    2. JSON-parse the {"questions": [...]} envelope.
    3. Normalize each question dict's keys via _normalize_question().
    4. Attempt Question(**data) — skip invalid questions with a warning.
    5. Raise ValueError if accepted count is outside [MIN, MAX].
    """

    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(
            f"Chapter {chapter_id}: JSON parse failed. "
            f"Raw response preview (first 500 chars):\n{raw_text[:500]}"
        )
        raise ValueError(f"JSON parse failed: {e}") from e

    raw_questions = data.get("questions")
    if raw_questions is None:
        logger.error(
            f"Chapter {chapter_id}: 'questions' key missing. "
            f"Top-level keys returned: {list(data.keys())}"
        )
        raise ValueError('Response JSON missing "questions" key.')

    accepted: list[Question] = []
    skipped = 0

    for i, raw_q in enumerate(raw_questions):
        normalized = _normalize_question(raw_q, i)
        normalized["chapter_id"] = chapter_id  # always re-stamp

        try:
            accepted.append(Question(**normalized))
        except (ValidationError, TypeError) as e:
            skipped += 1
            if skipped == 1:
                logger.warning(
                    f"Chapter {chapter_id}: first skipped question has "
                    f"keys: {list(raw_q.keys())} — add missing ones to "
                    f"_KEY_ALIASES if they map to known fields."
                )
            logger.warning(
                f"Chapter {chapter_id}: skipping question index {i} "
                f"(failed validation after normalization): {e}"
            )

    if skipped:
        logger.warning(
            f"Chapter {chapter_id}: {skipped} skipped, {len(accepted)} accepted."
        )

    count = len(accepted)
    if not (MIN_QUESTIONS_PER_CHAPTER <= count <= MAX_QUESTIONS_PER_CHAPTER):
        raise ValueError(
            f"Chapter {chapter_id}: {count} valid questions — "
            f"outside [{MIN_QUESTIONS_PER_CHAPTER}, {MAX_QUESTIONS_PER_CHAPTER}]."
        )

    return accepted


# ---------------------------------------------------------------------------
# Generate chapter questions
# ---------------------------------------------------------------------------

def generate_chapter_questions(
    chapter_id: int, chapter_title: str, chapter_markdown: str
) -> list[Question]:

    base_prompt = build_prompt(chapter_id, chapter_title, chapter_markdown)
    last_error: str | None = None

    for attempt in range(MAX_RETRIES):
        # On retry, append what went wrong last time so the model gets
        # a chance to actually fix it, instead of repeating the same
        # prompt and hoping for a different random outcome.
        if last_error is None:
            prompt = base_prompt
        else:
            prompt = (
                f"{base_prompt}\n\n"
                f"# Your previous attempt failed\n\n"
                f"Your last response was rejected. The specific reason "
                f"was:\n\n{last_error}\n\n"
                f"Produce the response again from scratch, making sure "
                f"this specific problem does not happen again — pay "
                f"particular attention to valid JSON string escaping "
                f"(no raw backslashes, no LaTeX) and to matching every "
                f"field name and value exactly as specified above."
            )

        logger.info(
            f"Chapter {chapter_id}: attempt {attempt + 1}/{MAX_RETRIES} "
            f"(prompt: {len(prompt)} chars)"
        )

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                ),
            )

            questions = _parse_questions(response.text, chapter_id)
            logger.info(
                f"Chapter {chapter_id}: {len(questions)} validated questions."
            )
            return questions

        except (ValueError, json.JSONDecodeError) as e:
            last_error = str(e)
            wait = 5 * (attempt + 1)
            logger.warning(
                f"Chapter {chapter_id} attempt {attempt + 1} invalid output "
                f"(retrying in {wait}s): {e}"
            )
            time.sleep(wait)

        except Exception as e:
            last_error = str(e)
            wait = 5 * (attempt + 1)
            logger.warning(
                f"Chapter {chapter_id} attempt {attempt + 1} API error "
                f"(retrying in {wait}s): {e}"
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Chapter {chapter_id}: failed after {MAX_RETRIES} attempts."
    )


# ---------------------------------------------------------------------------
# Save / process / combine / main  (unchanged from previous version)
# ---------------------------------------------------------------------------

def save_chapter_questions(chapter_id: int, questions: list[Question]):
    output_path = ASSESSMENT_DIR / f"assessment_chapter_{chapter_id}.json"
    payload = [q.model_dump() for q in questions]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved: {output_path}")


def process_chapter(chapter: dict):
    chapter_id = chapter["chapter_id"]
    markdown = chapter["markdown"]
    output_path = ASSESSMENT_DIR / f"assessment_chapter_{chapter_id}.json"

    if output_path.exists():
        logger.info(f"Skipping chapter {chapter_id} (already exists).")
        return

    logger.info(f"Starting chapter {chapter_id}.")
    chapter_title = extract_chapter_title(markdown, fallback=f"Chapter {chapter_id}")
    questions = generate_chapter_questions(chapter_id, chapter_title, markdown)
    save_chapter_questions(chapter_id, questions)
    logger.info(f"Finished chapter {chapter_id}.")


def combine_assessment(lecture_title: str) -> Assessment:
    chapter_files = sorted(
        ASSESSMENT_DIR.glob("assessment_chapter_*.json"),
        key=lambda p: int(p.stem.split("_")[-1]),
    )

    all_questions = []
    for file_path in chapter_files:
        with open(file_path, "r", encoding="utf-8") as f:
            all_questions.extend(json.load(f))

    total_questions = len(all_questions)
    total_chapters = len(chapter_files)
    estimated_time = round(total_questions * MINUTES_PER_QUESTION)

    metadata = AssessmentMetadata(
        lecture_title=lecture_title,
        total_chapters=total_chapters,
        total_questions=total_questions,
        estimated_time=estimated_time,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    assessment = Assessment(metadata=metadata, questions=all_questions)

    output_path = ASSESSMENT_DIR / "assessment.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(assessment.model_dump_json(indent=2))

    logger.info(
        f"Saved: {output_path} "
        f"({total_questions} questions across {total_chapters} chapters)"
    )
    return assessment


def main(lecture_title: str | None = None):
    logger.info(f"Using model: {MODEL_NAME}")
    ASSESSMENT_DIR.mkdir(parents=True, exist_ok=True)

    if lecture_title is None:
        outline_path = NOTES_DIR / "lecture_outline.json"
        if outline_path.exists():
            with open(outline_path, "r", encoding="utf-8") as f:
                outline = json.load(f)
            lecture_title = outline.get("lecture_title", "Untitled Lecture")
        else:
            lecture_title = "Untitled Lecture"
            logger.warning("No lecture_title provided and outline not found.")

    chapters = load_chapter_notes(NOTES_DIR)
    if not chapters:
        raise RuntimeError(
            f"No chapter_*.md files found in {NOTES_DIR}. "
            "Run notes_generator.py first."
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_chapter, ch) for ch in chapters]
        completed, total = 0, len(futures)
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Chapter failed: {e}")
            completed += 1
            logger.info(f"Progress: {completed}/{total}")

    combine_assessment(lecture_title)
    logger.info("Assessment generation complete.")

    from assessment.assessment_pdf_builder import build_assessment_pdf

    build_assessment_pdf(
        assessment_path="outputs/assessment/assessment.json",
        output_path="outputs/assessment/assessment.pdf",
    )


if __name__ == "__main__":
    main()