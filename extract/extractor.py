import json
import os
import logging
from pathlib import Path
import time
from dotenv import load_dotenv
from google import genai
import random
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
from backend.ratelimit import RPMRateLimiter
_limiter = RPMRateLimiter(max_calls=12)

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
    _limiter.wait()
    response = (
        client.models.generate_content(
            model=
            "gemini-3.1-flash-lite-preview",

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


# Retry wrapper

def process_chunk_with_retry(
    chunk,
    max_retries=8,
    output_dir="outputs/objects"
):
    """
    Process chunk with retry logic.
    """

    for attempt in range(
        max_retries
    ):

        try:

            return process_chunk(
                chunk,
                output_dir
            )

        except Exception as e:

            wait_time = (
                5 * (attempt + 1) + random.uniform(0.5, 3.0)
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
    output_dir="outputs/objects"
):
    """
    Save object as JSON to the given output directory.
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


# Public API – single chunk

def process_chunk(
    chunk,
    output_dir="outputs/objects"
):
    """
    Extract and save a single chunk.
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
        knowledge_object,
        output_dir
    )

    return knowledge_object


# Public API – all chunks (for orchestrator)

def extract_all_chunks(
    chunks_path: str,
    output_dir: str,
    max_workers: int = 4,
) -> dict:
    """
    Process all chunks from a chunks JSON file and save knowledge objects
    into {output_dir}/objects/.

    Returns { "objects_dir": str, "num_chunks": int }
    """

    with open(chunks_path, encoding="utf-8") as f:
        data = json.load(f)

    chunks = data["chunks"]
    total = len(chunks)
    logger.info(
        f"Extracting knowledge from {total} chunks (workers={max_workers})"
    )

    objects_dir = Path(output_dir) / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)

    completed = 0

    with ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:

        futures = [
            executor.submit(
                process_chunk_with_retry,
                ch,
                3,
                str(objects_dir)
            )
            for ch in chunks
        ]

        for future in as_completed(futures):
            try:
                future.result()
                completed += 1
                if completed % 5 == 0 or completed == total:
                    logger.info(
                        f"  Knowledge extraction: {completed}/{total}"
                    )
            except Exception as e:
                logger.error(f"  Chunk worker failed: {e}")

    return {
        "objects_dir": str(objects_dir),
        "num_chunks": total
    }


if __name__ == "__main__":

    CHUNKS_FILE = (
        "outputs/chunks/"
        "ciHThtTVNto_chunks.json"
    )

    result = extract_all_chunks(
        CHUNKS_FILE,
        output_dir="outputs"
    )

    print(json.dumps(result, indent=4))