import json
import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer


# Logging Setup


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# Constants

DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)


# Chunk Loader


def load_chunks(chunks_json_path):
    """
    Load chunked transcript JSON.
    """

    chunks_json_path = Path(chunks_json_path)

    if not chunks_json_path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {chunks_json_path}"
        )

    with open(
        chunks_json_path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)
 

# Model Loader


def load_embedding_model(
    model_name=DEFAULT_EMBEDDING_MODEL
):
    """
    Load sentence-transformer model.
    """

    logger.info(
        f"Loading embedding model: {model_name}"
    )

    return SentenceTransformer(
        model_name
    )



# Embedding Generator



def generate_embeddings(
    chunks,
    model
):
    """
    Generate embeddings for chunks.
    """

    chunk_texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = model.encode(
        chunk_texts,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    return embeddings



# Embedding Metadata Builder


def build_embedding_records(
    source,
    chunks,
    embeddings
):
    """
    Build embedding records.
    """

    records = []

    for chunk, embedding in zip(
        chunks,
        embeddings
    ):

        record = {
            "chunk_id": chunk["chunk_id"],

            "text": chunk["text"],

            "embedding": embedding.tolist(),

            "metadata": {
                "video_id": source.get(
                    "video_id"
                ),

                "title": source.get(
                    "title"
                ),

                "source_type": source.get(
                    "source_type"
                ),

                "start": chunk["start"],
                "end": chunk["end"],

                "segment_start":
                    chunk["segment_start"],

                "segment_end":
                    chunk["segment_end"]
            }
        }

        records.append(record)

    return records



# Embedding Saver


def save_embeddings(
    records,
    output_path
):
    """
    Save embedding records.
    """

    output_path = Path(output_path)

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
            records,
            f,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        f"Embeddings saved to: {output_path}"
    )


# Public API


def embed_chunks(
    chunks_json_path,
    output_dir="outputs",
    model_name=DEFAULT_EMBEDDING_MODEL
):
    """
    Main embedding pipeline.
    """

    data = load_chunks(
        chunks_json_path
    )

    source = data["source"]
    chunks = data["chunks"]

    logger.info(
        f"Loaded {len(chunks)} chunks."
    )

    model = load_embedding_model(
        model_name
    )

    embeddings = generate_embeddings(
        chunks,
        model
    )

    logger.info(
        f"Generated {len(embeddings)} embeddings."
    )

    logger.info(
        f"Embedding dimension: "
        f"{len(embeddings[0])}"
    )

    records = build_embedding_records(
        source,
        chunks,
        embeddings
    )

    chunks_path = Path(
        chunks_json_path
    )

    embedding_dir = (
        Path(output_dir)
        / "embeddings"
    )

    embedding_path = (
        embedding_dir /
        f"{chunks_path.stem}_embeddings.json"
    )

    save_embeddings(
        records,
        embedding_path
    )

    return {
        "embedding_path":
            str(embedding_path),

        "num_chunks":
            len(chunks),

        "embedding_dimension":
            len(embeddings[0])
    }



# Example Usage


if __name__ == "__main__":

    result = embed_chunks(
        "outputs/chunks/ciHThtTVNto_chunks.json"
    )

    print(
        json.dumps(
            result,
            indent=4
        )
    )