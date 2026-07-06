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


def merge_objects_without_visual(knowledge_object: dict) -> dict:
    """
    Build a merged object from a knowledge object when no visual
    object is available.  Every field that the chapter builder expects
    is present, so downstream stages never see empty chapters.
    """
    return {
        "object_type":          "merged_object",
        "chunk_id":             knowledge_object.get("chunk_id", 0),
        "topic":                knowledge_object.get("topic", ""),
        "transcript":           knowledge_object.get("transcript", ""),
        "lecture_notes":        knowledge_object.get("lecture_notes", []),
        "visual_notes":         [],            # no visual = no visual notes
        "key_points":           knowledge_object.get("key_points", []),
        "concepts":             knowledge_object.get("concepts", []),
        "important_information": knowledge_object.get("key_points", []),
        "inferred_knowledge":   knowledge_object.get("inferred_knowledge", []),
        "external_knowledge":   knowledge_object.get("external_knowledge", {}),
        "visual_information":   [],
        "ocr_text":             "",
        "visual_summary":       "",
        "visual_type":          "none",
        "teaching_stage":       "",
        "importance_score":     0,
        "include_in_notes":     False,
        "screenshots":          [],
        "selected_screenshots": [],
        "start":                knowledge_object.get("start", 0),
        "end":                  knowledge_object.get("end", 0),
    }
# Process One Chunk



def process_chunk(knowledge_path):
    chunk_id = int(knowledge_path.stem.split("_")[1])

    visual_path = VISUAL_OBJECTS_DIR / f"chunk_{chunk_id}_visual.json"
    knowledge_object = load_json(knowledge_path)

    if visual_path.exists():
        visual_object = load_json(visual_path)
        merged = merge_objects(knowledge_object, visual_object)
    else:
        logger.warning(f"Missing visual object for chunk {chunk_id} — merging knowledge object only")
        merged = merge_objects_without_visual(knowledge_object)

    save_merged_object(merged, MERGED_OBJECTS_DIR)


# Process All Chunks
def merge_all_chunks(
    objects_dir: str,
    visual_objects_dir: str,
    merged_objects_dir: str,
) -> dict:
    """
    Merge transcript knowledge objects with visual knowledge objects,
    writing the results into merged_objects_dir.

    Args:
        objects_dir:          path to the directory containing chunk_*.json
                              knowledge objects.
        visual_objects_dir:   path to the directory containing
                              chunk_*_visual.json files.
        merged_objects_dir:   path where merged chunk_*.json files will
                              be saved.

    Returns:
        { "merged_dir": str, "num_chunks": int }
    """
    import extract.merger as _merger

    # Override module globals so the existing functions use lecture‑scoped paths
    _merger.OBJECTS_DIR         = Path(objects_dir)
    _merger.VISUAL_OBJECTS_DIR  = Path(visual_objects_dir)
    out                         = Path(merged_objects_dir)
    out.mkdir(parents=True, exist_ok=True)
    _merger.MERGED_OBJECTS_DIR  = out

    knowledge_files = sorted(Path(objects_dir).glob("chunk_*.json"))
    if not knowledge_files:
        logger.warning("No knowledge objects found to merge.")
        return {"merged_dir": str(out), "num_chunks": 0}

    logger.info(f"Merging {len(knowledge_files)} chunks…")
    for kf in knowledge_files:
        process_chunk(kf)

    logger.info("Merge complete.")
    return {"merged_dir": str(out), "num_chunks": len(knowledge_files)}


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