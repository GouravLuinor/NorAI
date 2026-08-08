"""
test_selector_cache.py — Unit tests for screenshot-selector caching/reuse
(ROADMAP P1.3/P1.4): visual-analysis file loading and the per-chapter cache
skip (re-runs cost ~0 API calls).

No API calls. Run:
    python notes/test_selector_cache.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import notes.screenshot_selector as sel  # noqa: E402
from cache_util import write_marker  # noqa: E402


def test_load_visual_analysis():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        visual_dir = td / "visual_objects"
        visual_dir.mkdir(parents=True)
        frame_path = os.path.normpath(str(td / "screenshots/frames/ch1_f001.jpg"))
        analysis = {
            "chapter_id": 1,
            "frames": {
                frame_path: {
                    "ocr_text": "hello",
                    "importance_score": 7,
                    "visual_type": "slide",
                    "include_in_notes": True,
                }
            },
        }
        (visual_dir / "visual_analysis_ch1.json").write_text(json.dumps(analysis))
        loaded = sel.load_visual_analysis(str(td))
        key = os.path.normpath(frame_path)
        assert loaded.get(key) is not None, f"missing key {key!r} in {sorted(loaded)}"
        assert loaded[key]["ocr_text"] == "hello"
        assert loaded[key]["importance_score"] == 7
        print("PASS test_load_visual_analysis")


def test_load_visual_analysis_missing_dir_is_noop():
    with tempfile.TemporaryDirectory() as td:
        empty = sel.load_visual_analysis(str(Path(td) / "nope"))
        assert empty == {}
        print("PASS test_load_visual_analysis_missing_dir_is_noop")


def test_process_chapter_skips_when_up_to_date():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        out = td / "chapter_5_screenshots.json"
        marker = td / ".selection_ch5.sha256"
        out.write_text("{}")
        write_marker(marker, {"chapter_id": 5}, {"frame": "old analysis"})

        old_analysis = dict(sel._VISUAL_ANALYSIS)
        old_out = sel.SCREENSHOTS_OUT_DIR
        try:
            sel.SCREENSHOTS_OUT_DIR = td
            sel._VISUAL_ANALYSIS = {"frame": "old analysis"}
            orig_gen = sel.generate_selection
            orig_save = sel.save_selection

            def _bomb(*a, **k):
                raise AssertionError("selection stages must not run when cached")

            sel.generate_selection = _bomb
            sel.save_selection = _bomb
            try:
                sel.process_chapter({"chapter_id": 5}, 5)
            finally:
                sel.generate_selection = orig_gen
                sel.save_selection = orig_save
        finally:
            sel.SCREENSHOTS_OUT_DIR = old_out
            sel._VISUAL_ANALYSIS = old_analysis
        print("PASS test_process_chapter_skips_when_up_to_date")


if __name__ == "__main__":
    test_load_visual_analysis()
    test_load_visual_analysis_missing_dir_is_noop()
    test_process_chapter_skips_when_up_to_date()
    print("\nAll tests passed.")
