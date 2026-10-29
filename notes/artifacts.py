"""
notes/artifacts.py — write one chapter's study artifacts in the layout the API
and tutor read:

  notes/chapter_N.{md,json}, notes/notes.md
  revision/revision_chapter_N.md
  assessment/assessment_chapter_N.json
  flashcards/flashcards_chapter_N.json  (a 0-call transform of the quiz)

The content comes from lean/chapters.py (one multimodal call per chapter).
"""

import json
import logging
from pathlib import Path

from pydantic import BaseModel

from flashcards.generate_flashcards import convert_assessment_to_flashcards
from revision_notes.revision_generator import render_revision_markdown

logger = logging.getLogger(__name__)


class CoreConceptItem(BaseModel):
    concept: str
    explanation: str


def write_chapter_artifacts(
    output_dir: str,
    *,
    chapter_id: int,
    chapter_title: str,
    notes_title: str,
    sections: list[dict],
    revision_summary: list[str],
    core_concepts_breakdown: list,
    questions: list[dict],
) -> None:
    """Write one chapter's notes (.md + .json), revision, assessment and
    flashcard files in the layout the API and tutor read."""
    out = Path(output_dir)
    notes_dir, revision_dir = out / "notes", out / "revision"
    assessment_dir, flashcards_dir = out / "assessment", out / "flashcards"
    for d in (notes_dir, revision_dir, assessment_dir, flashcards_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Markdown for the RAG tutor and notes.md; JSON for deterministic card rendering.
    md_lines = [f"# {notes_title}\n"]
    for sec in sections:
        if sec.get("title"):
            md_lines.append(f"## {sec['title']}")
        md_lines.append(f"{sec.get('content_markdown', '')}\n")
    (notes_dir / f"chapter_{chapter_id}.md").write_text("\n\n".join(md_lines), encoding="utf-8")
    with open(notes_dir / f"chapter_{chapter_id}.json", "w", encoding="utf-8") as f:
        json.dump(
            {"chapter_id": chapter_id, "title": notes_title, "sections": sections},
            f, indent=4, ensure_ascii=False,
        )

    rev_md = render_revision_markdown(
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        revision_summary=revision_summary,
        core_concepts_breakdown=core_concepts_breakdown,
    )
    (revision_dir / f"revision_chapter_{chapter_id}.md").write_text(rev_md, encoding="utf-8")

    with open(assessment_dir / f"assessment_chapter_{chapter_id}.json", "w", encoding="utf-8") as f:
        json.dump(
            {"chapter_id": chapter_id, "chapter_title": chapter_title, "questions": questions},
            f, indent=4, ensure_ascii=False,
        )

    # Flashcards are a 0-call transformation of the quiz questions.
    with open(flashcards_dir / f"flashcards_chapter_{chapter_id}.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
                "flashcards": convert_assessment_to_flashcards(questions),
            },
            f, indent=4, ensure_ascii=False,
        )


def write_degraded_chapter(output_dir: str, chapter_id: int, chapter_title: str) -> None:
    """Placeholder files (incomplete: true) for a chapter whose generation failed."""
    out = Path(output_dir)
    for d in ("notes", "revision", "assessment", "flashcards"):
        (out / d).mkdir(parents=True, exist_ok=True)
    (out / "notes" / f"chapter_{chapter_id}.md").write_text(
        f"# Chapter {chapter_id}: {chapter_title}\n\n*Note: Content generation was partially degraded for this chapter.*",
        encoding="utf-8",
    )
    (out / "revision" / f"revision_chapter_{chapter_id}.md").write_text(
        f"# Revision Notes — Chapter {chapter_id}: {chapter_title}\n\n*Note: Content generation was partially degraded for this chapter.*",
        encoding="utf-8",
    )
    with open(out / "assessment" / f"assessment_chapter_{chapter_id}.json", "w", encoding="utf-8") as f:
        json.dump({"chapter_id": chapter_id, "chapter_title": chapter_title, "incomplete": True, "questions": []}, f, indent=4)
    with open(out / "flashcards" / f"flashcards_chapter_{chapter_id}.json", "w", encoding="utf-8") as f:
        json.dump({"chapter_id": chapter_id, "chapter_title": chapter_title, "incomplete": True, "flashcards": []}, f, indent=4)


def write_combined_notes(notes_dir: Path) -> Path:
    """Join every chapter_N.md under `notes_dir` into notes.md (chapter order)."""
    notes_dir = Path(notes_dir)
    files = sorted(notes_dir.glob("chapter_*.md"), key=lambda x: int(x.stem.split("_")[1]))
    output_path = notes_dir / "notes.md"
    output_path.write_text(
        "\n\n---\n\n".join(f.read_text(encoding="utf-8") for f in files),
        encoding="utf-8",
    )
    logger.info(f"Saved: {output_path}")
    return output_path
