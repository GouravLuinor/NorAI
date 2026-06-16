import logging
import chromadb
from sentence_transformers import SentenceTransformer


# Logging Setup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)



# Constants


DEFAULT_CHROMA_PATH = "chroma_db"

DEFAULT_COLLECTION_NAME = "norai_lectures"

DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)



# Global Model


logger.info(
    f"Loading embedding model: "
    f"{DEFAULT_EMBEDDING_MODEL}"
)

MODEL = SentenceTransformer(
    DEFAULT_EMBEDDING_MODEL
)



# Chroma Client


def get_collection(
    chroma_path=DEFAULT_CHROMA_PATH,
    collection_name=DEFAULT_COLLECTION_NAME
):
    """
    Return Chroma collection.
    """

    client = chromadb.PersistentClient(
        path=chroma_path
    )

    return client.get_collection(
        name=collection_name
    )



# Query Embedding


def get_query_embedding(
    query: str
):
    """
    Generate embedding for query.
    """

    return MODEL.encode(
        query,
        convert_to_numpy=True
    ).tolist()



# Retrieval


def retrieve_chunks(
    query: str,
    n_results: int = 3
):
    """
    Retrieve top-k chunks.
    """

    collection = get_collection()

    query_embedding = (
        get_query_embedding(query)
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],

        n_results=n_results,

        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    retrieved_chunks = []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        retrieved_chunks.append(
            {
                "chunk_id":
                    metadata["chunk_id"],

                "video_id":
                    metadata["video_id"],

                "title":
                    metadata["title"],

                "start":
                    metadata["start"],

                "end":
                    metadata["end"],

                "distance":
                    distance,

                "text":
                    document
            }
        )

    return retrieved_chunks


# Pretty Print


def print_results(
    retrieved_chunks
):
    """
    Display retrieval results.
    """

    for idx, chunk in enumerate(
        retrieved_chunks,
        start=1
    ):

        print("\n" + "=" * 80)

        print(
            f"Result #{idx}"
        )

        print(
            f"Distance: "
            f"{chunk['distance']:.4f}"
        )

        print(
            f"Chunk ID: "
            f"{chunk['chunk_id']}"
        )

        print(
            f"Video ID: "
            f"{chunk['video_id']}"
        )

        print(
            f"Title: "
            f"{chunk['title']}"
        )

        print(
            f"Timestamp: "
            f"{chunk['start']}s "
            f"→ "
            f"{chunk['end']}s"
        )

        print("\nDocument:\n")

        print(
            chunk["text"][:500]
        )


# =============================
# Example Usage
# =============================

if __name__ == "__main__":

    query = (
        "Why is O(n) not good enough?"
    )

    chunks = retrieve_chunks(
        query=query,
        n_results=5
    )

    print_results(chunks)