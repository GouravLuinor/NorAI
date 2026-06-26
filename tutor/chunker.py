"""
chunker.py — Chunk study-note Markdown files by heading hierarchy.

Strategy (locked in Phase 3 design):
  • Split at the smallest heading level present in the file (ATX-style: # … ######).
  • If a section has no sub-headings, use the section's own heading level.
  • Each chunk carries a `heading_path` metadata field — e.g.
      "Detailed Explanation > Leaf Nodes"
    built by walking from the root heading down to the chunk's own heading.
  • Chapter ID and source file path are also stored as metadata for filtering.

Why not LangChain's MarkdownHeaderTextSplitter?
  It splits at every heading level simultaneously, producing chunks at multiple
  granularities that would overlap. We want exactly one chunk per logical section
  at the finest grain — the heading tree's leaves.

Output schema (one dict per chunk):
    {
        "text":         str,          # chunk body, heading line stripped out
        "heading":      str,          # the chunk's own heading text
        "heading_path": str,          # e.g. "Parent > Child > This Heading"
        "level":        int,          # ATX heading depth (1=H1 … 6=H6)
        "chapter_id":   int | None,   # parsed from filename chapter_N.md
        "source":       str,          # absolute path to source .md file
    }
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator


# ── Internal types ─────────────────────────────────────────────────────────────

class _Section:
    """Raw section from a single pass over the file."""
    def __init__(self, level: int, heading: str, body: str) -> None:
        self.level = level
        self.heading = heading
        self.body = body.strip()


# ── Helpers ────────────────────────────────────────────────────────────────────

_ATX_RE = re.compile(r'^(#{1,6})\s+(.*)')


def _parse_chapter_id(path: Path) -> int | None:
    """Extract N from 'chapter_N.md', or return None."""
    m = re.match(r'chapter_(\d+)', path.stem)
    return int(m.group(1)) if m else None


def _parse_sections(lines: list[str]) -> list[_Section]:
    """
    Linear pass: split on ATX headings (# … ######), preserving body text.
    Returns sections in document order.
    """
    sections: list[_Section] = []
    current_level: int | None = None
    current_heading = ""
    current_body: list[str] = []

    def flush():
        if current_level is not None:
            sections.append(_Section(current_level, current_heading, "\n".join(current_body)))

    for line in lines:
        m = _ATX_RE.match(line)
        if m:
            flush()
            current_level = len(m.group(1))
            current_heading = m.group(2).strip()
            current_body = []
        else:
            current_body.append(line.rstrip())

    flush()
    return sections


def _build_heading_path(stack: list[_Section], current: _Section) -> str:
    """
    Build a breadcrumb path from the ancestor stack down to `current`.
    E.g. ["Introduction", "Key Concepts"] + "Leaf Nodes"
      → "Introduction > Key Concepts > Leaf Nodes"
    """
    parts = [s.heading for s in stack] + [current.heading]
    return " > ".join(parts)


def _find_min_level(sections: list[_Section]) -> int:
    """Smallest heading level present (most deeply nested)."""
    return max(s.level for s in sections) if sections else 1


def _iter_leaf_chunks(
    sections: list[_Section],
    min_level: int,
    ancestor_stack: list[_Section],
    source: str,
    chapter_id: int | None,
) -> Iterator[dict]:
    """
    Recursively decide which sections are leaves:
    - A section is a leaf if no child section exists at a deeper level in the
      contiguous run that follows it.
    - A section at `min_level` is always a leaf.
    Yields chunk dicts.
    """
    i = 0
    while i < len(sections):
        sec = sections[i]

        # Collect everything directly under this section (deeper level)
        children = []
        j = i + 1
        while j < len(sections) and sections[j].level > sec.level:
            children.append(sections[j])
            j += 1

        new_stack = ancestor_stack + [sec]

        if not children or sec.level == min_level:
            # Leaf: emit this chunk (with its own body)
            heading_path = _build_heading_path(ancestor_stack, sec)
            yield {
                "text": sec.body,
                "heading": sec.heading,
                "heading_path": heading_path,
                "level": sec.level,
                "chapter_id": chapter_id,
                "source": source,
            }
        else:
            # Non-leaf: emit a chunk for its own body if non-empty,
            # then recurse into children.
            if sec.body:
                heading_path = _build_heading_path(ancestor_stack, sec)
                yield {
                    "text": sec.body,
                    "heading": sec.heading,
                    "heading_path": heading_path,
                    "level": sec.level,
                    "chapter_id": chapter_id,
                    "source": source,
                }
            yield from _iter_leaf_chunks(children, min_level, new_stack, source, chapter_id)

        i = j


# ── Public API ─────────────────────────────────────────────────────────────────

def chunk_file(path: Path) -> list[dict]:
    """
    Parse one study-note Markdown file and return a list of chunk dicts.
    Returns [] if the file has no headings or is empty.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections = _parse_sections(lines)

    if not sections:
        return []

    min_level = _find_min_level(sections)
    chapter_id = _parse_chapter_id(path)
    source = str(path.resolve())

    # Group top-level sections (find the coarsest level present)
    root_level = min(s.level for s in sections)

    # Split into top-level trees
    chunks = []
    root_sections: list[_Section] = []
    for s in sections:
        if s.level == root_level:
            if root_sections:
                chunks.extend(
                    _iter_leaf_chunks(root_sections, min_level, [], source, chapter_id)
                )
            root_sections = [s]
        else:
            root_sections.append(s)

    if root_sections:
        chunks.extend(
            _iter_leaf_chunks(root_sections, min_level, [], source, chapter_id)
        )

    # Drop empty-body chunks (headings with no content)
    return [c for c in chunks if c["text"].strip()]


def chunk_glob(pattern: str) -> list[dict]:
    """
    Chunk all files matching a glob pattern (e.g. "outputs/notes/chapter_*.md").
    Returns all chunks across all files, sorted by chapter_id then file order.
    """
    from glob import glob
    paths = sorted(glob(pattern))
    all_chunks: list[dict] = []
    for p in paths:
        all_chunks.extend(chunk_file(Path(p)))
    return all_chunks