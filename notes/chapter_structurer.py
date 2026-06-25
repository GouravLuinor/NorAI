import json
import logging
import os
from pydantic import BaseModel
from pathlib import Path
from google import genai
from dotenv import load_dotenv


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



from pydantic import BaseModel


class OutlineChapter(BaseModel):

    chapter_id: int

    title: str

    start_chunk: int

    end_chunk: int

    focus_concepts: list[str]


class LectureOutline(BaseModel):

    lecture_title: str

    chapters: list[OutlineChapter]


def load_merged_objects(
    merged_dir
):

    merged_dir = Path(
        merged_dir
    )

    objects = []

    for file_path in sorted(
        merged_dir.glob(
            "chunk_*.json"
        )
    ):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            obj = json.load(
                f
            )

        objects.append(
            obj
        )

    objects.sort(
        key=lambda x:
        x["chunk_id"]
    )

    logger.info(
        f"Loaded "
        f"{len(objects)} merged objects."
    )

    return objects


MODEL_NAME = "gemini-3.5-flash"



def load_llm():
    """
    Load Gemini model.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found."
        )

    client = genai.Client(
        api_key=api_key
    )

    return client


# client = load_llm()


client = load_llm()


def load_merged_objects(
    merged_dir
):

    merged_dir = Path(
        merged_dir
    )

    objects = []

    for file_path in sorted(
        merged_dir.glob(
            "chunk_*.json"
        )
    ):

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            obj = json.load(
                f
            )

        objects.append(
            obj
        )

    objects.sort(
        key=lambda x:
        x["chunk_id"]
    )

    logger.info(
        f"Loaded "
        f"{len(objects)} merged objects."
    )

    return objects


def build_payload(
    merged_objects
):

    payload = []

    for obj in merged_objects:

        payload.append({

            "chunk_id":
            obj["chunk_id"],

            "topic":
            obj["topic"],

            "concepts":
            obj["concepts"],

            "important_information":
            obj[
                "important_information"
            ]
        })

    return payload


CHAPTER_CLUSTER_PROMPT = """
You are organizing a lecture into revision chapters.

You are given sequential lecture units.

Each unit contains:

- chunk_id
- topic
- concepts
- important_information

Your task:

1. Preserve chronological order.

2. Identify natural topic transitions.

3. Group adjacent chunks into meaningful chapters.

4. Minimize overlap between chapters.

5. Create between 5 and 10 chapters.

6. Each chapter should represent a coherent learning unit.

7. Merge small adjacent topics when appropriate.

8. Avoid creating chapters solely for:

    - course logistics
    - community announcements
    - repository links
    - closing remarks

Merge these into the nearest chapter when appropriate.
Return JSON only.

Schema:

{
    "lecture_title": "",

    "chapters": [

        {
            "chapter_id": 1,

            "title": "",

            "start_chunk": 0,

            "end_chunk": 5,

            "focus_concepts": []
        }
    ]
}
"""


def build_prompt(
    merged_objects
):

    payload = (
        build_payload(
            merged_objects
        )
    )

    return f"""
{CHAPTER_CLUSTER_PROMPT}

==================================================

LECTURE UNITS

{json.dumps(
    payload,
    indent=4,
    ensure_ascii=False
)}

==================================================

Return JSON only.
"""


def generate_outline(
    merged_objects
):

    prompt = (
        build_prompt(
            merged_objects
        )
    )

    response = (
        client.models.generate_content(

            model=
            MODEL_NAME,

            contents=[
                prompt
            ]
        )
    )

    return (
        response.text
    )


def parse_outline(
    response_text
):

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

    return json.loads(
        response_text
    )



def save_outline(
    outline,
    output_path
):

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
            outline,
            f,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )


def main():

    merged_objects = (
        load_merged_objects(
            "outputs/merged_objects"
        )
    )

    outline_text = (
        generate_outline(
            merged_objects
        )
    )

    outline = (
        parse_outline(
            outline_text
        )
    )

    save_outline(

        outline,

        "outputs/notes/lecture_outline.json"
    )

    logger.info(
        "Chapter clustering complete."
    )


if __name__ == "__main__":
    main()