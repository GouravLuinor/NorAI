import json
import logging
from pathlib import Path

import chromadb


# Logging Setup


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# Constants


DEFAULT_COLLECTION_NAME = (
    "norai_lectures"
)

DEFAULT_CHROMA_PATH = (
    "chroma_db"
)


# Chunk Loader


def load_chunks(
    chunks_json_path
):
    """
    Load chunk JSON.
    """

    chunks_json_path = Path(
        chunks_json_path
    )

    if not chunks_json_path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: "
            f"{chunks_json_path}"
        )

    with open(
        chunks_json_path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


# embedding loader

def load_embeddings(embeddings_json_path):
    """
    Load embedding JSON.
    """

    embeddings_json_path = Path(embeddings_json_path)

    if not embeddings_json_path.exists():
        raise FileNotFoundError(
            f"Embeddings file not found: {embeddings_json_path}"
        )

    with open(
        embeddings_json_path,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)



# Chroma Client


def get_chroma_client(
    chroma_path=DEFAULT_CHROMA_PATH
):
    """
    Create persistent Chroma client.
    """

    return chromadb.PersistentClient(
        path=chroma_path
    )


# Collection Manager


def get_or_create_collection(
    client,
    collection_name=
    DEFAULT_COLLECTION_NAME
):
    """
    Get or create collection.
    """

    return client.get_or_create_collection(
        name=collection_name
    )


# Record Builder

def build_records(
    source,
    chunks
):
    """
    Build Chroma-compatible records.
    """

    ids = []
    documents = []
    metadatas = []

    video_id = source.get(
        "video_id",
        "unknown_video"
    )

    for chunk in chunks:

        ids.append(
            f"{video_id}_chunk_"
            f"{chunk['chunk_id']}"
        )

        documents.append(
            chunk["text"]
        )

        metadatas.append(
            {
                "video_id":
                    video_id,

                "title":
                    source.get("title", "Unknown Title"),

                "source_type":
                    source.get(
                        "source_type", "Unknown source_type"
                    ),

                "chunk_id":
                    chunk["chunk_id"],

                "start":
                    chunk["start"],

                "end":
                    chunk["end"],

                "duration":
                    chunk["duration"]
            }
        )

    return (
        ids,
        documents,
        metadatas
    )



# Chroma Storage


def store_chunks(
    collection,
    ids,
    documents,
    embeddings,
    metadatas
):
    """
    Store chunks in Chroma.
    """

    collection.upsert( # UPSERT PREVENTS DUPLICATES
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    logger.info(
        f"Inserted "
        f"{len(ids)} records."
    )



# Public API


def store_chunks_in_chroma(
    chunks_json_path,
    embeddings_json_path,
    chroma_path=
        DEFAULT_CHROMA_PATH,

    collection_name=
        DEFAULT_COLLECTION_NAME
):
    """
    Main Chroma pipeline.
    """

    data = load_chunks(
        chunks_json_path
    )

    embedding_records = load_embeddings(
        embeddings_json_path
    )

    embeddings = [
        record["embedding"]
        for record in embedding_records
    ]

    source = data["source"]
    chunks = data["chunks"]

    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Mismatch: "
            f"{len(chunks)} chunks vs "
            f"{len(embeddings)} embeddings"
        )
    

    for chunk, record in zip(
    chunks,
    embedding_records
    ):
        if chunk["chunk_id"] != record["chunk_id"]:
            raise ValueError(
                "Chunk IDs and embeddings are misaligned."
            )


    logger.info(
        f"Loaded "
        f"{len(chunks)} chunks."
    )

    client = get_chroma_client(
        chroma_path
    )

    collection = (
        get_or_create_collection(
            client,
            collection_name
        )
    )

    ids, documents, metadatas = (
        build_records(
            source,
            chunks
        )
    )

    store_chunks(
        collection,
        ids,
        documents,
        embeddings,
        metadatas
    )

    logger.info(
        f"Collection count: "
        f"{collection.count()}"
    )

    return {
        "collection_name":
            collection_name,

        "documents_added":
            len(ids),

        "total_documents":
            collection.count()
    }


# Example Usage


if __name__ == "__main__":

    result = (
        store_chunks_in_chroma(
            "outputs/chunks/"
            "ciHThtTVNto_chunks.json",
            "outputs/embeddings/"
            "ciHThtTVNto_chunks_embeddings.json"
        )
    )

    print(
        json.dumps(
            result,
            indent=4
        )
    )