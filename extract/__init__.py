import json
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from extract.models import (
    KnowledgeObject
)

from extract.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    OUTPUT_SCHEMA
)

load_dotenv()


# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# Gemini Client

def load_llm():

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found."
        )

    return genai.Client(
        api_key=api_key
    )


# Prompt Builder

def build_prompt(
    transcript_chunk
):
    """
    Create extraction prompt.
    """

    return f"""
Transcript Chunk:

{transcript_chunk}

Return a JSON object
matching this schema:

{OUTPUT_SCHEMA}
"""


# Extraction

def extract_knowledge_object(
    chunk
):
    """
    Convert transcript chunk
    into KnowledgeObject.
    """

    client = load_llm()

    prompt = build_prompt(
        chunk["text"]
    )

    response = (
        client.models.generate_content(
            model=
            "gemini-2.5-flash-lite",

            contents=
            f"{EXTRACTION_SYSTEM_PROMPT}\n\n{prompt}"
        )
    )

    raw_json = (
        response.text
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

    data = json.loads(
        raw_json
    )

    return KnowledgeObject(
        chunk_id=
            chunk["chunk_id"],

        transcript=
            chunk["text"],

        **data
    )


# Save

def save_knowledge_object(
    knowledge_object,
    output_dir=
    "outputs/objects"
):
    """
    Save object as JSON.
    """

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        output_dir /
        f"chunk_"
        f"{knowledge_object.chunk_id}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            knowledge_object.model_dump(),
            f,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        f"Saved: "
        f"{output_path}"
    )


# Public API

def process_chunk(
    chunk
):
    """
    Extract and save.
    """

    knowledge_object = (
        extract_knowledge_object(
            chunk
        )
    )

    save_knowledge_object(
        knowledge_object
    )

    return knowledge_object