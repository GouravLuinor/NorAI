"""
test_lean.py — offline tests for the lean pipeline (no API calls).

Run:
    python lean/test_lean.py
"""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import lean.chapters as lc  # noqa: E402
import lean.structure as ls  # noqa: E402
from backend.video_map import build_video_map  # noqa: E402
from transcription.gemini_transcriber import parse_compact_transcript  # noqa: E402


# ── compact transcription ─────────────────────────────────────────────────────

def test_parse_compact_transcript():
    text = (
        "[00:00] Hello everyone.\n"
        "[00:03] Today we look at\n"
        "dynamic programming.\n"          # untimed → continues previous line
        "\n"
        "[01:05] After a long pause.\n"   # MM:SS, as the prompt asks: 65 s
        "[01:00] Out of order.\n"         # goes backwards → clamped to 65
        "[999] Past the end.\n"           # bare seconds; clamped to the clip duration
    )
    segs = parse_compact_transcript(text, duration=120.0)
    assert [s["start"] for s in segs] == [0.0, 3.0, 65.0, 65.0, 120.0], segs
    assert segs[1]["text"] == "Today we look at dynamic programming."
    # end = next start, but no longer than the words could take
    assert segs[0]["end"] == 2.2, "2 words: start + 1 s + 2 x 0.6 s, before the next start"
    assert segs[1]["end"] < 10, "a long silence must not stretch the sentence"
    assert all(s["end"] >= s["start"] for s in segs)
    assert segs[-1]["end"] == 120.0
    print("PASS test_parse_compact_transcript")


# ── structure ─────────────────────────────────────────────────────────────────

def _chunks(n=6, length=60.0):
    return [
        {"chunk_id": i, "start": i * length, "end": (i + 1) * length - 1,
         "segment_ids": [2 * i, 2 * i + 1], "text": f"chunk {i}\n\ntext"}
        for i in range(n)
    ]


def test_chapter_count_range():
    assert ls.chapter_count_range(4, 3) == (1, 1, 1)
    assert ls.chapter_count_range(8.7, 12) == (2, 2, 3)
    assert ls.chapter_count_range(15.5, 11) == (2, 4, 4)
    assert ls.chapter_count_range(71, 67) == (6, 10, 10)
    assert ls.chapter_count_range(71, 3) == (3, 3, 3), "never more chapters than chunks"
    assert lc.notes_word_target(100) == 300 and lc.notes_word_target(2949) == 1450
    assert lc.notes_word_target(13539) == 2200
    assert lc.notes_section_count(300) == 3 and lc.notes_section_count(900) == 6
    assert lc.notes_section_count(2200) == 12
    print("PASS test_chapter_count_range")


def test_repair_plan_makes_ranges_contiguous():
    C = ls.ChapterPlan
    plan = ls.LecturePlan(lecture_title="L", chapters=[
        C(title="B", start_chunk=3, end_chunk=4, focus_concepts=[], summary=""),
        C(title="A", start_chunk=1, end_chunk=3, focus_concepts=[], summary=""),  # gap at 0, overlaps B
        C(title=" ", start_chunk=5, end_chunk=5, focus_concepts=[], summary=""),  # empty title dropped
    ])
    fixed = ls.repair_plan(plan, 6)
    assert [(c.title, c.start_chunk, c.end_chunk) for c in fixed] == [("A", 0, 3), ("B", 4, 5)], fixed

    empty = ls.repair_plan(ls.LecturePlan(lecture_title="L", chapters=[]), 6)
    assert [(c.start_chunk, c.end_chunk) for c in empty] == [(0, 5)]
    print("PASS test_repair_plan_makes_ranges_contiguous")


