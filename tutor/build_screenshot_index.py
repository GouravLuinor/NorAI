"""
build_screenshot_index.py — one-shot script to index screenshot captions.

Walks all chapter_*_screenshots.json files, embeds the 'reason' field of
each screenshot using gemini-embedding-2 (role="document"), and upserts
into the Chroma screenshot_captions collection.

Usage:
    python -m tutor.build_screenshot_index
    python -m tutor.build_screenshot_index --reset
    python -m tutor.build_screenshot_index --smoke-test "what is a segment tree?"
"""

import argparse
import json
import glob
import time
from pathlib import Path

import chromadb

from .retrieval_config import (
    CHROMA_DIR,
    SCREENSHOT_COLLECTION_NAME,
    SCREENSHOT_JSON_GLOB,
    EMBED_BATCH_SLEEP_SEC,
)
from .embedding import GeminiEmbeddingFunction

# ── Batch size for embedding calls ─────────────────────────────────────────────
# Not in retrieval_config.py (that file is for shared runtime constants).
# This is an indexing-only concern — keep it local.
_INDEX_BATCH_SIZE = 20


def _get_screenshot_collection(reset: bool = False):
    """Create or retrieve the screenshot captions Chroma collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = GeminiEmbeddingFunction(role="document")

    if reset:
        try:
            client.delete_collection(SCREENSHOT_COLLECTION_NAME)
            print(f"Deleted existing collection '{SCREENSHOT_COLLECTION_NAME}'.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=SCREENSHOT_COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def index_screenshots(reset: bool = False):
    """Walk all screenshot JSONs and upsert captions into Chroma."""
    json_files = sorted(glob.glob(SCREENSHOT_JSON_GLOB))
    if not json_files:
        print("No screenshot JSON files found. Run knowledge extraction first.")
        return

    collection = _get_screenshot_collection(reset=reset)

    total = 0
    for json_path in json_files:
        with open(json_path, "r") as f:
            data = json.load(f)

        chapter_id = data.get("chapter_id")
        screenshots = data.get("screenshots", [])
        if not screenshots:
            print(f"  Skipping {json_path}: no screenshots.")
            continue

        ids = []
        documents = []
        metadatas = []

        for shot in screenshots:
            shot_id = f"ch{chapter_id}_{Path(shot['path']).stem}"
            ids.append(shot_id)
            # Embed the 'reason' field — it's a pre-written caption describing the slide
            documents.append(shot["reason"])
            metadatas.append({
                "path": shot["path"],
                "section": shot.get("section", ""),
                "importance": shot.get("importance", 0),
                "chapter_id": chapter_id,
            })

        # Batch upsert with sleep to stay under free-tier rate limits
        for i in range(0, len(ids), _INDEX_BATCH_SIZE):
            batch_ids = ids[i:i + _INDEX_BATCH_SIZE]
            batch_docs = documents[i:i + _INDEX_BATCH_SIZE]
            batch_meta = metadatas[i:i + _INDEX_BATCH_SIZE]
            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_meta,
            )
            print(f"  Chapter {chapter_id}: indexed {len(batch_ids)} screenshots "
                  f"(batch {i // _INDEX_BATCH_SIZE + 1})")
            time.sleep(EMBED_BATCH_SLEEP_SEC)

        total += len(ids)

    print(f"\nDone. Indexed {total} screenshots total across {len(json_files)} files.")


def smoke_test(query: str):
    """Quick retrieval test to verify the index works."""
    from .retriever import retrieve_images

    results = retrieve_images(query, chapter_id=None, k=2)
    print(f"\nSmoke test query: '{query}'")
    if not results:
        print("  No results returned.")
    for r in results:
        print(f"  [{r.get('section', '?')}] {r.get('path')} "
              f"(importance {r.get('importance')}, distance {r.get('distance'):.3f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Index screenshot captions into Chroma for Phase 4 retrieval."
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete the existing collection and rebuild from scratch."
    )
    parser.add_argument(
        "--smoke-test", type=str, default=None, metavar="QUERY",
        help="Run a test query after indexing to verify retrieval works."
    )
    args = parser.parse_args()

    index_screenshots(reset=args.reset)

    if args.smoke_test:
        smoke_test(args.smoke_test)