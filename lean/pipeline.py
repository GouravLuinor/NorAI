"""
lean/pipeline.py — the lean pipeline's content stages (NORAI_PIPELINE=lean).

    transcription (compact lines) ─┐
      → local chunking             ├→ structure (1 call) → chapters (1 call each)
    frames → scene detection ──────┘                      → notes.md

Called by backend/orchestrator.run_pipeline between ingestion and the tutor
index; ingestion, duration limits, metering and cleanup stay there.

CLI for A/B runs (outside the job queue and DB, into a fresh dir):
    # full run from a source URL/file (real Gemini calls: ~1 + 1 + chapters)
    venv/bin/python -m lean.pipeline --source <url|file> --out outputs/lean-<name>
    # reuse an existing lecture's transcript + keyframes (structure + chapters only)
    venv/bin/python -m lean.pipeline --reuse outputs/<lecture-id> --out outputs/lean-<name>
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from chunking.chunk import chunk_transcript
from config import NORAI_TRANSCRIPTION_BACKEND
from lean.chapters import generate_chapters
from lean.structure import generate_outline
from notes.notes_generator import write_combined_notes

logger = logging.getLogger(__name__)


def _noop(*_a, **_k):
    return None


def transcribe(audio_path: str, meta_path: str, out: str) -> str:
    if NORAI_TRANSCRIPTION_BACKEND.lower() in ("gemini", "api", "cloud"):
        from transcription.gemini_transcriber import transcribe_with_gemini
        tr = transcribe_with_gemini(audio_path, meta_path, output_dir=out, compact=True)
    else:
        from transcription.transcribe import transcribe_audio
        tr = transcribe_audio(audio_path, meta_path, output_dir=out)
    return tr["transcript_json_path"]


def extract_keyframes(video_path: str, out: str) -> str:
    from visual.extract_frames import extract_frames
    from visual.scene_detector import detect_scenes

    shots = Path(out) / "screenshots"
    fe = extract_frames(video_path, str(shots / "raw"))
    detect_scenes(fe["metadata_file"], str(shots / "keyframes"))
    return str(shots / "keyframes" / "metadata.json")


def run_content_stages(out: str, transcript_path: str, keyframes_meta: str | None, *,
                       source_title: str = "", duration_sec: float | None = None,
                       report=_noop, check_cancel=_noop, metrics: dict | None = None) -> dict:
    """Chunk → structure → chapters → notes.md, from an existing transcript."""
    metrics = metrics if metrics is not None else {}
    stage_seconds = metrics.setdefault("stage_seconds", {})

    report("chunking", "Chunking transcript…", 30)
    check_cancel()
    ch = chunk_transcript(transcript_path, output_dir=out)
    metrics["num_chunks"] = ch.get("num_chunks")
    metrics["segments_per_chunk"] = ch.get("segments_per_chunk")

    report("outline", "Mapping the lecture's chapters…", 36)
    check_cancel()
    t0 = time.perf_counter()
    outline = generate_outline(ch["chunks_path"], out, source_title=source_title, duration_sec=duration_sec)
    stage_seconds["outline"] = round(time.perf_counter() - t0, 2)
    metrics["num_chapters"] = len(outline["chapters"])
    metrics["title"] = outline["lecture_title"]

    report("chapter_artifacts", "Writing notes, revision & assessment…", 45)
    check_cancel()
    t0 = time.perf_counter()
    result = generate_chapters(outline, ch["chunks_path"], transcript_path, keyframes_meta, out)
    stage_seconds["chapter_artifacts"] = round(time.perf_counter() - t0, 2)
    write_combined_notes(Path(out) / "notes")
    return {"outline": outline, **result}


def run_lean_stages(out: str, video_path: str, audio_path: str, meta_path: str, *,
                    report=_noop, check_cancel=_noop, metrics: dict | None = None) -> dict:
    """Transcription ∥ keyframes, then the content stages. Returns
    {"outline", "num_chapters", "degraded"}."""
    metrics = metrics if metrics is not None else {}
    stage_seconds = metrics.setdefault("stage_seconds", {})
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))

    def _text():
        report("transcription", "Transcribing lecture…", 8)
        check_cancel()
        t0 = time.perf_counter()
        path = transcribe(audio_path, meta_path, out)
        stage_seconds["transcription"] = round(time.perf_counter() - t0, 2)
        return path

    def _visual():
        t0 = time.perf_counter()
        path = extract_keyframes(video_path, out)
        stage_seconds["keyframes"] = round(time.perf_counter() - t0, 2)
        return path

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_text, fut_visual = pool.submit(_text), pool.submit(_visual)
        transcript_path = fut_text.result()
        try:
            keyframes_meta = fut_visual.result()
        except Exception as e:  # noqa: BLE001 — notes without screenshots beat no notes
            logger.error("Keyframe extraction failed (continuing without frames): %s", e)
            keyframes_meta = None

    try:
        metrics["num_segments"] = len(json.loads(Path(transcript_path).read_text(encoding="utf-8"))["segments"])
    except Exception:  # noqa: BLE001
        pass

    return run_content_stages(
        out, transcript_path, keyframes_meta,
        source_title=meta.get("title", ""), duration_sec=meta.get("duration"),
        report=report, check_cancel=check_cancel, metrics=metrics,
    )


# ── CLI (A/B runs) ────────────────────────────────────────────────────────────

def _copy_inputs(src: Path, out: Path) -> tuple[str, str | None, dict]:
    """Copy an existing lecture's transcript + keyframes into `out`, rewriting
    keyframe paths so the new dir is self-contained."""
    transcript = sorted((src / "transcripts").glob("*.json"))[0]
    (out / "transcripts").mkdir(parents=True, exist_ok=True)
    t_dst = out / "transcripts" / transcript.name
    shutil.copy2(transcript, t_dst)
    for txt in (src / "transcripts").glob("*.txt"):
        shutil.copy2(txt, out / "transcripts" / txt.name)

    kf_src = src / "screenshots" / "keyframes"
    kf_meta = None
    if (kf_src / "metadata.json").is_file():
        kf_dst = out / "screenshots" / "keyframes"
        shutil.copytree(kf_src, kf_dst, dirs_exist_ok=True)
        frames = json.loads((kf_src / "metadata.json").read_text(encoding="utf-8"))
        for f in frames:
            f["image_path"] = str(kf_dst / Path(f["image_path"]).name)
        (kf_dst / "metadata.json").write_text(json.dumps(frames, indent=4), encoding="utf-8")
        kf_meta = str(kf_dst / "metadata.json")
    source = json.loads(t_dst.read_text(encoding="utf-8")).get("source", {})
    return str(t_dst), kf_meta, source


def main() -> None:
    from backend.orchestrator import cleanup_lecture_dir
    from backend.usage_ledger import diff_usage, snapshot_usage

    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--source", help="YouTube URL or local video file")
    g.add_argument("--reuse", help="existing lecture dir: reuse its transcript + keyframes")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-index", action="store_true", help="skip the tutor index (embeddings)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    before, t0 = snapshot_usage(), time.perf_counter()
    metrics: dict = {}
    try:
        if args.reuse:
            transcript, kf_meta, source = _copy_inputs(Path(args.reuse), out)
            result = run_content_stages(
                str(out), transcript, kf_meta, source_title=source.get("title", ""),
                duration_sec=source.get("duration"), metrics=metrics,
            )
        else:
            from ingest.ingest import process_source
            ing = process_source(args.source, output_dir=str(out))
            result = run_lean_stages(str(out), ing["video_path"], ing["audio_path"],
                                     ing["metadata_path"], metrics=metrics)
        if not args.no_index:
            from tutor.indexing import build_lecture_index
            build_lecture_index(str(out))
    finally:
        cleanup_lecture_dir(out)

    usage = diff_usage(before)
    print(json.dumps({
        "out": str(out),
        "chapters": result["num_chapters"],
        "degraded": result["degraded"],
        "seconds": round(time.perf_counter() - t0, 1),
        "stage_seconds": metrics.get("stage_seconds"),
        "usage": usage,
        "total_calls": sum(u.get("calls", 0) for u in usage),
        "total_cost_usd": round(sum(u.get("cost_usd", 0.0) for u in usage), 5),
    }, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
