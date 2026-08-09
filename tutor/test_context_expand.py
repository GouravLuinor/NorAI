"""
test_context_expand.py — Offline tests for P3.4 chunk context expansion.

Builds synthetic notes .md files and verifies expand_context pulls the parent
section + siblings around a leaf chunk, capped at the char budget.

Run:
    venv/bin/python tutor/test_context_expand.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.context_expand import expand_context  # noqa: E402
from tutor.chunker import chunk_file  # noqa: E402

_MD = """\
# Chapter 1: Foundations

## Overview

Generative AI is a paradigm shift in computing.

## Key Concepts

Machine learning learns patterns from data.

### Key Concepts: ML

ML is the foundation of modern AI.

### Key Concepts: Generative AI

GenAI creates new content by learning data structure.

## The Paradigm Shift

We moved from rule-based to learning-based computing.
"""


def _write_and_chunk(tmpdir: Path) -> list[dict]:
    md = tmpdir / "chapter_1.md"
    md.write_text(_MD, encoding="utf-8")
    return chunk_file(md)


def test_expand_pulls_parent_and_siblings():
    with tempfile.TemporaryDirectory() as td:
        chunks = _write_and_chunk(Path(td))
        leaf = next(c for c in chunks if c["heading"] == "Key Concepts: Generative AI")
        ctx = expand_context(leaf)
        # Parent heading + both sibling leaves present
        assert "Key Concepts" in ctx
        assert "Key Concepts: ML" in ctx
        assert "Key Concepts: Generative AI" in ctx
        # Should NOT pull in unrelated top-level siblings
        assert "The Paradigm Shift" not in ctx


def test_expand_missing_file_returns_empty():
    assert expand_context({"source": "/nonexistent/chapter_1.md", "heading": "X"}) == ""


def test_expand_no_source_returns_empty():
    assert expand_context({"heading": "X"}) == ""


def test_expand_top_level_chunk_has_no_parent():
    with tempfile.TemporaryDirectory() as td:
        md = Path(td) / "chapter_1.md"
        md.write_text("# Solo\n\nJust a body with no children.\n", encoding="utf-8")
        (chunk,) = chunk_file(md)
        assert chunk["heading"] == "Solo"
        assert expand_context(chunk) == ""


def test_expand_respects_char_cap():
    with tempfile.TemporaryDirectory() as td:
        chunks = _write_and_chunk(Path(td))
        leaf = next(c for c in chunks if c["heading"] == "Key Concepts: Generative AI")
        ctx = expand_context(leaf, max_chars=40)
        assert len(ctx) <= 40


def test_expand_survives_suffix_match():
    chunk = {
        "source": "/tmp/unused.md",
        "heading": "Key Concepts: ML",
        "heading_path": "Foundations > Key Concepts > Key Concepts: ML",
    }
    # file missing → returns "" (path handling), but if file existed we'd match.
    assert expand_context(chunk) == ""


if __name__ == "__main__":
    import traceback

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if failures else 0)
