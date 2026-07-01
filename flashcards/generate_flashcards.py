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


def build_prompt(questions: List[Dict[str, Any]]) -> str:
    """Create a prompt for a batch of questions."""
    lines = []
    for q in questions:
        lines.append(f"Q: {q.get('question', '')}")
        lines.append(f"A: {q.get('answer', '')}")
        explanation = q.get('explanation', '')
        if explanation:
            lines.append(f"Explanation: {explanation}")
        lines.append("")
    return PROMPT_TEMPLATE.format(questions_text="\n".join(lines))


def generate_flashcards_batch(batch: Tuple[int, int, List[Dict[str, Any]]]) -> Tuple[int, int, List[Dict[str, str]]]:
    """Call the LLM for a single batch. Returns (chapter_id, batch_index, cards)."""
    chapter_id, batch_idx, questions = batch
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0.3,
        google_api_key=get_api_key(),
    )
    prompt = build_prompt(questions)
    try:
        response = llm.invoke([
            SystemMessage(content="You are a helpful flashcard generator. Always respond with valid JSON."),
            HumanMessage(content=prompt),
        ])
        text = response.content
        if isinstance(text, list):
            text = " ".join(block.get("text", "") for block in text if isinstance(block, dict))
    except Exception as e:
        print(f"    Chapter {chapter_id} batch {batch_idx} LLM call failed: {e}")
        return (chapter_id, batch_idx, [])

    try:
        json_start = text.find('[')
        json_end = text.rfind(']') + 1
        if json_start != -1 and json_end > json_start:
            json_str = text[json_start:json_end]
            cards = json.loads(json_str)
            return (chapter_id, batch_idx, cards)
    except json.JSONDecodeError:
        pass

    return (chapter_id, batch_idx, [{"front": "Error", "back": "Could not generate flashcards", "explanation": text}])


def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from assessment data.")
    parser.add_argument("--chapter", type=int, default=None, help="Process a single chapter.")
    parser.add_argument("--max-cards", type=int, default=DEFAULT_MAX_CARDS,
                        help=f"Max cards per chapter (0 = all, default: {DEFAULT_MAX_CARDS}).")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Parallel API calls (default: {DEFAULT_WORKERS}).")
    args = parser.parse_args()

    if args.chapter is not None:
        chapters = [args.chapter]
    else:
        chapters = sorted({
            int(f.stem.split('_')[-1])
            for f in ASSESSMENT_DIR.glob("assessment_chapter_*.json")
        })

    # Collect all batches from all chapters
    all_batches: List[Tuple[int, int, List[Dict[str, Any]]]] = []
    chapter_question_counts = {}

    for ch in chapters:
        questions = load_assessment_questions(ch)
        if not questions:
            print(f"  No assessment data for chapter {ch}, skipping.")
            continue

        max_cards = args.max_cards
        if max_cards > 0 and len(questions) > max_cards:
            import random
            questions = random.sample(questions, max_cards)

        chapter_question_counts[ch] = len(questions)
        batches = [questions[i:i+BATCH_SIZE] for i in range(0, len(questions), BATCH_SIZE)]
        for idx, batch in enumerate(batches):
            all_batches.append((ch, idx + 1, batch))

    total_batches = len(all_batches)
    print(f"\nTotal batches across all chapters: {total_batches}")
    print(f"Using {args.workers} workers.\n")

    # Process all batches concurrently with a single pool
    all_cards_by_chapter: Dict[int, List[Dict[str, str]]] = {ch: [] for ch in chapters}

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(generate_flashcards_batch, b): b for b in all_batches}
        for future in as_completed(futures):
            ch, batch_idx, cards = future.result()
            all_cards_by_chapter[ch].extend(cards)
            print(f"  Chapter {ch} batch {batch_idx}: {len(cards)} cards")

    # Write per‑chapter files and combined file
    total_cards = []
    for ch in chapters:
        cards = all_cards_by_chapter.get(ch, [])
        total_cards.extend(cards)
        out_path = FLASHCARDS_DIR / f"flashcards_chapter_{ch}.json"
        out_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  Chapter {ch}: {len(cards)} cards written to {out_path}")

    combined_path = FLASHCARDS_DIR / "flashcards.json"
    combined_path.write_text(json.dumps(total_cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Combined flashcards ({len(total_cards)} cards) written to {combined_path}")
    print("Done.")


if __name__ == "__main__":
    main()