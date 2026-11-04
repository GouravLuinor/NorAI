"""
test_quota_after_download.py — the pipeline enforces the user's remaining
quota minutes on the real (downloaded) duration, before any Gemini call.

/process can only check a probed length, and the YouTube probe fails on some
videos (an oEmbed-only probe returns a placeholder 900 s). No network, no DB:
ingestion, plan lookup and the content stages are stubbed.
Run directly: venv/bin/python backend/test_quota_after_download.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backend.orchestrator as orch  # noqa: E402
import backend.usage as usage  # noqa: E402
from documents.intake import Prepared  # noqa: E402


def _run(duration_sec: float, limits: tuple[int, int], document: bool = False):
    """Run the pipeline on a fake download; return (error, content_stage_ran)."""
    tmp = Path(tempfile.mkdtemp())
    meta = tmp / "metadata.json"
    meta.write_text(json.dumps({"duration": duration_sec}))
    ran = []

    def _lean(*a, **k):
        ran.append(1)
        raise RuntimeError("stop after the check")  # don't run the rest

    ing = {"video_path": str(tmp / "v.mp4"), "audio_path": str(tmp / "a.wav"),
           "metadata_path": str(meta)}
    if document:
        prep = Prepared("document", transcript_path=str(tmp / "t.json"), duration_sec=duration_sec,
                        words=int(duration_sec * 150 / 60), title="Doc", doc_type="pdf")
    else:
        prep = Prepared("video", ingest=ing)
    env = {"NORAI_DEV_ACCESS": "0", "ENFORCE_FREE_TRIAL_DURATION": "true"}
    with patch.dict(os.environ, env), \
         patch.object(orch, "create_lecture", lambda *a, **k: tmp), \
         patch.object(orch, "prepare_source", lambda *a, **k: prep), \
         patch.object(orch, "run_lean_stages", _lean), \
         patch.object(orch, "run_content_stages", _lean), \
         patch.object(orch, "record_pipeline_outcome", lambda *a, **k: None), \
         patch.object(orch, "record_metrics", lambda *a, **k: None), \
         patch.object(orch, "cleanup_lecture_dir", lambda *a, **k: None), \
         patch.object(usage, "plan_limits", lambda user_id: limits):
        try:
            orch.run_pipeline("t1", "youtube", url="https://youtu.be/x", user_id="u1")
        except Exception as e:  # noqa: BLE001
            return e, bool(ran)
    return None, bool(ran)


def test_over_remaining_quota_fails_before_content():
    # Free plan: 180-min lectures allowed, 45 quota minutes left; a 58-min video.
    err, ran = _run(58 * 60, (180, 45))
    assert isinstance(err, orch.TerminalPipelineError), err
    assert "45 lecture minutes left" in err.friendly, err.friendly
    assert not ran


def test_within_quota_reaches_content_stages():
    err, ran = _run(44 * 60 + 30, (180, 45))  # 44.5 min meters as 45
    assert ran and isinstance(err, RuntimeError), err


def test_over_plan_length_still_fails():
    err, ran = _run(100 * 60, (90, 300))
    assert isinstance(err, orch.TerminalPipelineError) and "limit per lecture" in err.friendly
    assert not ran


def test_document_words_meter_like_minutes():
    # 9,000 words = 60 quota minutes; 45 left.
    err, ran = _run(60 * 60, (180, 45), document=True)
    assert isinstance(err, orch.TerminalPipelineError), err
    assert "9,000 words" in err.friendly and "split the document" in err.friendly, err.friendly
    assert not ran
    err, ran = _run(30 * 60, (180, 45), document=True)
    assert ran and isinstance(err, RuntimeError), err


if __name__ == "__main__":
    test_over_remaining_quota_fails_before_content()
    test_within_quota_reaches_content_stages()
    test_over_plan_length_still_fails()
    test_document_words_meter_like_minutes()
    print("test_quota_after_download: 4/4 passed")
