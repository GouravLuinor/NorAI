#!/usr/bin/env python3
"""
generate_flashcards.py

One‑shot script: reads all assessment questions, splits them into batches,
and processes them in parallel across chapters using a fixed pool of workers.

Internal defaults:
    WORKERS = 7               (parallel API calls)
    MAX_CARDS_PER_CHAPTER = 0  (0 = no limit, use all questions)
    BATCH_SIZE = 5             (questions per LLM call)

Usage:
    python -m flashcards.generate_flashcards
    python -m flashcards.generate_flashcards --chapter 1
    python -m flashcards.generate_flashcards --max-cards 15   # override cap
    python -m flashcards.generate_flashcards --workers 10     # more parallel
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tutor.config import MODEL_NAME, TEMPERATURE, get_api_key

ASSESSMENT_DIR = Path("outputs/assessment")
FLASHCARDS_DIR = Path("outputs/flashcards")
FLASHCARDS_DIR.mkdir(parents=True, exist_ok=True)

# ── Internal defaults ─────────────────────────────────────────────────────────
DEFAULT_WORKERS = 7
DEFAULT_MAX_CARDS = 0          # 0 = no limit, process all questions
BATCH_SIZE = 5                 # questions per LLM call

PROMPT_TEMPLATE = """You are an expert flashcard creator. Convert the following assessment questions into concise flashcards.

For each flashcard:
- The "front" must be a very short, self‑contained question (max 15 words).
- The "back" must be a short, precise answer (max 20 words).
- Include a brief "explanation" (max 30 words) that clarifies the answer.

Return ONLY a JSON array of objects with the fields "front", "back", "explanation".
Do NOT include any other text.

Assessment questions:
{questions_text}"""


def load_assessment_questions(chapter_id: int | None = None) -> List[Dict[str, Any]]:
    """Load assessment questions from the file system."""
    if chapter_id is not None:
        path = ASSESSMENT_DIR / f"assessment_chapter_{chapter_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return []

    combined = ASSESSMENT_DIR / "assessment.json"
    if combined.exists():
        return json.loads(combined.read_text(encoding="utf-8"))

    questions = []
    for f in sorted(ASSESSMENT_DIR.glob("assessment_chapter_*.json")):
        questions.extend(json.loads(f.read_text(encoding="utf-8")))
    return questions


def convert_assessment_to_flashcards(questions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Deterministic 0-call transform converting assessment questions directly into flashcards.
    Uses flashcard_front, flashcard_back, flashcard_explanation if present, or falls back
    to question, answer, explanation.
    """
    cards = []
    for q in questions:
        front = q.get("flashcard_front") or q.get("question", "")
        back = q.get("flashcard_back") or q.get("answer", "")
        explanation = q.get("flashcard_explanation") or q.get("explanation", "")

        front_words = front.split()
        if len(front_words) > 15:
            front = " ".join(front_words[:15]) + "..."

        back_words = back.split()
        if len(back_words) > 20:
            back = " ".join(back_words[:20]) + "..."

        explanation_words = explanation.split()
        if len(explanation_words) > 30:
            explanation = " ".join(explanation_words[:30]) + "..."

        cards.append({
            "front": front,
            "back": back,
            "explanation": explanation
        })
    return cards


def main(chapter=None, max_cards=DEFAULT_MAX_CARDS, workers=DEFAULT_WORKERS):
    if chapter is not None:
        chapters = [chapter]
    else:
        chapters = sorted({
            int(f.stem.split('_')[-1])
            for f in ASSESSMENT_DIR.glob("assessment_chapter_*.json")
        })

    total_cards = []
    for ch in chapters:
        questions = load_assessment_questions(ch)
        if not questions:
            print(f"  No assessment data for chapter {ch}, skipping.")
            continue

        if max_cards > 0 and len(questions) > max_cards:
            import random
            questions = random.sample(questions, max_cards)

        cards = convert_assessment_to_flashcards(questions)
        total_cards.extend(cards)

        out_path = FLASHCARDS_DIR / f"flashcards_chapter_{ch}.json"
        out_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Chapter {ch}: {len(cards)} flashcards created (0 API calls) -> {out_path}")

    combined_path = FLASHCARDS_DIR / "flashcards.json"
    combined_path.write_text(json.dumps(total_cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Combined flashcards ({len(total_cards)} cards) written to {combined_path}")
    print("Done.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default="outputs")
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--max-cards", type=int, default=DEFAULT_MAX_CARDS)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    args = parser.parse_args()

    from pathlib import Path
    import flashcards.generate_flashcards as fg
    fg.ASSESSMENT_DIR = Path(args.output_dir) / "assessment"
    fg.FLASHCARDS_DIR = Path(args.output_dir) / "flashcards"
    fg.FLASHCARDS_DIR.mkdir(parents=True, exist_ok=True)

    main(chapter=args.chapter, max_cards=args.max_cards, workers=args.workers)