import json
import logging
from pathlib import Path


# Logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Loaders


def load_chunks(
    chunks_json_path
):
    """
    Load chunk file.
    """

    with open(
        chunks_json_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def load_screenshots(
    metadata_path
):
    """
    Load screenshot metadata.
    """

    with open(
        metadata_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# Mapping


FALLBACK_TOLERANCE_SECONDS = 20.0


def map_screenshots_to_chunks(
    chunks_json_path,
    screenshots_metadata_path,
    tolerance_seconds=FALLBACK_TOLERANCE_SECONDS
):
    """
    Assign screenshots to their corresponding chunks.
    If a chunk has no screenshots under strict boundary matching,
    assigns the single nearest keyframe within tolerance_seconds.
    """

    chunk_data = load_chunks(
        chunks_json_path
    )

    screenshots = load_screenshots(
        screenshots_metadata_path
    )

    chunks = chunk_data["chunks"]

    mapped_chunks = []

    for chunk in chunks:

        chunk_start = chunk["start"]
        chunk_end = chunk["end"]
        chunk_screenshots = []

        for screenshot in screenshots:

            timestamp = (
                screenshot[
                    "timestamp"
                ]
            )

            if (
                chunk_start
                <= timestamp
                <= chunk_end
            ):

                chunk_screenshots.append(
                    screenshot
                )

        # Fallback: if no screenshot falls strictly inside [start, end]
        if not chunk_screenshots and screenshots:
            best_candidate = None
            min_dist = float("inf")

            for screenshot in screenshots:
                ts = screenshot["timestamp"]
                if ts < chunk_start:
                    dist = chunk_start - ts
                else:
                    dist = ts - chunk_end

                if dist < min_dist:
                    min_dist = dist
                    best_candidate = screenshot

            if best_candidate is not None and min_dist <= tolerance_seconds:
                logger.info(
                    f"Chunk {chunk['chunk_id']} ({chunk_start:.2f}s-{chunk_end:.2f}s) "
                    f"has 0 strict screenshots. Assigning fallback screenshot at "
                    f"{best_candidate['timestamp']}s (distance: {min_dist:.2f}s <= {tolerance_seconds}s)."
                )
                chunk_screenshots.append(best_candidate)

        mapped_chunks.append(
            {
                "chunk_id":
                    chunk[
                        "chunk_id"
                    ],

                "start":
                    chunk_start,

                "end":
                    chunk_end,

                "screenshots":
                    chunk_screenshots
            }
        )

    logger.info(
        f"Mapped "
        f"{len(screenshots)} screenshots "
        f"across "
        f"{len(chunks)} chunks."
    )

    return mapped_chunks



# Save


def save_mapping(
    mapped_chunks,
    output_path
):
    """
    Save mapping JSON.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            mapped_chunks,
            f,
            indent=4
        )

    logger.info(
        f"Saved mapping: "
        f"{output_path}"
    )


# Main API


def create_chunk_screenshot_mapping(
    chunks_json_path,
    screenshots_metadata_path,
    output_path
):
    """
    Full mapping pipeline.
    """

    mapped_chunks = (
        map_screenshots_to_chunks(
            chunks_json_path,
            screenshots_metadata_path
        )
    )

    save_mapping(
        mapped_chunks,
        output_path
    )

    return mapped_chunks



# Example Usage


if __name__ == "__main__":

    result = (
        create_chunk_screenshot_mapping(
            chunks_json_path=
            "outputs/chunks/ciHThtTVNto_chunks.json",

            screenshots_metadata_path=
            "outputs/screenshots/keyframes/metadata.json",

            output_path=
            "outputs/mappings/chunk_screenshot_mapping.json"
        )
    )

    print(
        f"\nMapped "
        f"{len(result)} chunks."
    )