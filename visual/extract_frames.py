import json
import logging
from pathlib import Path

import cv2


# Logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Constants


FRAME_INTERVAL_SECONDS = 8



# Frame Extraction


def extract_frames(
    video_path,
    output_dir,
    interval_seconds=FRAME_INTERVAL_SECONDS
):
    """
    Extract one frame every N seconds.

    Also creates metadata.json
    containing timestamps and paths.
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

    cap = cv2.VideoCapture(
        str(video_path)
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video: "
            f"{video_path}"
        )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    total_frames = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    duration = total_frames / fps

    logger.info(
        f"Video FPS: {fps:.2f}"
    )

    logger.info(
        f"Duration: {duration:.2f}s"
    )

    logger.info(
        f"Frame interval: "
        f"{interval_seconds}s"
    )

    metadata = []

    saved_count = 0
    current_time = 0

    while current_time < duration:

        cap.set(
            cv2.CAP_PROP_POS_MSEC,
            current_time * 1000
        )

        success, frame = cap.read()

        if not success:

            logger.warning(
                f"Failed at "
                f"{current_time:.2f}s"
            )

            current_time += (
                interval_seconds
            )

            continue

        filename = (
            f"frame_"
            f"{int(current_time)}.jpg"
        )

        output_path = (
            output_dir /
            filename
        )

        cv2.imwrite(
            str(output_path),
            frame
        )

        metadata.append(
            {
                "timestamp":
                    round(
                        current_time,
                        2
                    ),

                "image_path":
                    str(output_path)
            }
        )

        saved_count += 1

        current_time += (
            interval_seconds
        )

    cap.release()

    metadata_path = (
        output_dir /
        "metadata.json"
    )

    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=4
        )

    logger.info(
        f"Saved "
        f"{saved_count} frames."
    )

    logger.info(
        f"Metadata saved: "
        f"{metadata_path}"
    )

    return {
        "frames_saved":
            saved_count,

        "duration":
            duration,

        "metadata_file":
            str(metadata_path)
    }


# Example Usage


if __name__ == "__main__":

    VIDEO_PATH = (
        "outputs/videos/"
        "ciHThtTVNto_h264.mp4"
    )

    OUTPUT_DIR = (
        "outputs/screenshots/raw"
    )

    result = extract_frames(
        video_path=VIDEO_PATH,
        output_dir=OUTPUT_DIR
    )

    print(
        json.dumps(
            result,
            indent=4
        )
    )