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


def map_screenshots_to_chunks(
    chunks_json_path,
    screenshots_metadata_path
):
    """
    Assign screenshots
    to their corresponding chunks.
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

        chunk_screenshots = []

        for screenshot in screenshots:

            timestamp = (
                screenshot[
                    "timestamp"
                ]
            )

            if (
                chunk["start"]
                <= timestamp
                <= chunk["end"]
            ):

                chunk_screenshots.append(
                    screenshot
                )

        mapped_chunks.append(
            {
                "chunk_id":
                    chunk[
                        "chunk_id"
                    ],

                "start":
                    chunk[
                        "start"
                    ],

                "end":
                    chunk[
                        "end"
                    ],

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