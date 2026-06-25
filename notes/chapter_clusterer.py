import json

import logging
from pathlib import Path
from sentence_transformers import (
    SentenceTransformer
)

from sklearn.metrics.pairwise import (
    cosine_similarity
)

from notes.chapter_models import (
    Chapter,
    ChapterGroup
)


# -----------------------------
# Config
# -----------------------------

MODEL_NAME = (
    "all-MiniLM-L6-v2"
)

SIMILARITY_THRESHOLD = 0.72

CHAPTER_DIR = (
    "outputs/chapters"
)



logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Model


model = SentenceTransformer(
    MODEL_NAME
)



# Load Objects


def load_merged_objects(
    merged_dir
):

    merged_dir = Path(
        merged_dir
    )

    objects = []

    for file_path in sorted(
        merged_dir.glob(
            "*.json"
        )
    ):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            objects.append(
                json.load(f)
            )

    objects.sort(
        key=lambda x:
        x["chunk_id"]
    )

    logger.info(
        f"Loaded "
        f"{len(objects)} "
        f"merged objects."
    )

    return objects



# Embedding Text


def build_embedding_text(
    obj
):

    concepts = " ".join(
        obj.get(
            "concepts",
            []
        )
    )

    important = " ".join(
        obj.get(
            "important_information",
            []
        )
    )

    inferred = " ".join(
        obj.get(
            "inferred_knowledge",
            []
        )
    )

    return f"""
    Topic:
    {obj.get("topic", "")}

    Lecture Notes:
    {obj.get("lecture_notes", "")}

    Concepts:
    {concepts}

    Important Information:
    {important}

    Inferred Knowledge:
    {inferred}
    """



# Embeddings


def generate_embeddings(
    merged_objects
):

    texts = [

        build_embedding_text(
            obj
        )

        for obj
        in merged_objects
    ]

    return model.encode(
        texts,
        normalize_embeddings=True
    )



# Similarity


def compute_adjacent_similarity(
    embeddings
):

    similarities = []

    for i in range(
        len(embeddings) - 1
    ):

        sim = cosine_similarity(

            [embeddings[i]],

            [embeddings[i + 1]]

        )[0][0]

        similarities.append(
            float(sim)
        )

    return similarities



# Clustering


SIMILARITY_THRESHOLD = 0.72


def create_groups(
    merged_objects,
    similarities
):

    if not merged_objects:
        return []

    groups = []

    current_group = [
        merged_objects[0]
    ]

    for i, similarity in (
        enumerate(
            similarities
        )
    ):

        if similarity >= (
            SIMILARITY_THRESHOLD
        ):

            current_group.append(
                merged_objects[
                    i + 1
                ]
            )

        else:

            groups.append(
                current_group
            )

            current_group = [
                merged_objects[
                    i + 1
                ]
            ]

    groups.append(
        current_group
    )

    logger.info(
        f"Created "
        f"{len(groups)} "
        f"groups."
    )

    return groups



# Chapter Groups


def build_chapter_groups(
    groups
):

    chapter_groups = []

    for chapter_id, group in (
        enumerate(
            groups,
            start=1
        )
    ):

        chunk_ids = [

            obj["chunk_id"]

            for obj
            in group
        ]

        topics = sorted(
            set(

                obj["topic"]

                for obj
                in group
            )
        )

        concepts = sorted(
            set(

                concept

                for obj in group

                for concept in (
                    obj.get(
                        "concepts",
                        []
                    )
                )
            )
        )

        chapter_groups.append({

            "chapter_id":
            chapter_id,

            "start_chunk":
            chunk_ids[0],

            "end_chunk":
            chunk_ids[-1],

            "chunk_ids":
            chunk_ids,

            "topics":
            topics,

            "concepts":
            concepts
        })

    return chapter_groups



# Chapter Objects


