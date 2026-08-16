import json
import logging
import subprocess
from pathlib import Path
import cv2
import ffmpeg

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

try:
    from config import MAX_FRAME_HEIGHT
except ImportError:
    MAX_FRAME_HEIGHT = 720

FRAME_INTERVAL_SECONDS = 8


def _extract_frames_ffmpeg(
    video_path: Path,
    output_dir: Path,
    interval_seconds: float = FRAME_INTERVAL_SECONDS,
    max_height: int = MAX_FRAME_HEIGHT
) -> dict:
    """
    Bulletproof FFmpeg fallback frame extractor for videos with codecs
    unsupported by OpenCV (such as AV1, VP9, or custom WebM streams).
    """
    logger.info("Using FFmpeg native frame extraction fallback...")
    try:
        probe = ffmpeg.probe(str(video_path))
        duration = float(probe.get("format", {}).get("duration", 0.0))
    except Exception:
        duration = 0.0

    output_pattern = str(output_dir / "frame_%04d.jpg")
    vf_filter = f"fps=1/{interval_seconds}"
    if max_height:
        vf_filter += f",scale=-1:{max_height}"

    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", vf_filter,
        "-q:v", "2",
        output_pattern
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        logger.error(f"FFmpeg frame extraction failed: {e}")
        raise

    metadata = []
    saved_files = sorted(output_dir.glob("frame_*.jpg"))
    for idx, fpath in enumerate(saved_files):
        ts = round(idx * interval_seconds, 2)
        metadata.append({
            "timestamp": ts,
            "image_path": str(fpath)
        })

    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    logger.info(f"FFmpeg saved {len(saved_files)} frames. Metadata: {metadata_path}")
    return {
        "frames_saved": len(saved_files),
        "duration": duration,
        "metadata_file": str(metadata_path)
    }


def extract_frames(
    video_path,
    output_dir,
    interval_seconds=FRAME_INTERVAL_SECONDS,
    max_height=MAX_FRAME_HEIGHT
):
    """
    Extract one frame every N seconds.
    First tries OpenCV; if OpenCV cannot decode frames (e.g. AV1/VP9 codecs),
    automatically falls back to native FFmpeg extraction.

    Also creates metadata.json containing timestamps and paths.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        logger.warning(f"OpenCV could not open {video_path}, using FFmpeg fallback.")
        return _extract_frames_ffmpeg(video_path, output_dir, interval_seconds, max_height)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = (total_frames / fps) if fps > 0 else 0.0

    metadata = []
    saved_count = 0
    current_time = 0.0

    try:
        while duration > 0 and current_time < duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
            success, frame = cap.read()

            if not success or frame is None:
                current_time += interval_seconds
                continue

            if max_height and frame.shape[0] > max_height:
                scale = float(max_height) / frame.shape[0]
                new_w = int(round(frame.shape[1] * scale))
                frame = cv2.resize(frame, (new_w, max_height), interpolation=cv2.INTER_AREA)

            filename = f"frame_{int(current_time)}.jpg"
            output_path = output_dir / filename
            cv2.imwrite(str(output_path), frame)

            metadata.append({
                "timestamp": round(current_time, 2),
                "image_path": str(output_path)
            })
            saved_count += 1
            current_time += interval_seconds
    finally:
        cap.release()

    # If OpenCV failed to save any frames (common with AV1/unsupported codecs), trigger FFmpeg fallback
    if saved_count == 0:
        logger.warning("OpenCV extracted 0 frames (unsupported codec in OpenCV). Falling back to FFmpeg...")
        return _extract_frames_ffmpeg(video_path, output_dir, interval_seconds, max_height)

    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    logger.info(f"Saved {saved_count} frames. Metadata saved: {metadata_path}")

    return {
        "frames_saved": saved_count,
        "duration": duration,
        "metadata_file": str(metadata_path)
    }


if __name__ == "__main__":
    VIDEO_PATH = "outputs/videos/ciHThtTVNto.mp4"
    OUTPUT_DIR = "outputs/screenshots/raw"
    result = extract_frames(video_path=VIDEO_PATH, output_dir=OUTPUT_DIR)
    print(json.dumps(result, indent=4))