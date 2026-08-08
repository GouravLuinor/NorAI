"""
backend/estimator.py — Pre-flight cost/time estimator + self-calibration loop.

P1.8: Estimates the number of Gemini calls and wall-clock minutes a lecture will
consume BEFORE the pipeline runs, then re-fits its heuristics from every real
pipeline run so the estimate tightens over time.

Feedback loop
-------------
1. POST /estimate probes the source duration cheaply (yt-dlp metadata-only for
   YouTube, ~2s; browser-reported duration for uploads) and calls
   estimate_pipeline().
2. orchestrator.run_pipeline() snapshots the LLM/embed counters, runs the full
   pipeline, and appends one JSONL entry of actuals to config.METRICS_FILE via
   record_metrics().
3. estimate_pipeline() consults load_calibration(), which medians recent FRESH
   runs (completed, non-zero call count) to re-fit: segs_per_min,
   transcription_realtime, sec_per_call, sec_per_embed_batch, and the
   screenshot-selection Pass-2 ratio.
4. `python -m backend.estimator --recalibrate` prints the fitted constants plus
   prediction-vs-actual error so drift is visible.

Model (mirrors chunking/chunk.py + notes/outline_generator.py)
---------------------------------------------------------------
  segments      = ceil(duration_min * segs_per_min)
  spc           = adaptive_segments_per_chunk(segments)
  chunks        = ceil(segments / spc)
  chapters      = min(8, max(3, chunks // 3))        # outline generator formula
  selection     = round(selection_ratio * chapters)  # screenshot-selection Pass-2
  calls         = chunks + 1 + 2*chapters + selection + embed_batches
                  # 1 outline + chapters visual + chapters artifacts
  time_sec      = download_sec
                  + transcription_realtime * duration_sec
                  + calls * sec_per_call
                  + embed_batches * sec_per_embed_batch
                  + overhead_sec

Call mix validated against the P1.8 baseline run (8.43 min, 88 segments, 6
chunks, 3 chapters): 6 + 1 + 3 + 2 + 3 + 2 = 17 observed vs 17 predicted.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

from config import (
    METRICS_FILE,
    DEFAULT_SEGS_PER_MIN,
    MAX_FREE_DURATION_MIN,
)
from chunking.chunk import adaptive_segments_per_chunk

# ── Default heuristics (pre-calibration) ──────────────────────────────────────
DEFAULT_TRANSCRIPTION_REALTIME = 1.0   # whisper-small wall-clock / audio
DEFAULT_SEC_PER_CALL = 9.0             # RPM spacing (5s @12rpm) + latency
DEFAULT_SEC_PER_EMBED_BATCH = 3.0      # one batchEmbedContents call
DEFAULT_SELECTION_RATIO = 0.7          # Pass-2 screenshot-selection calls / chapter
DEFAULT_DOWNLOAD_SEC = 30.0            # YouTube download + audio extraction
DEFAULT_OVERHEAD_SEC = 90.0            # frame/scene/mapping/build/cleanup
MIN_CALIBRATION_SAMPLES = 5            # below this, keep defaults

FREE_TRIAL_MIN = MAX_FREE_DURATION_MIN


def _median(values):
    vals = [v for v in values if v is not None and v == v]  # drop None/NaN
    return statistics.median(vals) if vals else None


def load_calibration(metrics_path=None) -> dict:
    """Median-fit heuristics from the metrics file's recent fresh runs.

    A "fresh" run is completed with > 0 LLM calls (cache-only re-runs would
    report ~0 calls and skew the timing/call fits). Returns a dict of fitted
    values, with None entries meaning "not enough data — keep default".
    """
    metrics_path = Path(metrics_path or METRICS_FILE)
    entries = []
    if metrics_path.exists():
        try:
            with open(metrics_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            entries = []

    fresh = [e for e in entries if e.get("completed") and (e.get("llm_calls") or 0) > 0]
    n_fresh = len(fresh)

    segs_per_min = _median(
        e["num_segments"] / (e["duration_sec"] / 60.0)
        for e in fresh if e.get("num_segments") and e.get("duration_sec")
    )
    transcription_realtime = _median(
        e["stage_seconds"]["transcription"] / e["duration_sec"]
        for e in fresh
        if (e.get("stage_seconds") or {}).get("transcription")
        and e.get("duration_sec")
    )
    # Non-transcription time per LLM call (lumps download, LLM RPM, embeds, IO).
    sec_per_call = _median(
        (
            e["stage_seconds"]["pipeline"]
            - (e.get("stage_seconds") or {}).get("transcription", 0.0)
            - DEFAULT_DOWNLOAD_SEC
        ) / e["llm_calls"]
        for e in fresh
        if (e.get("stage_seconds") or {}).get("pipeline") and e["llm_calls"]
    )
    sec_per_embed_batch = _median(
        (
            (e.get("stage_seconds") or {}).get("pipeline", 0.0)
            - (e.get("stage_seconds") or {}).get("transcription", 0.0)
            - DEFAULT_DOWNLOAD_SEC
            - e["llm_calls"] * (sec_per_call or DEFAULT_SEC_PER_CALL)
        ) / e["embed_batches"]
        for e in fresh
        if e.get("embed_batches")
        and (e.get("stage_seconds") or {}).get("pipeline")
    )
    # Back out Pass-2 selection calls from the recorded mix.
    selection_ratio = _median(
        (
            e["llm_calls"] - e["num_chunks"] - 1 - 2 * e["num_chapters"]
            - e.get("embed_batches", 0)
        ) / e["num_chapters"]
        for e in fresh
        if e.get("num_chunks") and e.get("num_chapters") and e["num_chapters"] > 0
    )

    return {
        "n_fresh_runs": n_fresh,
        "segs_per_min": segs_per_min,
        "transcription_realtime": transcription_realtime,
        "sec_per_call": sec_per_call,
        "sec_per_embed_batch": sec_per_embed_batch,
        "selection_ratio": selection_ratio,
    }


def estimate_pipeline(
    duration_min: float,
    source_type: str = "youtube",
    segments: int | None = None,
    metrics_path=None,
    calibration: dict | None = None,
) -> dict:
    """Estimate calls + time for a lecture of `duration_min` minutes.

    Uses calibrated heuristics when enough real runs exist, else defaults.
    `segments` overrides the segment estimate (used by the orchestrator once
    the real transcript count is known).
    """
    cal = calibration if calibration is not None else load_calibration(metrics_path)
    n_runs = cal.get("n_fresh_runs", 0)
    enough = n_runs >= MIN_CALIBRATION_SAMPLES

    def pick(default, fitted):
        return fitted if (enough and fitted) else default

    segs_per_min = pick(DEFAULT_SEGS_PER_MIN, cal.get("segs_per_min"))
    transcription_realtime = pick(DEFAULT_TRANSCRIPTION_REALTIME, cal.get("transcription_realtime"))
    sec_per_call = pick(DEFAULT_SEC_PER_CALL, cal.get("sec_per_call"))
    sec_per_embed_batch = pick(DEFAULT_SEC_PER_EMBED_BATCH, cal.get("sec_per_embed_batch"))
    selection_ratio = pick(DEFAULT_SELECTION_RATIO, cal.get("selection_ratio"))

    duration_sec = max(0.0, duration_min * 60.0)
    if segments is None:
        segments = math.ceil(duration_min * segs_per_min) if duration_min else 0
    spc = adaptive_segments_per_chunk(max(segments, 0))
    chunks = math.ceil(max(segments, 0) / spc) if spc else 0
    chapters = min(8, max(3, chunks // 3)) if chunks else 0
    embed_batches = 2  # notes index + screenshot index
    selection = round(selection_ratio * chapters) if chapters else 0
    llm_calls = chunks + 1 + 2 * chapters + selection + embed_batches if chunks else 0

    time_sec = (
        DEFAULT_DOWNLOAD_SEC
        + transcription_realtime * duration_sec
        + llm_calls * sec_per_call
        + embed_batches * sec_per_embed_batch
        + DEFAULT_OVERHEAD_SEC
    )

    return {
        "duration_min": round(duration_min, 2),
        "source_type": source_type,
        "segments": segments,
        "segments_per_chunk": spc,
        "estimated_chunks": chunks,
        "estimated_chapters": chapters,
        "est_calls": llm_calls,
        "est_embed_batches": embed_batches,
        "est_time_min": max(1, math.ceil(time_sec / 60.0)),
        "free_trial_ok": duration_min <= FREE_TRIAL_MIN,
        "free_trial_min": FREE_TRIAL_MIN,
        "calibrated": enough,
        "n_calibration_runs": n_runs,
    }


def record_metrics(entry: dict, metrics_path=None) -> None:
    """Append one run's actuals (JSONL) to the metrics file for calibration."""
    metrics_path = Path(metrics_path or METRICS_FILE)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def recalibrate(metrics_path=None) -> dict:
    """Fit + report calibration quality. Returns the fitted constants."""
    cal = load_calibration(metrics_path)
    print(f"Fitted from {cal['n_fresh_runs']} fresh pipeline runs "
          f"(need ≥ {MIN_CALIBRATION_SAMPLES}):")
    for key, value in cal.items():
        if key == "n_fresh_runs":
            continue
        print(f"  {key:24s} {value!r}" if value else f"  {key:24s} (insufficient data)")
    if cal["n_fresh_runs"]:
        _report_prediction_error(metrics_path)
    return cal


