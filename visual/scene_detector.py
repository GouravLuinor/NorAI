import json
import shutil
import logging
from pathlib import Path

import cv2
import numpy as np


# Logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Constants


SCENE_THRESHOLD = 30

MAX_GAP_SECONDS = 90



# Metadata Loader


def load_metadata(
    metadata_path
):
    """
    Load frame metadata.
    """

    metadata_path = Path(
        metadata_path
    )

    with open(
        metadata_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



# Difference Calculator


def compute_difference(
    image1_path,
    image2_path
):
    """
    Compute average pixel difference
    between two images.
    """

    img1 = cv2.imread(
        str(image1_path)
    )

    img2 = cv2.imread(
        str(image2_path)
    )

    if img1 is None:
        raise ValueError(
            f"Could not read: "
            f"{image1_path}"
        )

    if img2 is None:
        raise ValueError(
            f"Could not read: "
            f"{image2_path}"
        )

    gray1 = cv2.cvtColor(
        img1,
        cv2.COLOR_BGR2GRAY
    )

    gray2 = cv2.cvtColor(
        img2,
        cv2.COLOR_BGR2GRAY
    )

    diff = cv2.absdiff(
        gray1,
        gray2
    )

    score = float(
        np.mean(diff)
    )

    return score



# Scene Detection


def detect_scenes(
    metadata_path,
    output_dir,
    threshold=SCENE_THRESHOLD,
    max_gap_seconds=MAX_GAP_SECONDS
):
    """
    Detect scene changes and keep
    only important screenshots.
    """

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    frames = load_metadata(
        metadata_path
    )

    if not frames:
        raise ValueError(
            "No frames found."
        )

    logger.info(
        f"Loaded "
        f"{len(frames)} frames."
    )

    selected_frames = []


    # Always keep first frame


    first_frame = frames[0]

    src = Path(
        first_frame["image_path"]
    )

    dst = (
        output_dir /
        src.name
    )

    shutil.copy2(
        src,
        dst
    )

    selected_frames.append(
        {
            "timestamp":
                first_frame[
                    "timestamp"
                ],

            "image_path":
                str(dst),

            "difference":
                0.0
        }
    )

    last_saved_frame = (
        first_frame
    )

    last_saved_timestamp = (
        first_frame[
            "timestamp"
        ]
    )


    # Process remaining frames


    for frame in frames[1:]:

        score = (
            compute_difference(
                last_saved_frame[
                    "image_path"
                ],

                frame[
                    "image_path"
                ]
            )
        )

        time_gap = (
            frame["timestamp"]
            -
            last_saved_timestamp
        )

        keep_frame = (
            score > threshold
            or
            time_gap >= max_gap_seconds
        )

        if keep_frame:

            src = Path(
                frame["image_path"]
            )

            dst = (
                output_dir /
                src.name
            )

            shutil.copy2(
                src,
                dst
            )

            selected_frames.append(
                {
                    "timestamp":
                        frame[
                            "timestamp"
                        ],

                    "image_path":
                        str(dst),

                    "difference":
                        round(
                            score,
                            4
                        )
                }
            )

            last_saved_frame = (
                frame
            )

            last_saved_timestamp = (
                frame[
                    "timestamp"
                ]
            )


    # Save metadata


    metadata_output = (
        output_dir /
        "metadata.json"
    )

    with open(
        metadata_output,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            selected_frames,
            f,
            indent=4
        )

    logger.info(
        f"Selected "
        f"{len(selected_frames)} "
        f"keyframes."
    )

    logger.info(
        f"Metadata saved: "
        f"{metadata_output}"
    )

    return selected_frames



# Example Usage


if __name__ == "__main__":

    selected = detect_scenes(
        metadata_path=
        "outputs/screenshots/raw/metadata.json",

        output_dir=
        "outputs/screenshots/keyframes"
    )

    print(
        f"\nSelected "
        f"{len(selected)} "
        f"keyframes."
    )