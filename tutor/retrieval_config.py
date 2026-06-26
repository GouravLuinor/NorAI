"""
Retrieval configuration for Phase 3.
Kept separate from config.py so tutor core (LLM, checkpointer) and retrieval
(Chroma, embeddings) can evolve independently without touching each other.
"""

import os
from pathlib import Path

# ── Embedding model ───────────────────────────────────────────────────────────
# gemini-embedding-2: stable GA model (April 2026).
# - Does NOT accept task_type= parameter — task instructions go in prompt text.
# - Auto-normalises truncated dims, so 768 cosine similarity is accurate OOTB.
# - gemini-embedding-exp-03-07 / gemini-embedding-001 are deprecated; don't use.
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 768  # 768 / 1536 / 3072 all recommended; 768 saves storage.

# ── Phase 4: screenshot retrieval ─────────────────────────────────────────────

SCREENSHOT_COLLECTION_NAME = "screenshot_captions"

TOP_K_IMAGES = 2  # Number of images to retrieve per query

SCREENSHOTS_DIR = "outputs/screenshots/keyframes"  # base path for image files

# Screenshot JSON pattern: outputs/screenshots/chapter_*_screenshots.json
SCREENSHOT_JSON_GLOB = "outputs/screenshots/selected/chapter_*_screenshots.json"

# ── Chroma persistent store ───────────────────────────────────────────────────
CHROMA_DIR = Path("outputs/tutor/chroma")
NOTES_COLLECTION = "study_notes"

# ── Source notes glob ─────────────────────────────────────────────────────────
NOTES_GLOB = "outputs/notes/chapter_*.md"

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K = 5  # chunks returned per query

# ── Rate limiting ─────────────────────────────────────────────────────────────
# gemini-embedding-2 free tier: varies; add a small sleep between batch calls
# during indexing to stay safely under limits.
EMBED_BATCH_SLEEP_SEC = 0.5  # seconds between batches during build_index