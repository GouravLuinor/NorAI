import json
import logging
from pathlib import Path



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Paths


OBJECTS_DIR = (
    Path("outputs/objects")
)

VISUAL_OBJECTS_DIR = (
    Path("outputs/visual_objects")
)

MERGED_OBJECTS_DIR = (
    Path("outputs/merged_objects")
)


# Load JSON


def load_json(
    path
):
    """
    Load JSON file.
    """

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



# Selected Screenshots



def get_selected_screenshots(
    visual_object
):
    """
    Convert image indices
    into image paths.
    """

    selected = []

    indices = visual_object.get(
        "selected_image_indices",
        []
    )

    screenshots = visual_object.get(
        "source_screenshots",
        []
    )

    for idx in indices:

        if idx < len(
            screenshots
        ):

            selected.append(
                screenshots[idx]
            )

    return selected



# Merge Objects


def merge_objects(
    knowledge_object,
    visual_object
):
    """
    Merge transcript and
    visual knowledge.
    """

    concepts = sorted(
        set(
            knowledge_object.get(
                "concepts",
                []
            )
            +
            visual_object.get(
                "concepts",
                []
            )
        )
    )

    important_information = (
        knowledge_object.get(
            "key_points",
            []
        )
        +
        visual_object.get(
            "important_information",
            []
        )
    )

    return {

        "object_type":
            "merged_object",

        "chunk_id":
            knowledge_object[
                "chunk_id"
            ],

        "topic":
            knowledge_object.get(
                "topic"
            ),

        "transcript":
            knowledge_object.get(
                "transcript"
            ),

        "lecture_notes":
            knowledge_object.get(
                "lecture_notes"
            ),

        "visual_notes":
            visual_object.get(
                "visual_notes"
            ),

        "key_points":
            knowledge_object.get(
                "key_points",
                []
            ),

        "concepts":
            concepts,

        "important_information":
            important_information,

        "inferred_knowledge":
            knowledge_object.get(
                "inferred_knowledge",
                []
            ),

        "external_knowledge":
            knowledge_object.get(
                "external_knowledge",
                {}
            ),

        "visual_information":
            visual_object.get(
                "important_information",
                []
            ),

        "ocr_text":
            visual_object.get(
                "ocr_text",
                ""
            ),

        "visual_summary":
            visual_object.get(
                "visual_summary",
                ""
            ),

        "visual_type":
            visual_object.get(
                "visual_type"
            ),

        "teaching_stage":
            visual_object.get(
                "teaching_stage"
            ),

        "importance_score":
            visual_object.get(
                "importance_score",
                0
            ),

        "include_in_notes":
            visual_object.get(
                "include_in_notes",
                False
            ),

        "screenshots":
            visual_object.get(
                "source_screenshots",
                []
            ),

        "selected_screenshots":
            get_selected_screenshots(
                visual_object
            ),

        "start":
            visual_object.get(
                "start"
            ),

        "end":
            visual_object.get(
                "end"
            )
    }



# Save


def save_merged_object(
    merged_object,
    output_dir
):
    """
    Save merged object.
    """

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    chunk_id = (
        merged_object[
            "chunk_id"
        ]
    )

    output_path = (
        output_dir
        /
        f"chunk_{chunk_id}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            merged_object,
            f,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )



# Process One Chunk



def process_chunk(
    knowledge_path
):
    """
    Process one chunk.
    """

    chunk_name = (
        knowledge_path.stem
    )

    chunk_id = (
        chunk_name
        .replace(
            "chunk_",
            ""
        )
    )

    visual_path = (
        VISUAL_OBJECTS_DIR
        /
        f"chunk_{chunk_id}_visual.json"
    )

    if not visual_path.exists():

        logger.warning(
            f"Missing visual object "
            f"for chunk "
            f"{chunk_id}"
        )

        return

    knowledge_object = (
        load_json(
            knowledge_path
        )
    )

    visual_object = (
        load_json(
            visual_path
        )
    )

    merged_object = (
        merge_objects(
            knowledge_object,
            visual_object
        )
    )

    save_merged_object(
        merged_object,
        MERGED_OBJECTS_DIR
    )


# Process All Chunks


def process_all_chunks():
    """
    Merge all chunks.
    """

    knowledge_files = sorted(
        OBJECTS_DIR.glob(
            "chunk_*.json"
        )
    )

    logger.info(
        f"Found "
        f"{len(knowledge_files)} "
        f"knowledge objects."
    )

    for knowledge_file in (
        knowledge_files
    ):

        process_chunk(
            knowledge_file
        )

    logger.info(
        "Merge complete."
    )


# Main


if __name__ == "__main__":

    process_all_chunks()