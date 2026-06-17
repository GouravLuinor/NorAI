import json
import os
import logging
from pathlib import Path
import time
from dotenv import load_dotenv
from google import genai

from extract.models import (
    KnowledgeObject
)

from extract.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    OUTPUT_SCHEMA
)

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed
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
            "gemma-4-26b-a4b-it",

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

    logger.info(
        f"Processing chunk "
        f"{chunk['chunk_id']}"
    )

    return KnowledgeObject(
        chunk_id=
            chunk["chunk_id"],

        transcript=
            chunk["text"],

        **data
    )

#create a retry wrapper

def process_chunk_with_retry(
    chunk,
    max_retries=3
):
    """
    Process chunk with retry logic.
    """

    for attempt in range(
        max_retries
    ):

        try:

            return process_chunk(
                chunk
            )

        except Exception as e:

            wait_time = (
                2 ** attempt
            )

            logger.warning(
                f"Chunk "
                f"{chunk['chunk_id']} "
                f"failed. "
                f"Retry "
                f"{attempt + 1}/"
                f"{max_retries}. "
                f"Waiting "
                f"{wait_time}s."
            )

            time.sleep(
                wait_time
            )

    raise RuntimeError(
        f"Failed chunk "
        f"{chunk['chunk_id']} "
        f"after "
        f"{max_retries} retries."
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

    logger.info(
        f"Starting chunk "
        f"{chunk['chunk_id']}"
    )

    knowledge_object = (
        extract_knowledge_object(
            chunk
        )
    )

    save_knowledge_object(
        knowledge_object
    )

    return knowledge_object


if __name__ == "__main__":

    CHUNKS_FILE = (
        "outputs/chunks/"
        "ciHThtTVNto_chunks.json"
    )

    MAX_WORKERS = 7

    with open(
        CHUNKS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    chunks = data["chunks"]

    total_chunks = len(
        chunks
    )

    completed = 0

    logger.info(
        f"Loaded "
        f"{total_chunks} chunks."
    )

    with ThreadPoolExecutor(
        max_workers=
        MAX_WORKERS
    ) as executor:

        futures = []

        for chunk in chunks:

            futures.append(
                executor.submit(
                    process_chunk_with_retry,
                    chunk
                )
            )

        for future in as_completed(
            futures
        ):

            try:

                result = (
                    future.result()
                )

                completed += 1

                logger.info(
                    f"Progress: "
                    f"{completed}/"
                    f"{total_chunks}"
                )

            except Exception as e:

                logger.error(
                    f"Worker failed: "
                    f"{e}"
                )

    logger.info(
        "Knowledge extraction complete."
    )