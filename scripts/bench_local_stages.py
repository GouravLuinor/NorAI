"""
scripts/bench_local_stages.py — CPU / RAM / disk cost of the pipeline's LOCAL
stages (no Gemini calls): ingest (yt-dlp download + ffmpeg audio), frame
extraction, scene detection, transcript chunking.

Each stage runs in a fresh spawned process so peak RSS is per stage, not
cumulative. CPU includes child processes (ffmpeg, yt-dlp's merger).

    venv/bin/python scripts/bench_local_stages.py <youtube-url|video-file> --out <dir> [--transcript <json>]

`--transcript` (an existing lecture's transcripts/<id>.json) adds the chunking
stage. Prints one JSON object (also written to <out>/bench.json); `--out` is
scratch and can be deleted after.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _stage(name: str, args: dict) -> dict:
    if name == "ingest":
        from ingest.ingest import process_source
        r = process_source(args["source"], output_dir=args["out"])
        return {"video_path": r["video_path"], "audio_path": r["audio_path"],
                "duration": r["metadata"].get("duration")}
    if name == "frames":
        from visual.extract_frames import extract_frames
        r = extract_frames(args["video_path"], str(Path(args["out"]) / "screenshots" / "raw"))
        return {"frames": r["frames_saved"], "metadata_file": r["metadata_file"]}
    if name == "scenes":
        from visual.scene_detector import detect_scenes
        kf = Path(args["out"]) / "screenshots" / "keyframes"
        detect_scenes(args["metadata_file"], str(kf))
        return {"keyframes": len(json.loads((kf / "metadata.json").read_text()))}
    if name == "chunking":
        from chunking.chunk import chunk_transcript
        r = chunk_transcript(args["transcript"], output_dir=args["out"])
        return {"chunks": r.get("num_chunks")}
    raise ValueError(name)


def _child(name: str, args: dict, q) -> None:
    base = resource.getrusage(resource.RUSAGE_SELF)
    base_rss_kb = base.ru_maxrss  # interpreter + imports already done by spawn
    t0 = time.perf_counter()
    try:
        out = _stage(name, args)
        err = None
    except Exception as e:  # noqa: BLE001
        out, err = {}, f"{type(e).__name__}: {e}"
    wall = time.perf_counter() - t0
    me = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    q.put({
        "stage": name,
        "wall_s": round(wall, 2),
        "cpu_s": round(me.ru_utime + me.ru_stime - base.ru_utime - base.ru_stime, 2),
        "child_cpu_s": round(kids.ru_utime + kids.ru_stime, 2),
        "peak_rss_mb": round(me.ru_maxrss / 1024, 1),
        "start_rss_mb": round(base_rss_kb / 1024, 1),
        "child_peak_rss_mb": round(kids.ru_maxrss / 1024, 1),
        "error": err,
        **out,
    })


def run(name: str, args: dict) -> dict:
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_child, args=(name, args, q))
    p.start()
    res = q.get()
    p.join()
    return res


def _du_mb(p: Path) -> float:
    if p.is_file():
        return round(p.stat().st_size / 1e6, 2)
    return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6, 2) if p.exists() else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", required=True)
    ap.add_argument("--transcript")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    stages = [run("ingest", {"source": a.source, "out": str(out)})]
    ing = stages[0]
    if ing["error"]:
        print(json.dumps({"stages": stages}, indent=2))
        sys.exit(1)
    stages.append(run("frames", {"video_path": ing["video_path"], "out": str(out)}))
    stages.append(run("scenes", {"metadata_file": stages[-1]["metadata_file"], "out": str(out)}))
    if a.transcript:
        stages.append(run("chunking", {"transcript": a.transcript, "out": str(out)}))

    disk = {k: _du_mb(out / k) for k in ("videos", "audio", "screenshots/raw", "screenshots/keyframes")}
    report = json.dumps({"source": a.source, "duration_s": ing.get("duration"),
                         "stages": stages, "disk_mb": disk}, indent=2)
    (out / "bench.json").write_text(report)  # stdout also carries yt-dlp's progress lines
    print(report)


if __name__ == "__main__":
    main()
