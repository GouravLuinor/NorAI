"""Callable tools for the NorAI tutor."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

FLASHCARD_COUNT = 5
ASSESSMENT_GLOB = "outputs/assessment/assessment_chapter_*.json"
COMBINED_ASSESSMENT = "outputs/assessment/assessment.json"


def start_quiz(chapter_id: Optional[int] = None) -> dict:
    """Prepare a quiz – sets state, the existing quiz loop takes over."""
    questions = _load_questions(chapter_id)
    if not questions:
        return {"error": "No questions found for this chapter."}

    if len(questions) > FLASHCARD_COUNT:
        questions = random.sample(questions, FLASHCARD_COUNT)

    return {
        "quiz_active": True,
        "quiz_questions": questions,
        "quiz_total": len(questions),
        "quiz_index": 0,
        "quiz_score": 0,
        "quiz_awaiting_answer": False,
        "quiz_answers": [],
        "quiz_chapter_id": chapter_id,
    }


def show_summary(chapter_id: int) -> str:
    """Return the pre‑made revision summary for a chapter."""
    path = Path(f"outputs/revision/revision_chapter_{chapter_id}.md")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"No summary available for chapter {chapter_id}."


def show_flashcards(chapter_id: Optional[int] = None) -> str:
    """Generate a set of flashcards from assessment data."""
    questions = _load_questions(chapter_id)
    if not questions:
        return "I couldn't find any questions to make flashcards from."

    if len(questions) > FLASHCARD_COUNT:
        questions = random.sample(questions, FLASHCARD_COUNT)

    lines = ["**Flashcards**\n"]
    for i, q in enumerate(questions, 1):
        lines.append(f"**Q{i}:** {q['question']}")
        lines.append(f"**A:** {q.get('answer', '')}")
        if q.get("explanation"):
            lines.append(f"*({q['explanation']})*")
        lines.append("")
    return "\n".join(lines)


def _load_questions(chapter_id: Optional[int]) -> list[dict]:
    """Load assessment questions, optionally filtered by chapter."""
    if chapter_id is not None:
        path = Path(f"outputs/assessment/assessment_chapter_{chapter_id}.json")
        if path.exists():
            with open(path) as f:
                return json.load(f)
    combined = Path(COMBINED_ASSESSMENT)
    if combined.exists():
        with open(combined) as f:
            all_qs = json.load(f)
        if chapter_id is not None:
            return [q for q in all_qs if q.get("chapter_id") == chapter_id]
        return all_qs
    return []