def _report_prediction_error(metrics_path=None):
    """Re-derive the estimate for each fresh run and compare to actuals."""
    metrics_path = Path(metrics_path or METRICS_FILE)
    if not metrics_path.exists():
        return
    errors = []
    with open(metrics_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not e.get("completed") or (e.get("llm_calls") or 0) <= 0:
                continue
            est = estimate_pipeline(
                e["duration_sec"] / 60.0,
                source_type=e.get("source_type", "youtube"),
                segments=e.get("num_segments"),
                metrics_path=metrics_path,
            )
            err_calls = e["llm_calls"] - est["est_calls"]
            err_time = e["stage_seconds"].get("pipeline", 0) / 60.0 - est["est_time_min"]
            errors.append((e.get("lecture_id", "?"), err_calls, err_time))
    if errors:
        call_mae = statistics.mean(abs(c) for _, c, _ in errors)
        time_mae = statistics.mean(abs(t) for _, _, t in errors)
        print(f"Prediction error over {len(errors)} fresh runs:")
        print(f"  calls MAE = {call_mae:.2f}   time MAE = {time_mae:.2f} min")
        for lid, ec, et in errors:
            print(f"    {lid[:8]}  calls err {ec:+.0f}  time err {et:+.1f} min")


if __name__ == "__main__":
    metrics_arg = None
    if "--metrics" in sys.argv:
        i = sys.argv.index("--metrics")
        metrics_arg = sys.argv[i + 1]
    if "--recalibrate" in sys.argv:
        sys.exit(recalibrate(metrics_arg))
    print("Usage: python -m backend.estimator --recalibrate [--metrics <path>]")
