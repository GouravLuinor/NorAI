import json
import logging
from pathlib import Path
import os

from google import genai
from dotenv import load_dotenv
from notes.outline_prompts import OUTLINE_PROMPT


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


MODEL_NAME = "gemma-4-26b-a4b-it"


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



def load_chapters(
    chapter_dir
):
    """
    Load all chapter objects.
    """

    chapter_dir = Path(
        chapter_dir
    )

    chapters = []

    for file_path in sorted(
        chapter_dir.glob(
            "chapter_*.json"
        )
    ):

        if (
            file_path.stem
            == "chapter_groups"
        ):
            continue

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            chapter = json.load(
                f
            )

        chapters.append(
            chapter
        )

    chapters.sort(
        key=lambda x:
        x["chapter_id"]
    )

    logger.info(
        f"Loaded "
        f"{len(chapters)} chapters."
    )

    return chapters


def build_outline_payload(
    chapters
):

    payload = []

    for chapter in chapters:

        payload.append({

            "chapter_id":
            chapter["chapter_id"],

            "topics":
            chapter["topics"][:5],

            "concepts":
            chapter["concepts"][:10],

            "summary":
            " ".join(
                chapter[
                    "lecture_notes"
                ]
            )[:1000]
        })

    return payload


def build_prompt(
    chapters
):

    payload = (
        build_outline_payload(
            chapters
        )
    )

    return (

        OUTLINE_PROMPT

        +

        "\n\n"

        +

        json.dumps(
            payload,
            indent=4,
            ensure_ascii=False
        )
    )



def generate_outline(
    chapters
):

    prompt = (
        build_prompt(
            chapters
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


def main():

    chapters = (
        load_chapters(
            "outputs/chapters"
        )
    )

    outline_text = (
        generate_outline(
            chapters
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
        "Outline generation complete."
    )      

if __name__ == "__main__":
    main()
