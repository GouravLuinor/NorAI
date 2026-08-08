"""
test_visual_cache.py — Unit tests for the visual-extraction whole-stage cache
(ROADMAP P1.4): re-running with unchanged mapping+outline must skip the
(chapter-aligned) LLM batch calls entirely.

No API calls. Run:
    python visual/test_visual_cache.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import visual.visual_extractor as ve  # noqa: E402


def _bomb(*a, **k):
    raise AssertionError("batch processing must not run when cache is up to date")


def _write_inputs(td: Path, marker_text: str = "content-v1"):
    mapping = [{"chunk_id": i, "text": f"chunk {i}"} for i in range(6)]
    mapping_path = td / "mapping.json"
    mapping_path.write_text(json.dumps(mapping))
    outline = {
        "lecture_title": "Test",
        "chapters": [
            {"chapter_id": 1, "title": "A", "chunk_ids": [0, 1]},
            {"chapter_id": 2, "title": "B", "chunk_ids": [2, 3]},
            {"chapter_id": 3, "title": "C", "chunk_ids": [4, 5]},
        ],
    }
    outline_path = td / "outline.json"
    outline_path.write_text(json.dumps(outline))
    return mapping_path, outline_path, marker_text


def test_process_all_chunks_skips_when_cached():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        mapping_path, outline_path, _ = _write_inputs(td)
        out_dir = td / "visual_objects"
        calls = {"n": 0}

        def _fake_batch(ch_id, ch_title, ch_chunks, output_dir):
            calls["n"] += 1
            out_dir = Path(output_dir)
            (out_dir / f"chunk_{ch_chunks[0]['chunk_id']}.json").write_text("{}")
            (out_dir / f"visual_analysis_ch{ch_id}.json").write_text(json.dumps({"frames": {}}))

        orig_batch = ve.process_chapter_visual_batch
        ve.process_chapter_visual_batch = _fake_batch
        try:
            ve.process_all_chunks(str(mapping_path), str(out_dir), outline_path=str(outline_path))
            assert calls["n"] == 3, f"first run should process all chapters, got {calls['n']}"
            assert (out_dir / ".visual_extract.sha256").is_file()

            # Second run, identical inputs → must skip (batch fn would raise)
            calls["n"] = 0
            ve.process_chapter_visual_batch = _bomb
            ve.process_all_chunks(str(mapping_path), str(out_dir), outline_path=str(outline_path))
            assert calls["n"] == 0, "cached run must not call the batch function"
        finally:
            ve.process_chapter_visual_batch = orig_batch


def test_process_all_chunks_reruns_on_input_change():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        mapping_path, outline_path, _ = _write_inputs(td)
        out_dir = td / "visual_objects"
        calls = {"n": 0}

        def _fake_batch(ch_id, ch_title, ch_chunks, output_dir):
            calls["n"] += 1
            out_dir = Path(output_dir)
            (out_dir / f"chunk_{ch_chunks[0]['chunk_id']}.json").write_text("{}")
            (out_dir / f"visual_analysis_ch{ch_id}.json").write_text(json.dumps({"frames": {}}))

        orig_batch = ve.process_chapter_visual_batch
        ve.process_chapter_visual_batch = _fake_batch
        try:
            ve.process_all_chunks(str(mapping_path), str(out_dir), outline_path=str(outline_path))
            assert calls["n"] == 3
            calls["n"] = 0

            # Change the mapping content → cache must miss → reprocess
            mapping_path.write_text(json.dumps([{"chunk_id": i} for i in range(3)]))
            ve.process_all_chunks(str(mapping_path), str(out_dir), outline_path=str(outline_path))
            assert calls["n"] > 0, "changed mapping must invalidate the cache"
        finally:
            ve.process_chapter_visual_batch = orig_batch


if __name__ == "__main__":
    test_process_all_chunks_skips_when_cached()
    test_process_all_chunks_reruns_on_input_change()
    print("\nAll tests passed.")
