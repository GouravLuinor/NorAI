"""
build_index.py — Build-once indexer for NorAI study notes.

Run this script once (or re-run when notes change) to:
  1. Chunk all outputs/notes/chapter_*.md files by heading hierarchy.
  2. Embed each chunk with gemini-embedding-2 (document role, 768 dims).
  3. Persist the collection to outputs/tutor/chroma/ as a Chroma database.

Usage:
    python -m tutor.build_index                  # index all chapters
    python -m tutor.build_index --reset          # drop + rebuild from scratch

The tutor graph's retrieval node just queries this persisted store — it never
calls this script. Keep them decoupled: indexing is a pipeline step, not a
runtime dependency.

Rate limiting:
    gemini-embedding-2 free tier has per-minute limits. EMBED_BATCH_SLEEP_SEC
    (set in retrieval_config.py) adds a pause between batches. The batch size
    below (BATCH_SIZE = 20) is conservative. Adjust up if you have a paid key.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import chromadb

from tutor.chunker import chunk_glob
from tutor.embedding import GeminiEmbeddingFunction
from tutor.retrieval_config import (
    CHROMA_DIR,
    EMBED_BATCH_SLEEP_SEC,
    NOTES_COLLECTION,
    NOTES_GLOB,
    TOP_K,
)

BATCH_SIZE = 20  # chunks per embed call; keeps us under free-tier rate limits


def _make_chroma_id(chunk: dict, idx: int) -> str:
    """
    Stable, unique ID per chunk. Uses chapter_id + heading_path so re-indexing
    the same file produces the same IDs (idempotent upsert-friendly).
    Falls back to positional index if chapter_id is missing.
    """
    chapter = chunk.get("chapter_id") or "x"
    # Sanitise heading_path: Chroma IDs must be strings with no special meaning
    path_slug = chunk["heading_path"].replace(" > ", "__").replace(" ", "_")[:80]
    return f"ch{chapter}__{path_slug}__{idx}"


def build_index(reset: bool = False) -> None:
    # ── 1. Chunk ───────────────────────────────────────────────────────────────
    print(f"Chunking notes from: {NOTES_GLOB}")
    chunks = chunk_glob(NOTES_GLOB)
    if not chunks:
        print("No chunks produced. Check that NOTES_GLOB matches existing files.")
        sys.exit(1)
    print(f"  {len(chunks)} chunks from {len(set(c['source'] for c in chunks))} files")

    # ── 2. Chroma client ───────────────────────────────────────────────────────
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if reset:
        try:
            client.delete_collection(NOTES_COLLECTION)
            print(f"  Dropped existing collection '{NOTES_COLLECTION}'")
        except Exception:
            pass  # Collection didn't exist; fine

    # EmbeddingFunction passed here is used for .add() calls below.
    # We use role="document" at index time.
    doc_ef = GeminiEmbeddingFunction(role="document")

    collection = client.get_or_create_collection(
        name=NOTES_COLLECTION,
        embedding_function=doc_ef,
        metadata={"hnsw:space": "cosine"},
    )

    # ── 3. Embed + upsert in batches ───────────────────────────────────────────
    total = len(chunks)
    inserted = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]

        ids = [_make_chroma_id(c, batch_start + i) for i, c in enumerate(batch)]
        documents = [c["text"] for c in batch]
        metadatas = [
            {
                "heading": c["heading"],
                "heading_path": c["heading_path"],
                "level": c["level"],
                "chapter_id": c["chapter_id"] if c["chapter_id"] is not None else -1,
                "source": c["source"],
            }
            for c in batch
        ]

        # .upsert() is idempotent: safe to re-run without --reset
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        inserted += len(batch)
        pct = inserted / total * 100
        print(f"  [{inserted:>4}/{total}] {pct:.0f}%  — batch {batch_start // BATCH_SIZE + 1}")

        if batch_start + BATCH_SIZE < total:
            time.sleep(EMBED_BATCH_SLEEP_SEC)

    print(f"\nDone. Collection '{NOTES_COLLECTION}' has {collection.count()} documents.")
    print(f"Persisted at: {CHROMA_DIR.resolve()}")


def _smoke_test(query: str = "What is a binary search tree?") -> None:
    """Quick sanity check: query the just-built index and print top results."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    query_ef = GeminiEmbeddingFunction(role="query")
    collection = client.get_collection(name=NOTES_COLLECTION, embedding_function=query_ef)

    results = collection.query(query_texts=[query], n_results=TOP_K)
    print(f"\n── Smoke test: '{query}' ──")
    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        print(f"\n[{i+1}] path={meta['heading_path']!r}  dist={dist:.4f}")
        print(f"     {doc[:200].replace(chr(10), ' ')!r}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build NorAI study-notes Chroma index")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and rebuild the collection from scratch",
    )
    parser.add_argument(
        "--smoke-test",
        dest="smoke",
        metavar="QUERY",
        nargs="?",
        const="What is the main topic of the notes?",
        help="After building, run a smoke-test query",
    )
    args = parser.parse_args()

    build_index(reset=args.reset)

    if args.smoke is not None:
        _smoke_test(args.smoke)