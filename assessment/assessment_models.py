"""
assessment_models.py

Pydantic models for the assessment engine.

Design notes (see conversation for full rationale):

- Question is a single flat model, not a discriminated union per
  question type. This keeps the JSON schema simple for the LLM to
  target via structured output, and keeps every downstream consumer
  (PDF builder, future renderer, future grading logic) able to loop
  over `Assessment.questions` without type-narrowing.

  The cost of "flat" is that nothing *structurally* prevents an MCQ
  from having zero options, or a Short Answer question from having
  options it shouldn't. That's handled instead by the validator below
  — invalid combinations raise at parse time rather than silently
  reaching the PDF builder.

- QUESTION_TYPES is intentionally generic (not biology/history/CS
  specific). Subject-specific framing ("Diagram Question", "Chronology",
  etc.) is a *prompting* concern — the prompt asks the model to pick
  the most relevant generic type and phrase the question in
  subject-appropriate language. Adding a new literal type here is a
  one-line change if a type proves genuinely structurally different
  later (e.g. needs its own field), not a sign the union should split.

- Difficulty and total question count are intentionally NOT enforced
  to match any fixed distribution. The prompt is given the 8-10/chapter
  guidance and an example distribution as *guidance text*, and the
  model here only validates that what comes back is well-formed:
  known type, known difficulty, options present iff required, and a
  sane total count. This matches the "assess understanding, don't
  hit a quota" prompt philosophy — see assessment_prompts.py.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

# Generic across subjects. Subject flavour (e.g. "Diagram Question" for
# Biology, "Chronology" for History) is handled by phrasing within these
# generic buckets, not by adding subject-specific literals here.
QuestionType = Literal[
    "MCQ",
    "True/False",
    "Fill in the Blank",
    "Short Answer",
    "Long Answer",
    "Conceptual",
    "Application",
    "Code Tracing",
    "Complexity",
    "Scenario",
]

Difficulty = Literal["Easy", "Medium", "Hard"]

# Question types that require a populated `options` list.
_OPTION_REQUIRED_TYPES = {"MCQ", "True/False"}

# Sane bounds for total question count, used to catch a generation
# gone wrong (e.g. truncated output, or the model ignoring guidance
# entirely) without hardcoding an exact expected count.
MIN_QUESTIONS_PER_CHAPTER = 4
MAX_QUESTIONS_PER_CHAPTER = 15


# ---------------------------------------------------------------------------
# Question
# ---------------------------------------------------------------------------

class Question(BaseModel):
    """
    A single assessment question.

    `options` is only meaningful for MCQ and True/False questions.
    For True/False it should be exactly ["True", "False"] (or the
    equivalent in whatever phrasing the prompt settles on) — for MCQ
    it should have at least two entries, one of which matches `answer`.
    For every other type, `options` must be empty: the answer is free
    text, graded against `answer` and `explanation`, not selected from
    a list.
    """

    question_id: int

    chapter_id: int

    type: QuestionType

    difficulty: Difficulty

    concepts: list[str] = Field(
        description=(
            "Short tags naming the specific idea(s) this question "
            "probes, e.g. ['Partial Overlap']. Used later for "
            "weak-concept tracking and targeted regeneration."
        ),
    )

    question: str

    options: list[str] = Field(default_factory=list)

    answer: str

    explanation: str = ""

    @model_validator(mode="after")
    def _validate_options_for_type(self) -> "Question":
        requires_options = self.type in _OPTION_REQUIRED_TYPES

        if requires_options and len(self.options) < 2:
            raise ValueError(
                f"question_id={self.question_id} has type "
                f"'{self.type}', which requires at least 2 options, "
                f"but got {len(self.options)}."
            )

        if not requires_options and self.options:
            raise ValueError(
                f"question_id={self.question_id} has type "
                f"'{self.type}', which should not have options, "
                f"but got {len(self.options)}."
            )

        if requires_options and self.answer not in self.options:
            raise ValueError(
                f"question_id={self.question_id}: answer "
                f"{self.answer!r} is not among its own options "
                f"{self.options!r}."
            )

        return self


# ---------------------------------------------------------------------------
# Assessment metadata
# ---------------------------------------------------------------------------

class AssessmentMetadata(BaseModel):
    """
    Metadata describing a generated assessment.

    Field names intentionally mirror RevisionMetadata
    (lecture_title, total_chapters, generated_at) for consistency
    across the notes / revision / assessment pipelines.
    """

    lecture_title: str

    total_chapters: int

    total_questions: int

    estimated_time: int  # minutes

    generated_at: str

    @model_validator(mode="after")
    def _check_generated_at_is_iso(self) -> "AssessmentMetadata":
        try:
            datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"generated_at {self.generated_at!r} is not a valid "
                f"ISO 8601 timestamp."
            ) from exc
        return self


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

class Assessment(BaseModel):
    """
    A complete generated assessment: metadata + every question across
    every chapter of one lecture.
    """

    metadata: AssessmentMetadata

    questions: list[Question]

    @model_validator(mode="after")
    def _check_counts_and_ids(self) -> "Assessment":
        n = len(self.questions)

        if self.metadata.total_questions != n:
            raise ValueError(
                f"metadata.total_questions={self.metadata.total_questions} "
                f"does not match len(questions)={n}."
            )

        # question_id is only required to be unique WITHIN a chapter
        # (chapters are generated independently, each starting its own
        # ids at 1 — see assessment_prompts.py). So uniqueness is
        # checked on the (chapter_id, question_id) pair, not on
        # question_id alone, which would always collide across more
        # than one chapter.
        pairs = [(q.chapter_id, q.question_id) for q in self.questions]
        if len(pairs) != len(set(pairs)):
            dupes = sorted({p for p in pairs if pairs.count(p) > 1})
            raise ValueError(
                f"Duplicate (chapter_id, question_id) pairs: {dupes}"
            )

        chapters_seen = sorted({q.chapter_id for q in self.questions})
        for chapter_id in chapters_seen:
            count = sum(
                1 for q in self.questions if q.chapter_id == chapter_id
            )
            if not (
                MIN_QUESTIONS_PER_CHAPTER
                <= count
                <= MAX_QUESTIONS_PER_CHAPTER
            ):
                raise ValueError(
                    f"chapter_id={chapter_id} has {count} questions, "
                    f"outside the expected "
                    f"[{MIN_QUESTIONS_PER_CHAPTER}, "
                    f"{MAX_QUESTIONS_PER_CHAPTER}] range. This usually "
                    f"means generation was truncated or the prompt's "
                    f"per-chapter guidance was ignored."
                )

        return self

    def questions_for_chapter(self, chapter_id: int) -> list[Question]:
        """Convenience accessor — used by the PDF builder and, later,
        by per-chapter practice test generation."""
        return [q for q in self.questions if q.chapter_id == chapter_id]

    def by_difficulty(self, difficulty: Difficulty) -> list[Question]:
        """Convenience accessor for difficulty-filtered practice sets."""
        return [q for q in self.questions if q.difficulty == difficulty]