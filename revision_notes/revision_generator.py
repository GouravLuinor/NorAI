"""
revision_generator.py

The LLM-based per-chapter revision generator was replaced by the consolidated
chapter-artifact stage (notes/notes_generator.process_chapter_artifacts_merged),
which produces structured revision summaries in one call. What survives here is
the pure-markdown bridge that renders those structured summaries into the
revision chapter files. Everything else in this module was dead code and was
deleted (see ROADMAP P1.5).
"""

import logging

logger = logging.getLogger(__name__)


def render_revision_markdown(
    chapter_id: int,
    chapter_title: str,
    revision_summary: list[str],
    core_concepts_breakdown: list,
) -> str:
    """Bridge structured JSON revision outputs into standard Markdown format."""
    lines = [
        f"# Revision Notes — Chapter {chapter_id}: {chapter_title}\n",
        "## Key Exam Takeaways\n",
    ]
    for bullet in revision_summary:
        lines.append(f"- {bullet}")

    lines.append("\n## Core Concepts Breakdown\n")
    for item in core_concepts_breakdown:
        if isinstance(item, dict):
            concept = item.get("concept", "")
            explanation = item.get("explanation", "")
        else:
            concept = getattr(item, "concept", "")
            explanation = getattr(item, "explanation", "")
        lines.append(f"- **{concept}**: {explanation}")

    return "\n".join(lines)
