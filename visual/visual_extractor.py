import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import time
import random
from visual.visual_prompts import (
    VISUAL_PROMPT
)
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Gemini / Gemma Client

load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found."
    )
client = genai.Client(
    api_key=API_KEY
)


# Load Mapping


def load_mapping(
    mapping_path
):
    """
    Load chunk screenshot mapping.
    """

    with open(
        mapping_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



# Upload Images


def upload_images(
    image_paths
):
    """
    Upload screenshots to
    Google AI Studio.
    """

    uploaded_files = []

    for image_path in image_paths:

        logger.info(
            f"Uploading: "
            f"{image_path}"
        )

        file = client.files.upload(
            file=image_path
        )

        uploaded_files.append(
            file
        )

    return uploaded_files



# Visual Analysis


def analyze_chunk_images(
    image_paths
):
    """
    Analyze screenshots belonging
    to a single chunk.
    """

    uploaded_files = upload_images(
        image_paths
    )

    image_listing = []

    for idx, path in enumerate(
        image_paths
    ):

        image_listing.append(
            f"{idx}: "
            f"{Path(path).name}"
        )

    enhanced_prompt = (
        VISUAL_PROMPT
        +
        "\n\n"
        +
        "Screenshot Index Mapping:\n"
        +
        "\n".join(
            image_listing
        )
    )

    for attempt in range(3):

        try:

            response = (
                client.models.generate_content(
                    model=
                    "gemma-4-26b-a4b-it",

                    contents=[
                        *uploaded_files,
                        enhanced_prompt
                    ]
                )
            )

            return response.text

        except Exception as e:

            logger.warning(
                f"Attempt "
                f"{attempt + 1} failed: "
                f"{e}"
            )

            time.sleep(
                5 * (attempt + 1)
            )

    raise RuntimeError(
        "Gemma failed after 3 attempts."
    )

    return response.text



# JSON Cleanup


def parse_response(
    response_text
):
    """
    Parse model JSON safely.
    """

    response_text = (
        response_text
        .replace(
            "```json",
            ""
        )
        .replace(
            "```",
            ""
        )
        .strip()
    )


    response_text = (
        response_text
        .replace(
            "\\",
            "\\\\"
        )
    )

    try:

        visual_object = json.loads(
            response_text
        )

    except json.JSONDecodeError:

        logger.error(
            response_text
        )

        raise

    required_fields = {

        "visual_summary": "",

        "visual_notes": "",

        "ocr_text": "",

        "concepts": [],

        "note_worthy_concepts": [],

        "important_information": [],

        "formulas": [],

        "code_snippets": [],

        "visual_type": "",

        "teaching_stage": "",

        "importance_score": 0,

        "importance_reason": "",

        "include_in_notes": False,

        "selected_image_indices": []
    }

    for key, default in (
        required_fields.items()
    ):

        visual_object.setdefault(
            key,
            default
        )

    return visual_object


def validate_visual_object(
    visual_object
):
    """
    Validate and normalize
    visual object fields.
    """

    score = visual_object.get(
        "importance_score",
        0
    )

    if not isinstance(
        score,
        (int, float)
    ):
        score = 5

    score = max(
        1,
        min(
            int(score),
            10
        )
    )

    visual_object[
        "importance_score"
    ] = score

    return visual_object

# Extract Visual Object


def extract_visual_object(
    chunk_mapping
):
    """
    Create visual object for
    a single chunk.
    """

    screenshots = (
        chunk_mapping[
            "screenshots"
        ]
    )

    if not screenshots:

        logger.warning(
            f"Chunk "
            f"{chunk_mapping['chunk_id']} "
            f"has no screenshots."
        )

        return None

    image_paths = [

        screenshot[
            "image_path"
        ]

        for screenshot
        in screenshots
    ]

    screenshot_timestamps = [

        screenshot[
            "timestamp"
        ]

        for screenshot
        in screenshots
    ]

    MAX_ATTEMPTS = 5

    for attempt in range(
        MAX_ATTEMPTS
    ):

        try:

            logger.info(
                f"Chunk "
                f"{chunk_mapping['chunk_id']} "
                f"attempt "
                f"{attempt + 1}/"
                f"{MAX_ATTEMPTS}"
            )

            response_text = (
                analyze_chunk_images(
                    image_paths
                )
            )

            visual_object = (
                parse_response(
                    response_text
                )
            )

            visual_object = (
                validate_visual_object(
                    visual_object
                )
            )

            break

        except Exception as e:

            logger.warning(
                f"Chunk "
                f"{chunk_mapping['chunk_id']} "
                f"attempt "
                f"{attempt + 1} failed: "
                f"{e}"
            )

    else:

        raise RuntimeError(
            f"Chunk "
            f"{chunk_mapping['chunk_id']} "
            f"failed after "
            f"{MAX_ATTEMPTS} attempts."
        )

    visual_object = (
        validate_visual_object(
            visual_object
        )
    )
    

    # ----------------------------------
    # Source Data
    # ----------------------------------

    visual_object[
        "source_screenshots"
    ] = image_paths

    visual_object[
        "screenshot_timestamps"
    ] = screenshot_timestamps

    # ----------------------------------
    # Chunk Metadata
    # ----------------------------------

    visual_object[
        "chunk_id"
    ] = (
        chunk_mapping[
            "chunk_id"
        ]
    )

    visual_object[
        "start"
    ] = (
        chunk_mapping[
            "start"
        ]
    )

    visual_object[
        "end"
    ] = (
        chunk_mapping[
            "end"
        ]
    )

    visual_object[
        "screenshot_count"
    ] = len(
        screenshots
    )


    visual_object[
        "object_type"
    ] = (
        "visual_object"
    )

    visual_object[
        "generated_by"
    ] = (
        "gemma-4-26b-a4b-it"
    )

    return visual_object


def process_chunk(
    chunk_mapping,
    output_dir
):
    """
    Process one chunk.
    """

    chunk_id = chunk_mapping[
        "chunk_id"
    ]

    try:

        logger.info(
            f"Starting chunk "
            f"{chunk_id}"
        )

        output_file = (
            Path(output_dir)
            /
            f"chunk_{chunk_id}_visual.json"
        )

        if output_file.exists():

            logger.info(
                f"Skipping chunk "
                f"{chunk_id}"
            )

            return True
        
        time.sleep(
            random.uniform(
                0.5,
                2
            )
        )


        visual_object = (
            extract_visual_object(
                chunk_mapping
            )
        )

        if visual_object:

            save_visual_object(
                visual_object,
                output_dir
            )

        logger.info(
            f"Finished chunk "
            f"{chunk_id}"
        )

        return True

    except Exception as e:

        logger.error(
            f"Chunk {chunk_id} failed: "
            f"{e}"
        )

        return False

# Save


def save_visual_object(
    visual_object,
    output_dir
):
    """
    Save visual object.
    """

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    chunk_id = (
        visual_object[
            "chunk_id"
        ]
    )

    output_path = (
        output_dir /
        f"chunk_{chunk_id}_visual.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            visual_object,
            f,
            indent=4,
            ensure_ascii=False,
            sort_keys=False
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )

    return output_path


def process_all_chunks(
    mapping_path,
    output_dir,
    max_workers=7
):
    """
    Process all chunks.
    """

    mapping = load_mapping(
        mapping_path
    )

    logger.info(
        f"Loaded "
        f"{len(mapping)} chunks."
    )

    completed = 0

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        futures = [

            executor.submit(
                process_chunk,
                chunk,
                output_dir
            )

            for chunk
            in mapping
        ]

        for future in as_completed(
            futures
        ):

            future.result()

            completed += 1

            logger.info(
                f"Progress: "
                f"{completed}/"
                f"{len(mapping)}"
            )

    logger.info(
        "Visual extraction complete."
    )


# Example Usage


if __name__ == "__main__":

    process_all_chunks(

        mapping_path=
        "outputs/mappings/"
        "chunk_screenshot_mapping.json",

        output_dir=
        "outputs/visual_objects",

        max_workers=7
    )