def test_outline_feeds_video_map():
    C = ls.ChapterPlan
    chunks = _chunks()
    outline = ls.build_outline("Lecture", [
        C(title="A", start_chunk=0, end_chunk=2, focus_concepts=["x"], summary="s"),
        C(title="B", start_chunk=3, end_chunk=5, focus_concepts=[], summary=""),
    ], chunks)
    assert outline["chapters"][1]["chunk_ids"] == [3, 4, 5]
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "notes").mkdir()
        (Path(td) / "notes" / "lecture_outline.json").write_text(json.dumps(outline))
        vm = build_video_map(td)  # no merged_objects/: chunk times come from the outline
    assert [(c["start_sec"], c["end_sec"]) for c in vm["chapters"]] == [(0.0, 179.0), (180.0, 359.0)]
    assert len(vm["chunks"]) == 6
    print("PASS test_outline_feeds_video_map")


# ── chapter helpers ───────────────────────────────────────────────────────────

def test_clean_questions_repairs_and_drops():
    raw = [
        {"type": "MCQ", "difficulty": "Easy", "concepts": ["a"], "question": "q1",
         "options": ["Alpha", "Beta", "Gamma", "Delta"], "answer": "b"},        # letter → "Beta"
        {"type": "True/False", "difficulty": "Easy", "concepts": [], "question": "q2",
         "options": [], "answer": "true"},                                    # options filled in
        {"type": "Short Answer", "difficulty": "Medium", "concepts": [], "question": "q3",
         "options": ["stray"], "answer": "text"},                             # options cleared
        {"type": "MCQ", "difficulty": "Hard", "concepts": [], "question": "bad",
         "options": ["x", "y"], "answer": "not an option"},                   # dropped
        {"type": "Essay", "difficulty": "Easy", "concepts": [], "question": "bad type",
         "answer": "z"},                                                      # dropped
        "not a dict",
    ]
    qs = lc.clean_questions(raw, chapter_id=7)
    assert [q["question"] for q in qs] == ["q1", "q2", "q3"]
    assert [q["question_id"] for q in qs] == [1, 2, 3]
    assert all(q["chapter_id"] == 7 for q in qs)
    assert qs[0]["answer"] == "Beta"
    assert qs[1]["options"] == ["True", "False"] and qs[1]["answer"] == "True"
    assert qs[2]["options"] == []
    print("PASS test_clean_questions_repairs_and_drops")


def test_span_segments_and_frame_sampling():
    chunks = _chunks()
    ch1 = {"start_chunk": 0, "end_chunk": 2}
    ch2 = {"start_chunk": 3, "end_chunk": 5}
    assert lc.chapter_span(ch1, chunks, 400) == (0.0, 180.0)
    assert lc.chapter_span(ch2, chunks, 400) == (180.0, 400)
    segs = [{"segment_id": i, "start": i * 30.0, "end": i * 30.0 + 29, "text": f"s{i}"} for i in range(12)]
    assert [s["segment_id"] for s in lc.chapter_segments(ch2, chunks, segs)] == [6, 7, 8, 9, 10, 11]

    kfs = [{"timestamp": t, "image_path": f"f{t}.jpg"} for t in range(0, 400, 8)]
    picked = lc.sample_frames(kfs, 0.0, 180.0, cap=5)
    assert len(picked) == 5 and picked[0]["timestamp"] == 0 and picked[-1]["timestamp"] == 176
    assert lc.sample_frames(kfs, 390.0, 400.0, cap=12, last=True) == [{"timestamp": 392, "image_path": "f392.jpg"}]
    print("PASS test_span_segments_and_frame_sampling")


