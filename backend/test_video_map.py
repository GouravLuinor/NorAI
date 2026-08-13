"""
test_video_map.py — Unit tests for backend/video_map.py (ROADMAP P6.3).

Builds fixture lecture dirs on disk and checks the seek map is derived
deterministically from outline + merged objects. No network, no LLM. Run:
    python backend/test_video_map.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.video_map import (  # noqa: E402
    build_video_map,
    load_chunk_times,
    load_outline_chapters,
)


def _write(lecture_dir: Path, rel: str, payload):
    path = lecture_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_video_map_derives_chapter_timestamps():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write(d, "notes/lecture_outline.json", {
            "lecture_title": "Test Lecture",
            "chapters": [
                {"chapter_id": 1, "title": "Intro", "chunk_ids": [0, 1]},
                {"chapter_id": 2, "title": "Deep Dive", "chunk_ids": [2]},
                {"chapter_id": 3, "title": "No Timestamps", "chunk_ids": [99]},
            ],
        })
        _write(d, "merged_objects/chunk_0.json", {"chunk_id": 0, "start": 0.0, "end": 75.5})
        _write(d, "merged_objects/chunk_1.json", {"chunk_id": 1, "start": 75.5, "end": 150.0})
        _write(d, "merged_objects/chunk_2.json", {"chunk_id": 2, "start": 150.0, "end": 240.0})
        _write(d, "merged_objects/chunk_99.json", {"chunk_id": 99, "start": None, "end": None})

        m = build_video_map(d)
        assert len(m["chapters"]) == 3
        assert m["chapters"][0]["start_sec"] == 0.0
        assert m["chapters"][0]["end_sec"] == 150.0
        assert m["chapters"][1]["start_sec"] == 150.0
        assert m["chapters"][1]["end_sec"] == 240.0
        # Chapter 3 references a chunk with no numeric timestamps → None.
        assert m["chapters"][2]["start_sec"] is None
        assert m["chapters"][2]["end_sec"] is None
        # Chunks list drops the unusable chunk, sorted by id.
        assert [c["chunk_id"] for c in m["chunks"]] == [0, 1, 2]
        assert m["chunks"][0] == {"chunk_id": 0, "start_sec": 0.0, "end_sec": 75.5}
    print("PASS test_build_video_map_derives_chapter_timestamps")


def test_build_video_map_missing_artifacts_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        m = build_video_map(Path(tmp))
        assert m == {"chapters": [], "chunks": []}
    print("PASS test_build_video_map_missing_artifacts_is_empty")


def test_build_video_map_handles_malformed_files():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "notes").mkdir(parents=True)
        (d / "notes" / "lecture_outline.json").write_text("not json{{", encoding="utf-8")
        (d / "merged_objects").mkdir(parents=True)
        (d / "merged_objects" / "chunk_0.json").write_text("garbage", encoding="utf-8")
        m = build_video_map(d)
        assert m == {"chapters": [], "chunks": []}
    print("PASS test_build_video_map_handles_malformed_files")


def test_build_video_map_ignores_chunks_without_numeric_start():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write(d, "notes/lecture_outline.json", {
            "chapters": [{"chapter_id": 1, "title": "A", "chunk_ids": [0, 1]}],
        })
        _write(d, "merged_objects/chunk_0.json", {"chunk_id": 0, "start": "5.5", "end": "10"})
        _write(d, "merged_objects/chunk_1.json", {"chunk_id": 1, "start": "oops", "end": None})
        _write(d, "merged_objects/chunk_2.json", {"chunk_id": 2, "start": 20, "end": 30})
        m = build_video_map(d)
        # chunk_1 (non-numeric start) dropped; chunk_2 kept but not in chapter.
        assert [c["chunk_id"] for c in m["chunks"]] == [0, 2]
        assert m["chapters"][0]["start_sec"] == 5.5
        assert m["chapters"][0]["end_sec"] == 10.0
    print("PASS test_build_video_map_ignores_chunks_without_numeric_start")


def test_load_chunk_times_string_path():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write(d, "merged_objects/chunk_3.json", {"chunk_id": 3, "start": 1.5, "end": 2.5})
        times = load_chunk_times(str(d))
        assert times == {3: {"start_sec": 1.5, "end_sec": 2.5}}
    print("PASS test_load_chunk_times_string_path")


def test_load_outline_chapters_returns_list():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        assert load_outline_chapters(d) == []
        _write(d, "notes/lecture_outline.json", {"chapters": [{"chapter_id": 1}]})
        assert load_outline_chapters(d) == [{"chapter_id": 1}]
    print("PASS test_load_outline_chapters_returns_list")


if __name__ == "__main__":
    test_build_video_map_derives_chapter_timestamps()
    test_build_video_map_missing_artifacts_is_empty()
    test_build_video_map_handles_malformed_files()
    test_build_video_map_ignores_chunks_without_numeric_start()
    test_load_chunk_times_string_path()
    test_load_outline_chapters_returns_list()
    print("\nAll tests passed.")
