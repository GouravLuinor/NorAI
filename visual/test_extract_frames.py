"""
test_extract_frames.py — keyframe-only frame extraction (visual/extract_frames.py).

Builds two tiny synthetic videos with ffmpeg (needs ffmpeg on PATH; no API calls):
  - a 2 s GOP: every keyframe is kept, with its real timestamp;
  - a single keyframe: too sparse, so it falls back to OpenCV seeks every 8 s.

Run:
    python visual/test_extract_frames.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import visual.extract_frames as ef  # noqa: E402


def _make_video(path: Path, seconds: int, gop_frames: int) -> None:
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=160x90:rate=25",
        "-c:v", "libx264", "-g", str(gop_frames), "-keyint_min", str(gop_frames),
        "-sc_threshold", "0", "-pix_fmt", "yuv420p", str(path),
    ], check=True)


def test_keyframes_kept_with_timestamps():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        video = td / "gop2.mp4"
        _make_video(video, seconds=30, gop_frames=50)
        r = ef.extract_frames(video, td / "raw")
        meta = json.loads(Path(r["metadata_file"]).read_text())
        ts = [m["timestamp"] for m in meta]
        assert ts == [float(t) for t in range(0, 30, 2)], ts
        for m in meta:
            p = Path(m["image_path"])
            assert p.is_file() and p.name == f"frame_{int(m['timestamp'])}.jpg", p
        assert not list((td / "raw").glob("kf_*.jpg")), "temp names left behind"


def test_sparse_keyframes_fall_back_to_seeks():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        video = td / "gop_inf.mp4"
        _make_video(video, seconds=40, gop_frames=10_000)
        r = ef.extract_frames(video, td / "raw")
        ts = [m["timestamp"] for m in json.loads(Path(r["metadata_file"]).read_text())]
        assert ts == [0.0, 8.0, 16.0, 24.0, 32.0], ts
        assert not list((td / "raw").glob("kf_*.jpg")), "temp frames not cleaned up"


if __name__ == "__main__":
    test_keyframes_kept_with_timestamps()
    test_sparse_keyframes_fall_back_to_seeks()
    print("test_extract_frames: 2/2 passed")
