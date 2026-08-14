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
CHROMA_DIR = Path(os.environ.get("NORAI_CHROMA_DIR", "outputs/tutor/chroma"))
NOTES_COLLECTION = "norai_notes"

# ── Source notes glob ─────────────────────────────────────────────────────────
NOTES_GLOB = "outputs/notes/chapter_*.md"

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K = 5  # chunks returned per query

# ── Phase 3 (P3.2): hybrid search & adaptive top-k ────────────────────────────
# Cosine (Chroma) and BM25 each return this many candidates; the two ranked
# lists are merged with Reciprocal Rank Fusion (RRF_K = fusion constant).
ADAPTIVE_TOP_K_CANDIDATES = 20
RRF_K = 60
# Dynamic score dropoff: candidate chunks whose RRF fused score drops below
# this fraction of the top result are trimmed (between MIN_RESULTS and TOP_K).
ADAPTIVE_SCORE_DROPOFF_RATIO = 0.50
ADAPTIVE_TOP_K_MIN = 2
ADAPTIVE_TOP_K_MAX = 5
# After fusion, results above CONFIDENCE_THRESHOLD are dropped unless fewer than
# MIN_RESULTS would remain (kept as weak context, flagged relevant=False so they
# never surface as references — P3.8).
MIN_RESULTS = 2

# ── Phase 3 (P3.4): chunk context expansion ──────────────────────────────────
# When a leaf chunk is a hit, retrieve() augments it with the surrounding parent
# section + sibling text (read from the source .md at query time — zero re-embed
# cost). Cap the expanded context to keep prompts token-friendly.
MAX_CONTEXT_CHARS = 1400

# ── Rate limiting ─────────────────────────────────────────────────────────────
# gemini-embedding-2 free tier: varies; add a small sleep between batch calls
# during indexing to stay safely under limits.
EMBED_BATCH_SLEEP_SEC = 0.5  # seconds between batches during build_index

# ── Phase 5: confidence signaling ─────────────────────────────────────────────
# Maximum cosine distance for a chunk to be considered a "strong" match.
# Chunks above this threshold trigger a low-confidence disclaimer in the answer.
# Based on observed distances: good matches 0.20-0.26, weak matches 0.35+.
CONFIDENCE_THRESHOLD = 0.35