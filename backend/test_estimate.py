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

def test_estimate_baseline_matches_observed():
    """8.43-min lecture → 88 segs, 6 chunks, 3 chapters, 17 calls (observed)."""
    with patch.dict("os.environ", {"MAX_FREE_DURATION_MIN": "15"}):
        est = estimate_pipeline(8.43, metrics_path="/nonexistent/metrics.jsonl")
    check("baseline 17 calls", est["est_calls"] == 17)
    check("baseline 6 chunks", est["estimated_chunks"] == 6)
    check("baseline 3 chapters", est["estimated_chapters"] == 3)
    check("baseline within free trial", est["free_trial_ok"] is True)


def test_estimate_long_lecture_bounded():
    """3-hour lecture: adaptive spc bounds chunk count and calls."""
    est = estimate_pipeline(181, metrics_path="/nonexistent/metrics.jsonl")
    check("3h spc == 30 (cap)", est["segments_per_chunk"] == 30)
    check("3h chunks bounded (<=65)", est["estimated_chunks"] <= 65)
    check("3h chapters dynamic scale (<=16)", est["estimated_chapters"] <= 16)
    check("3h exceeds free trial", est["free_trial_ok"] is False)


def test_estimate_segments_override():
    est = estimate_pipeline(8.43, segments=88, metrics_path="/nonexistent/metrics.jsonl")
    check("segments override respected", est["segments"] == 88)


def test_estimate_no_calibration_uses_defaults():
    est = estimate_pipeline(10, metrics_path="/nonexistent/metrics.jsonl")
    check("no calibration → not calibrated", est["calibrated"] is False)
    check("no calibration → 0 runs", est["n_calibration_runs"] == 0)


# ── Calibration layer ─────────────────────────────────────────────────────────

def _fake_metrics_dir():
    tmp = Path(tempfile.mkdtemp())
    metrics = tmp / "metrics.jsonl"
    # 5 fresh runs, all with the same call mix: 6+1+3+2+3+2 = 17.
    for i in range(MIN_CALIBRATION_SAMPLES):
        entry = {
            "ts": "2026-01-01T00:00:00+0000",
            "lecture_id": f"f{i}",
            "source_type": "youtube",
            "duration_sec": 506.0,
            "num_segments": 88,
            "segments_per_chunk": 15,
            "num_chunks": 6,
            "num_chapters": 3,
            "llm_calls": 17,
            "embed_batches": 2,
            "stage_seconds": {"transcription": 400.0, "pipeline": 1500.0},
            "completed": True,
            "error": None,
            "planned": None,
        }
        record_metrics(entry, metrics)
    return metrics


def test_calibration_fits_from_fresh_runs():
    metrics = _fake_metrics_dir()
    cal = load_calibration(metrics)
    check("calibration counts 5 runs", cal["n_fresh_runs"] == 5)
    check("segs_per_min ≈ 10.4", abs(cal["segs_per_min"] - 88 / 8.433) < 0.1)
    check("transcription_realtime ≈ 0.79", abs(cal["transcription_realtime"] - 400.0 / 506.0) < 0.01)
    check("selection_ratio ≈ 2/3", abs(cal["selection_ratio"] - 2.0 / 3.0) < 0.01)
    # est now calibrated: segs_per_min ≈ 10.4 → still 6 chunks/17 calls
    est = estimate_pipeline(8.43, metrics_path=metrics)
    check("calibrated flag true", est["calibrated"] is True)
    check("calibrated 17 calls", est["est_calls"] == 17)


def test_calibration_ignores_rerun_zero_calls():
    tmp = Path(tempfile.mkdtemp())
    metrics = tmp / "m.jsonl"
    record_metrics({
        "completed": True, "llm_calls": 0, "num_segments": 88,
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


def test_estimate_upload_missing_duration():
    r = client.post("/estimate", data={"source_type": "upload"})
    body = r.json()
    check("upload no-duration 200", r.status_code == 200)
    check("upload no-duration available=false", body.get("available") is False)


def test_estimate_bad_source_type_400():
    r = client.post("/estimate", data={"source_type": "ftp"})
    check("bad source_type 400", r.status_code == 400)


if __name__ == "__main__":
    test_estimate_baseline_matches_observed()
    test_estimate_long_lecture_bounded()
    test_estimate_segments_override()
    test_estimate_no_calibration_uses_defaults()
    test_calibration_fits_from_fresh_runs()
    test_calibration_ignores_rerun_zero_calls()
    test_recalibrate_cli_prints()
    test_estimate_youtube_success()
    test_estimate_youtube_probe_failure_soft()
    test_estimate_invalid_youtube_url_400()
    test_estimate_gdrive_soft_fail()
    test_estimate_upload_with_duration()
    test_estimate_upload_missing_duration()
    test_estimate_bad_source_type_400()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED > 0 else 0)