def build_chapter(
    chapter_id,
    group
):

    chunk_ids = [

        obj["chunk_id"]

        for obj
        in group
    ]

    topics = sorted(
        set(
            obj["topic"]
            for obj
            in group
        )
    )

    concepts = sorted(
        set(

            concept

            for obj in group

            for concept in (
                obj.get(
                    "concepts",
                    []
                )
            )
        )
    )

    lecture_notes = [

        obj["lecture_notes"]

        for obj
        in group
    ]

    visual_notes = [

        obj.get(
            "visual_notes",
            ""
        )

        for obj
        in group
    ]

    important_information = sorted(
        set(

            item

            for obj in group

            for item in (
                obj.get(
                    "important_information",
                    []
                )
            )
        )
    )

    inferred_knowledge = sorted(
        set(

            item

            for obj in group

            for item in (
                obj.get(
                    "inferred_knowledge",
                    []
                )
            )
        )
    )

    screenshots = []

    for obj in group:

        selected = obj.get(
            "selected_screenshots",
            []
        )

        if selected:

            screenshots.extend(
                selected
            )

        else:

            screenshots.extend(
                obj.get(
                    "screenshots",
                    []
                )
            )

    screenshots = sorted(
        set(
            screenshots
        )
    )

    return {

        "chapter_id":
        chapter_id,

        "start_chunk":
        chunk_ids[0],

        "end_chunk":
        chunk_ids[-1],

        "chunk_ids":
        chunk_ids,

        "topics":
        topics,

        "concepts":
        concepts,

        "lecture_notes":
        lecture_notes,

        "visual_notes":
        visual_notes,

        "important_information":
        important_information,

        "inferred_knowledge":
        inferred_knowledge,

        "screenshots":
        screenshots
    }


def build_chapters(
    groups
):

    chapters = []

    for chapter_id, group in (
        enumerate(
            groups,
            start=1
        )
    ):

        chapters.append(

            build_chapter(
                chapter_id,
                group
            )
        )

    return chapters



# Save


def save_chapter_groups(
    chapter_groups,
    output_dir
):

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        output_dir
        /
        "chapter_groups.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            chapter_groups,
            f,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )


def save_chapters(
    chapters,
    output_dir
):

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    for chapter in chapters:

        chapter_id = (
            chapter[
                "chapter_id"
            ]
        )

        output_path = (
            output_dir
            /
            f"chapter_{chapter_id}.json"
        )

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                chapter,
                f,
                indent=4,
                ensure_ascii=False
            )

        logger.info(
            f"Saved: "
            f"{output_path}"
        )



# Main


def main():

    logger.info(
        "Loading merged objects..."
    )

    merged_objects = (
        load_merged_objects(
            "outputs/merged_objects"
        )
    )

    logger.info(
        "Generating embeddings..."
    )

    embeddings = (
        generate_embeddings(
            merged_objects
        )
    )

    logger.info(
        "Computing similarities..."
    )

    similarities = (
        compute_adjacent_similarity(
            embeddings
        )
    )

    logger.info(
        "Similarity Scores:"
    )

    for i, similarity in (
        enumerate(
            similarities
        )
    ):

        logger.info(
            f"{i} -> {i+1}: "
            f"{similarity:.3f}"
        )

    logger.info(
        "Creating chapter groups..."
    )

    groups = (
        create_groups(
            merged_objects,
            similarities
        )
    )

    logger.info(
        f"Created "
        f"{len(groups)} "
        f"chapter groups."
    )

    chapter_groups = (
        build_chapter_groups(
            groups
        )
    )

    save_chapter_groups(
        chapter_groups,
        CHAPTER_DIR
    )

    logger.info(
        "Building chapter objects..."
    )

    chapters = (
        build_chapters(
            groups
        )
    )

    save_chapters(
        chapters,
        CHAPTER_DIR
    )

    logger.info(
        "Chapter Summary:"
    )

    for chapter in (
        chapter_groups
    ):

        logger.info(
            f"Chapter "
            f"{chapter['chapter_id']}: "
            f"{chapter['start_chunk']} "
            f"-> "
            f"{chapter['end_chunk']} "
            f"("
            f"{len(chapter['chunk_ids'])}"
            f" chunks)"
        )

    logger.info(
        "Chapter clustering complete."
    )


if __name__ == "__main__":
    main()