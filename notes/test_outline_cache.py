"""
test_outline_cache.py — Unit tests for the outline-generation cache
(ROADMAP P1.4): same merged objects → skip the LLM call on re-runs.

No API calls. Run:
    python notes/test_outline_cache.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import notes.outline_generator as og  # noqa: E402


OUTLINE_TEXT = json.dumps({
    "lecture_title": "Test Lecture",
    "chapters": [
        {"chapter_id": 1, "title": "Intro"},
        {"chapter_id": 2, "title": "Middle"},
        {"chapter_id": 3, "title": "Conclusion"},
    ],
})


def _write_objects(td: Path, n: int = 6, marker: str = "v1"):
    obj_dir = td / "objects"
    obj_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (obj_dir / f"chunk_{i}.json").write_text(json.dumps({
            "chunk_id": i,
            "topic": f"topic-{marker}",
            "concepts": ["a", "b"],
            "lecture_notes": ["note"],
        }))
    return obj_dir


def test_generate_lecture_outline_skips_llm_when_cached():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        obj_dir = _write_objects(td)
        output_dir = td / "out"
        calls = {"n": 0}

        def _fake_generate(chapters):
            calls["n"] += 1
            return OUTLINE_TEXT

        orig_gen = og.generate_outline
        og.generate_outline = _fake_generate
        try:
            r1 = og.generate_lecture_outline(str(obj_dir), str(output_dir))
            assert calls["n"] == 1
            assert r1["num_chapters"] == 3
            outline_path = Path(r1["outline_path"])
            assert outline_path.is_file()
            assert (outline_path.with_name(".outline.sha256")).is_file()

            # Identical inputs → cached, no LLM call
            r2 = og.generate_lecture_outline(str(obj_dir), str(output_dir))
            assert calls["n"] == 1, "cached run must not call the LLM"
            assert r2["num_chapters"] == 3

            # Changed object content → cache miss → LLM called again
            _write_objects(td, n=6, marker="v2")
            og.generate_lecture_outline(str(obj_dir), str(output_dir))
            assert calls["n"] == 2, "changed inputs must invalidate the cache"
        finally:
            og.generate_outline = orig_gen


if __name__ == "__main__":
    test_generate_lecture_outline_skips_llm_when_cached()
    print("\nAll tests passed.")
