"""
revision_generator.py

Renders a chapter's structured revision summary (from lean/chapters.py's one
call per chapter) into its revision markdown file.
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
