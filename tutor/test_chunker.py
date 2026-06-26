"""
test_chunker.py — Unit tests for tutor/chunker.py.

No Chroma, no API calls, no google-genai. Fully runnable offline.

Run:
    python -m pytest tutor/test_chunker.py -v
    # or without pytest:
    python tutor/test_chunker.py
"""

import sys
import textwrap
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.chunker import chunk_file  # noqa: E402

import tempfile
import os


def _write_temp_md(content: str) -> Path:
    """Write content to a temporary .md file and return its Path."""
    fd, path = tempfile.mkstemp(suffix=".md", prefix="chapter_1_")
    with os.fdopen(fd, "w") as f:
        f.write(textwrap.dedent(content))
    return Path(path)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_flat_headings():
    """Single-level headings → each heading is a leaf chunk."""
    p = _write_temp_md("""\
        # Introduction
        This is the intro.

        # Methods
        Here are the methods.

        # Results
        Here are the results.
    """)
    try:
        chunks = chunk_file(p)
        assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"
        assert chunks[0]["heading"] == "Introduction"
        assert chunks[0]["heading_path"] == "Introduction"
        assert "intro" in chunks[0]["text"]
        print("PASS test_flat_headings")
    finally:
        p.unlink()


def test_nested_headings_only_leaves():
    """Nested headings → only leaf nodes emitted (not their parents)."""
    p = _write_temp_md("""\
        # Overview
        Overview text.

        ## Key Concepts
        Concepts text.

        ### Leaf Node A
        Leaf A text.

        ### Leaf Node B
        Leaf B text.

        ## Summary
        Summary text.
    """)
    try:
        chunks = chunk_file(p)
        headings = [c["heading"] for c in chunks]
        # Overview has a child (Key Concepts) so it's not a leaf —
        # but it has non-empty body, so it IS emitted as a body chunk.
        # Leaf Node A and B are leaves. Summary is a leaf (no children at deeper level).
        assert "Leaf Node A" in headings
        assert "Leaf Node B" in headings
        assert "Summary" in headings
        # heading_path should be fully qualified for nested ones
        leaf_a = next(c for c in chunks if c["heading"] == "Leaf Node A")
        assert "Key Concepts" in leaf_a["heading_path"], \
            f"Expected 'Key Concepts' in path, got {leaf_a['heading_path']!r}"
        assert "Leaf Node A" in leaf_a["heading_path"]
        print("PASS test_nested_headings_only_leaves")
    finally:
        p.unlink()


def test_heading_path_breadcrumb():
    """heading_path is a ' > '-separated breadcrumb."""
    p = _write_temp_md("""\
        # Chapter
        ## Section
        ### Subsection
        Leaf content here.
    """)
    try:
        chunks = chunk_file(p)
        leaf = next(c for c in chunks if c["heading"] == "Subsection")
        assert leaf["heading_path"] == "Chapter > Section > Subsection", \
            f"Got: {leaf['heading_path']!r}"
        print("PASS test_heading_path_breadcrumb")
    finally:
        p.unlink()


def test_empty_body_chunks_dropped():
    """Chunks with no body text (heading only) are not emitted."""
    p = _write_temp_md("""\
        # Section with content
        Some content.

        # Empty Section

        # Another with content
        More content.
    """)
    try:
        chunks = chunk_file(p)
        headings = [c["heading"] for c in chunks]
        assert "Empty Section" not in headings, \
            f"Empty section should be dropped, got headings={headings}"
        assert len(chunks) == 2
        print("PASS test_empty_body_chunks_dropped")
    finally:
        p.unlink()


def test_chapter_id_parsed_from_filename():
    """chapter_id extracted from chapter_N prefix in filename."""
    p = _write_temp_md("# Topic\nContent.\n")
    # Rename to match chapter_N.md pattern
    new_p = p.parent / "chapter_7_test.md"
    p.rename(new_p)
    try:
        chunks = chunk_file(new_p)
        assert chunks[0]["chapter_id"] == 7, \
            f"Expected chapter_id=7, got {chunks[0]['chapter_id']}"
        print("PASS test_chapter_id_parsed_from_filename")
    finally:
        new_p.unlink()


def test_no_headings_returns_empty():
    """File with no ATX headings → empty list (not a crash)."""
    p = _write_temp_md("Just some plain text.\nNo headings here.\n")
    try:
        chunks = chunk_file(p)
        assert chunks == [], f"Expected [], got {chunks}"
        print("PASS test_no_headings_returns_empty")
    finally:
        p.unlink()


def test_mixed_levels_min_level_used():
    """
    When a file has H1, H2, H3 — the min_level is H3 (most deeply nested).
    H3 sections are always leaves regardless of whether they have sub-content.
    """
    p = _write_temp_md("""\
        # H1
        ## H2 with child
        ### H3 child
        H3 content.
        ## H2 no children
        H2 leaf content.
    """)
    try:
        chunks = chunk_file(p)
        headings = [c["heading"] for c in chunks]
        assert "H3 child" in headings
        assert "H2 no children" in headings
        print("PASS test_mixed_levels_min_level_used")
    finally:
        p.unlink()


if __name__ == "__main__":
    test_flat_headings()
    test_nested_headings_only_leaves()
    test_heading_path_breadcrumb()
    test_empty_body_chunks_dropped()
    test_chapter_id_parsed_from_filename()
    test_no_headings_returns_empty()
    test_mixed_levels_min_level_used()
    print("\nAll tests passed.")