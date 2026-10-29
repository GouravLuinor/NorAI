"""
test_estimate.py — Unit tests for the pre-flight estimator + /estimate endpoint
(ROADMAP P1.8). Run directly: venv/bin/python backend/test_estimate.py
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.estimator import (  # noqa: E402
    estimate_pipeline,
    load_calibration,
    record_metrics,
    recalibrate,
    MIN_CALIBRATION_SAMPLES,
)
from backend.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, cond: bool):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok  {label}")
    else:
        FAILED += 1
        print(f"FAIL  {label}")


# ── Estimator math ────────────────────────────────────────────────────────────

def test_estimate_lean_matches_observed():
    """17.07-min run: 123 segments → 9 chunks, 4 chapters, 1 + 1 + 4 = 6 counted calls."""
    est = estimate_pipeline(17.07, segments=123, metrics_path="/nonexistent/metrics.jsonl")
    check("9 chunks", est["estimated_chunks"] == 9)
    check("4 chapters", est["estimated_chapters"] == 4)
    check("6 calls", est["est_calls"] == 6)
    check("3 min (observed 2.4)", est["est_time_min"] == 3)
    long = estimate_pipeline(71, metrics_path="/nonexistent/metrics.jsonl")
    check("71 min: 4 slices + 1 + chapters", long["est_calls"] == 4 + 1 + long["estimated_chapters"])
    check("71 min: 10 chapters (cap)", long["estimated_chapters"] == 10)


def test_estimate_long_lecture_bounded():
    """3-hour lecture: adaptive spc bounds the chunk count."""
    est = estimate_pipeline(181, metrics_path="/nonexistent/metrics.jsonl")
    check("3h spc == 30 (cap)", est["segments_per_chunk"] == 30)
    check("3h chunks bounded (<=65)", est["estimated_chunks"] <= 65)
    check("3h chapters: 1 per 12 min floor (16)", est["estimated_chapters"] == 16)
    check("3h exceeds free trial", est["free_trial_ok"] is False)


def test_estimate_segments_override():
    est = estimate_pipeline(8.43, segments=88, metrics_path="/nonexistent/metrics.jsonl")
    check("segments override respected", est["segments"] == 88)
    check("8.43 min within free trial", est["free_trial_ok"] is True)


def test_estimate_no_calibration_uses_defaults():
    est = estimate_pipeline(10, metrics_path="/nonexistent/metrics.jsonl")
    check("no calibration → not calibrated", est["calibrated"] is False)
    check("no calibration → 0 runs", est["n_calibration_runs"] == 0)


# ── Calibration layer ─────────────────────────────────────────────────────────

def _fake_metrics_dir(pipeline: str | None = "lean"):
    tmp = Path(tempfile.mkdtemp())
    metrics = tmp / "metrics.jsonl"
    # 5 fresh runs of the 17-min lecture: 1 slice + 1 structure + 4 chapters.
    for i in range(MIN_CALIBRATION_SAMPLES):
        entry = {
            "ts": "2026-01-01T00:00:00+0000",
            "lecture_id": f"f{i}",
            "source_type": "youtube",
            "duration_sec": 1024.0,
            "num_segments": 123,
            "segments_per_chunk": 15,
            "num_chunks": 9,
            "num_chapters": 4,
            "llm_calls": 6,
            "embed_batches": 3,
            "stage_seconds": {"transcription": 40.0, "pipeline": 142.0},
            "completed": True,
            "error": None,
            "planned": None,
        }
        if pipeline:
            entry["pipeline"] = pipeline
        record_metrics(entry, metrics)
    return metrics


def test_calibration_fits_from_fresh_runs():
    metrics = _fake_metrics_dir()
    cal = load_calibration(metrics)
    check("calibration counts 5 runs", cal["n_fresh_runs"] == 5)
    check("segs_per_min ≈ 7.2", abs(cal["segs_per_min"] - 123 / (1024.0 / 60)) < 0.01)
    check("transcription_realtime ≈ 0.039", abs(cal["transcription_realtime"] - 40.0 / 1024.0) < 0.001)
    # (142 - 40 - 30) / (1 structure + 2 chapter waves) = 24 s per round
    check("sec_per_call fit on rounds", abs(cal["sec_per_call"] - 24.0) < 0.01)
    est = estimate_pipeline(17.07, segments=123, metrics_path=metrics)
    check("calibrated flag true", est["calibrated"] is True)
    check("calibrated 6 calls", est["est_calls"] == 6)


def test_calibration_ignores_legacy_entries():
    """Entries without a "pipeline" key came from the retired legacy chain."""
    check("legacy entries ignored", load_calibration(_fake_metrics_dir(pipeline=None))["n_fresh_runs"] == 0)
    check("legacy-tagged entries ignored", load_calibration(_fake_metrics_dir(pipeline="legacy"))["n_fresh_runs"] == 0)


def test_calibration_ignores_rerun_zero_calls():
    tmp = Path(tempfile.mkdtemp())
    metrics = tmp / "m.jsonl"
    record_metrics({
        "pipeline": "lean", "completed": True, "llm_calls": 0, "num_segments": 88,
        "duration_sec": 506.0, "num_chunks": 6, "num_chapters": 3,
        "embed_batches": 0, "stage_seconds": {"transcription": 0, "pipeline": 20},
    }, metrics)
    cal = load_calibration(metrics)
    check("rerun excluded from fresh fits", cal["n_fresh_runs"] == 0)


def test_recalibrate_cli_prints():
    metrics = _fake_metrics_dir()
    # Just ensure it doesn't raise.
    recalibrate(metrics)


# ── /estimate endpoint contract ───────────────────────────────────────────────
# NOTE: TestClient used WITHOUT `with` so lifespan startup (init_db → Postgres)
# is not triggered; the endpoint itself doesn't need the DB.
client = TestClient(app)


def test_estimate_youtube_success():
    with patch("backend.main.probe_video_metadata", return_value={"duration_sec": 506.0, "title": "Networking"}):
        r = client.post("/estimate", data={"source_type": "youtube", "url": "https://youtube.com/watch?v=abc"})
        body = r.json()
    check("youtube 200", r.status_code == 200)
    check("youtube available", body.get("available") is True)
    check("youtube title surfaced", body.get("title") == "Networking")
    check("youtube calls > 0", body.get("est_calls", 0) > 0)
    check("youtube duration ≈ 8.43", abs(body.get("duration_min", 0) - 506.0 / 60.0) < 0.01)


def test_estimate_youtube_probe_failure_soft():
    with patch("backend.main.probe_video_metadata", return_value=None):
        r = client.post("/estimate", data={"source_type": "youtube", "url": "https://youtube.com/watch?v=abc"})
        body = r.json()
    check("probe failure 200", r.status_code == 200)
    check("probe failure available=false", body.get("available") is False)


def test_estimate_invalid_youtube_url_400():
    r = client.post("/estimate", data={"source_type": "youtube", "url": "https://example.com/x"})
    check("invalid url 400", r.status_code == 400)


def test_estimate_gdrive_soft_fail():
    r = client.post("/estimate", data={"source_type": "gdrive", "url": "https://drive.google.com/file/d/abc/view"})
    body = r.json()
    check("gdrive 200", r.status_code == 200)
    check("gdrive available=false", body.get("available") is False)


def test_estimate_upload_with_duration():
    r = client.post("/estimate", data={"source_type": "upload", "duration": "10.0"})
    body = r.json()
    check("upload 200", r.status_code == 200)
    check("upload available", body.get("available") is True)
    check("upload calls > 0", body.get("est_calls", 0) > 0)


def test_estimate_plan_fit_anonymous_is_free():
    from backend.plans import get_plan

    free = get_plan("free")
    r = client.post("/estimate", data={"source_type": "upload", "duration": "10.0"})
    body = r.json()
    check("plan fit: anonymous → free plan", body.get("plan_id") == "free")
    check("plan fit: max lecture surfaced", body.get("plan_max_min") == free.max_lecture_min)
    check("plan fit: minutes needed rounds up", body.get("minutes_needed") == 10)
    check("plan fit: 10 min fits free", body.get("fits_plan") is True)

    too_long = free.max_lecture_min + 5
    r = client.post("/estimate", data={"source_type": "upload", "duration": str(too_long)})
    check("plan fit: over max lecture → fits_plan false", r.json().get("fits_plan") is False)


def test_estimate_upload_missing_duration():
    r = client.post("/estimate", data={"source_type": "upload"})
    body = r.json()
    check("upload no-duration 200", r.status_code == 200)
    check("upload no-duration available=false", body.get("available") is False)


def test_estimate_bad_source_type_400():
    r = client.post("/estimate", data={"source_type": "ftp"})
    check("bad source_type 400", r.status_code == 400)


if __name__ == "__main__":
    test_estimate_lean_matches_observed()
    test_estimate_long_lecture_bounded()
    test_estimate_segments_override()
    test_estimate_no_calibration_uses_defaults()
    test_calibration_fits_from_fresh_runs()
    test_calibration_ignores_legacy_entries()
    test_calibration_ignores_rerun_zero_calls()
    test_recalibrate_cli_prints()
    test_estimate_youtube_success()
    test_estimate_youtube_probe_failure_soft()
    test_estimate_invalid_youtube_url_400()
    test_estimate_gdrive_soft_fail()
    test_estimate_upload_with_duration()
    test_estimate_plan_fit_anonymous_is_free()
    test_estimate_upload_missing_duration()
    test_estimate_bad_source_type_400()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED > 0 else 0)