def test_select_screenshots():
    F = lc.FrameNote
    sent = [{"timestamp": 10.0 * i, "image_path": f"f{i}.jpg"} for i in range(4)]
    frames = [
        F(frame=1, visual_type="talking_head", ocr_text="", description="face", importance=9, include_in_notes=True, section="A"),
        F(frame=2, visual_type="slide", ocr_text="x", description="slide", importance=7, include_in_notes=True, section="A"),
        F(frame=3, visual_type="diagram", ocr_text="", description="diag", importance=9, include_in_notes=True, section="B"),
        F(frame=4, visual_type="slide", ocr_text="", description="low", importance=3, include_in_notes=True, section="B"),
        F(frame=9, visual_type="slide", ocr_text="", description="bad index", importance=10, include_in_notes=True, section="B"),
    ]
    shots = lc.select_screenshots(frames, sent)
    # talking head, low importance and out-of-range frames are excluded;
    # the rest are ordered by importance.
    assert [s["path"] for s in shots] == ["f2.jpg", "f1.jpg"], shots
    assert [s["reason"] for s in shots] == ["diag", "slide"], shots
    assert shots[0]["timestamp"] == 20.0

    # The same slide shown twice (dp8 ch1: 1:04 and 1:36) is kept once — the
    # first by importance/time; a slide whose text differs is kept.
    sent = [{"timestamp": 32.0 * i, "image_path": f"g{i}.jpg"} for i in range(5)]
    frames = [
        F(frame=1, visual_type="slide", ocr_text="300. Longest Increasing Subsequence",
          description="The problem description for LIS.", importance=9, include_in_notes=True, section="A"),
        F(frame=2, visual_type="slide", ocr_text="300.  longest increasing subsequence",
          description="The LIS problem statement.", importance=9, include_in_notes=True, section="A"),
        F(frame=3, visual_type="slide", ocr_text="Input: nums = [0, 1, 0, 3, 2, 3] Output = 4",
          description="Example input.", importance=8, include_in_notes=True, section="A"),
        F(frame=4, visual_type="diagram", ocr_text="", description="An array visualization for LIS.",
          importance=7, include_in_notes=True, section="A"),
        F(frame=5, visual_type="diagram", ocr_text="", description="An array visualization for LIS.",
          importance=7, include_in_notes=True, section="A"),
    ]
    shots = lc.select_screenshots(frames, sent)
    assert [s["path"] for s in shots] == ["g0.jpg", "g2.jpg", "g3.jpg"], shots
    print("PASS test_select_screenshots")


# ── one chapter end to end (fake Gemini) ─────────────────────────────────────

def _fake_response(n_frames):
    return {
        "study_notes_title": "Intro",
        "study_notes_sections": [
            {"section_type": "definition", "title": "What", "content_markdown": "Body $x$", "start": "0:31"},
            {"section_type": "prose", "title": "Why", "content_markdown": "More", "start": "garbage"},
        ],
        "revision_summary": ["one", "two", "three"],
        "core_concepts_breakdown": [{"concept": "c", "explanation": "e"}],
        "assessment_questions": [
            {"question_id": 1, "chapter_id": 1, "type": "MCQ", "difficulty": "Easy", "concepts": ["c"],
             "question": "Which?", "options": ["A1", "B1", "C1", "D1"], "answer": "C1",
             "flashcard_front": "Which?", "flashcard_back": "C1"},
            {"question_id": 2, "chapter_id": 1, "type": "MCQ", "difficulty": "Easy", "concepts": [],
             "question": "Broken", "options": [], "answer": "x"},
        ],
        "frames": [
            {"frame": i, "visual_type": "slide", "ocr_text": f"ocr {i}", "description": f"d{i}",
             "importance": 8, "include_in_notes": True, "section": "What"}
            for i in range(1, n_frames + 1)
        ] + [{"frame": "junk"}],
    }


