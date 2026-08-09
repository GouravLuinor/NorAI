"""
test_citations.py — Offline unit tests for P3.3 verified citations.

No LLM / Chroma calls — pure parsing + matching over synthetic answers/chunks.

Run:
    venv/bin/python tutor/test_citations.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.citations import (  # noqa: E402
    _normalize,
    parse_citations,
    verify_citations,
    verified_citations,
)


def _chunk(chunk_id: str, heading_path: str, heading: str | None = None) -> dict:
    return {
        "text": "body",
        "heading": heading or heading_path.split(" > ")[-1],
        "heading_path": heading_path,
        "chunk_id": chunk_id,
        "distance": 0.2,
        "relevant": True,
    }


CHUNKS = [
    _chunk("c1", "Chapter 4 > Core Architecture: The Transformer"),
    _chunk("c2", "Chapter 5 > Core Mechanism: Next-Word Prediction"),
    _chunk("c3", "Chapter 14 > The Three Mindsets Toward AI"),
]

SOURCE_BODY = (
    "The Transformer relies on self-attention to weigh every token.\n\n"
    "**Sources**\n"
    "• Core Architecture: The Transformer\n"
    "• Next-Word Prediction\n"
)


def test_normalize_strips_markdown_and_bullets():
    assert _normalize("**• Core Architecture:** The Transformer") == "core architecture: the transformer"


def test_parse_citations_standard():
    assert parse_citations(SOURCE_BODY) == [
        "Core Architecture: The Transformer",
        "Next-Word Prediction",
    ]


def test_parse_citations_variants():
    assert parse_citations("**Sources:**\n- A Section\n* B Section") == ["A Section", "B Section"]
    assert parse_citations("answer with no sources section") == []
    assert parse_citations("") == []


def test_parse_citations_stops_at_closing_line():
    ans = "**Sources**\n• Transformer\n\nWant to walk through an example?"
    assert parse_citations(ans) == ["Transformer"]


def test_verify_all_matches():
    result = verify_citations(SOURCE_BODY, CHUNKS)
    assert len(result) == 2
    assert all(c["verified"] for c in result)
    assert result[0]["chunk_id"] == "c1"
    assert result[1]["chunk_id"] == "c2"


def test_verify_flags_unverified():
    ans = "**Sources**\n• Core Architecture: The Transformer\n• Made Up Section\n"
    result = verify_citations(ans, CHUNKS)
    by_section = {c["section"]: c for c in result}
    assert by_section["Core Architecture: The Transformer"]["verified"] is True
    assert by_section["Made Up Section"]["verified"] is False
    assert by_section["Made Up Section"]["chunk_id"] is None


def test_verified_citations_drops_unverified():
    ans = "**Sources**\n• Core Architecture: The Transformer\n• Made Up Section\n"
    verified = verified_citations(ans, CHUNKS)
    assert [c["section"] for c in verified] == ["Core Architecture: The Transformer"]


def test_fuzzy_leaf_heading_matches():
    # Citation uses the leaf heading only, heading_path is the full breadcrumb.
    ans = "**Sources**\n• The Three Mindsets Toward AI\n"
    result = verify_citations(ans, CHUNKS)
    assert result[0]["verified"] is True
    assert result[0]["chunk_id"] == "c3"


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
