"""
context_expand.py — P3.4: pull parent-section + sibling context around a
retrieved leaf chunk.

Hits in the Chroma index are atomic leaf chunks. When a leaf is a strong match,
the answer benefits from its surrounding section: the parent heading, the parent
body (if the parent carries its own prose), and the sibling leaves under the same
parent. This module reads the chunk's source notes .md at QUERY TIME and slices
that context out — no Chroma re-embed, no index rebuild, no API cost.

Only the surrounding text is added; the chunk's own heading_path / distance /
relevance metadata are untouched. The expanded text is attached to the chunk as
`context` by retriever.retrieve().
"""

from __future__ import annotations

import logging
from pathlib import Path

from tutor.chunker import _build_heading_path, _parse_sections
from tutor.retrieval_config import MAX_CONTEXT_CHARS

logger = logging.getLogger(__name__)


def _heading_paths(sections):
    """Yield (heading_path, section) for every section using the same
    ancestor-stack breadcrumbs as the chunker."""
    stack: list = []
    for sec in sections:
        while stack and sec.level <= stack[-1].level:
            stack.pop()
        path = _build_heading_path(stack, sec)
        stack.append(sec)
        yield path, sec


def _build_section_block(section) -> str:
    parts = [f"{'#' * section.level} {section.heading}"]
    if section.body.strip():
        parts.append(section.body.strip())
    return "\n\n".join(parts)


def expand_context(chunk: dict, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Return the parent-section + sibling context for a retrieved chunk, capped at
    `max_chars`. Returns "" when the source file is unreadable, the section
    can't be located, or the chunk is a top-level section (no parent to expand).
    """
    source = chunk.get("source") or ""
    if not source:
        return ""

    try:
        lines = Path(source).read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        logger.debug(f"context_expand: cannot read {source}: {exc}")
        return ""

    sections = _parse_sections(lines)
    if not sections:
        return ""

    paths = [p for p, _ in _heading_paths(sections)]
    target_path = chunk.get("heading_path") or chunk.get("heading") or ""

    # Pass 1: exact breadcrumb match (the normal case).
    target_idx = paths.index(target_path) if target_path in paths else -1
    if target_idx < 0:
        # Pass 2: first section whose heading equals the chunk's leaf heading.
        leaf = chunk.get("heading")
        for i, sec in enumerate(sections):
            if leaf and sec.heading == leaf:
                target_idx = i
                break
    if target_idx < 0:
        # Pass 3: breadcrumb suffix match (survives normalisation differences).
        for i, p in enumerate(paths):
            if target_path and p.endswith(target_path):
                target_idx = i
                break
    if target_idx < 0:
        return ""

    target_sec = sections[target_idx]

    # Parent = nearest preceding section with a shallower heading level.
    parent_idx = -1
    for j in range(target_idx - 1, -1, -1):
        if sections[j].level < target_sec.level:
            parent_idx = j
            break
    if parent_idx < 0:
        return ""  # top-level chunk, nothing to expand

    parent_sec = sections[parent_idx]
    parts = [_build_section_block(parent_sec)]
    for j in range(parent_idx + 1, len(sections)):
        sec = sections[j]
        if sec.level <= parent_sec.level:
            break
        if sec.level == parent_sec.level + 1:
            parts.append(_build_section_block(sec))
        if len("\n\n".join(parts)) >= max_chars:
            break

    block = "\n\n".join(parts).strip()
    if len(block) > max_chars:
        block = block[:max_chars].rsplit(" ", 1)[0] + "…"
    return block