def test_process_chapter_writes_artifacts_and_caches():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        kf_dir = out / "screenshots" / "keyframes"
        kf_dir.mkdir(parents=True)
        keyframes = []
        for t in (0, 40, 90):
            p = kf_dir / f"frame_{t}.jpg"
            p.write_bytes(b"\xff\xd8\xff\xd9")
            keyframes.append({"timestamp": float(t), "image_path": str(p)})
        chunks = _chunks(n=2)
        segments = [{"segment_id": i, "start": i * 30.0, "end": i * 30.0 + 29, "text": f"said {i}"} for i in range(4)]
        outline = {"lecture_title": "L", "chapters": [
            {"chapter_id": 1, "title": "Intro", "focus_concepts": [], "summary": "", "chunk_ids": [0, 1],
             "start_chunk": 0, "end_chunk": 1},
        ]}

        calls = {"n": 0, "contents": None}

        class _Models:
            def generate_content(self, model, contents, config):
                calls["n"] += 1
                calls["contents"] = contents
                return SimpleNamespace(text=json.dumps(_fake_response(3)), usage_metadata=None)

        orig = (lc.get_client, lc.record_generate_usage)
        lc.get_client = lambda: SimpleNamespace(models=_Models())
        lc.record_generate_usage = lambda *a, **k: None
        try:
            ok = lc.process_chapter(outline, 0, chunks, segments, keyframes, str(out), lecture_end=120.0)
            assert ok and calls["n"] == 1
            # prompt + (label, image) per frame
            assert len(calls["contents"]) == 1 + 2 * 3
            assert "[0:30] said 1" in calls["contents"][0]

            notes = json.loads((out / "notes" / "chapter_1.json").read_text())
            assert [s["start_sec"] for s in notes["sections"]] == [31.0, None]
            assert "## What" in (out / "notes" / "chapter_1.md").read_text()
            quiz = json.loads((out / "assessment" / "assessment_chapter_1.json").read_text())
            assert [q["question"] for q in quiz["questions"]] == ["Which?"], "invalid question dropped, not fatal"
            cards = json.loads((out / "flashcards" / "flashcards_chapter_1.json").read_text())
            assert len(cards["flashcards"]) == 1
            shots = json.loads((out / "screenshots" / "selected" / "chapter_1_screenshots.json").read_text())
            assert len(shots["screenshots"]) == 3 and shots["screenshots"][0]["section"] == "What"
            vis = json.loads((out / "visual_objects" / "visual_analysis_ch1.json").read_text())
            assert vis["frames"][keyframes[1]["image_path"]]["ocr_text"] == "ocr 2"
            assert (out / "revision" / "revision_chapter_1.md").is_file()

            # Same inputs → cached, no call.
            assert lc.process_chapter(outline, 0, chunks, segments, keyframes, str(out), lecture_end=120.0)
            assert calls["n"] == 1, "cached chapter must not call the LLM"
        finally:
            lc.get_client, lc.record_generate_usage = orig
    print("PASS test_process_chapter_writes_artifacts_and_caches")


def test_process_chapter_degrades_on_bad_output():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        chunks = _chunks(n=1)
        segments = [{"segment_id": 0, "start": 0.0, "end": 5.0, "text": "hi"}]
        outline = {"lecture_title": "L", "chapters": [
            {"chapter_id": 1, "title": "Only", "chunk_ids": [0], "start_chunk": 0, "end_chunk": 0},
        ]}

        class _Models:
            def generate_content(self, model, contents, config):
                return SimpleNamespace(text="{not json", usage_metadata=None)

        orig = (lc.get_client, lc.record_generate_usage)
        lc.get_client = lambda: SimpleNamespace(models=_Models())
        lc.record_generate_usage = lambda *a, **k: None
        try:
            assert lc.process_chapter(outline, 0, chunks, segments, [], str(out), lecture_end=5.0) is False
            quiz = json.loads((out / "assessment" / "assessment_chapter_1.json").read_text())
            assert quiz["incomplete"] is True
            assert not (out / "notes" / ".lean_ch1.sha256").exists(), "a degraded chapter must be retried next run"
        finally:
            lc.get_client, lc.record_generate_usage = orig
    print("PASS test_process_chapter_degrades_on_bad_output")


if __name__ == "__main__":
    test_parse_compact_transcript()
    test_chapter_count_range()
    test_repair_plan_makes_ranges_contiguous()
    test_outline_feeds_video_map()
    test_clean_questions_repairs_and_drops()
    test_span_segments_and_frame_sampling()
    test_select_screenshots()
    test_process_chapter_writes_artifacts_and_caches()
    test_process_chapter_degrades_on_bad_output()
    print("\nAll tests passed.")
