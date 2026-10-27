"""
Retrieval configuration for Phase 3.
Kept separate from config.py so tutor core (LLM, checkpointer) and retrieval
(vector index, embeddings) can evolve independently without touching each other.
"""

import os

# ── Embedding model ───────────────────────────────────────────────────────────
# gemini-embedding-2: stable GA model (April 2026).
# - Does NOT accept task_type= parameter — task instructions go in prompt text.
# - Auto-normalises truncated dims, so 768 cosine similarity is accurate OOTB.
# - gemini-embedding-exp-03-07 / gemini-embedding-001 are deprecated; don't use.
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 768  # 768 / 1536 / 3072 all recommended; 768 saves storage.

# ── Phase 4: screenshot retrieval ─────────────────────────────────────────────

TOP_K_IMAGES = 2  # Number of images to retrieve per query
# Screenshots further than this (cosine distance, caption+OCR vs question) are
# not shown to the model. Calibrated on the answer eval (tutor/evals).
IMAGE_MAX_DISTANCE = float(os.environ.get("NORAI_IMAGE_MAX_DISTANCE", "0.30"))

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K = 5  # chunks returned per query (single-kind lookups)
# Mixed lookups: transcript windows (what was said) + note sections (summary).
TOP_K_TRANSCRIPT = int(os.environ.get("NORAI_TOP_K_TRANSCRIPT", "4"))
TOP_K_NOTES = int(os.environ.get("NORAI_TOP_K_NOTES", "2"))

# ── Phase 3 (P3.2): hybrid search & adaptive top-k ────────────────────────────
# Cosine and BM25 each return this many candidates; the two ranked
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

# ── Phase 5: confidence signaling ─────────────────────────────────────────────
# Maximum cosine distance for a chunk to be considered a "strong" match.
# Chunks above this threshold trigger a low-confidence disclaimer in the answer.
# Based on observed distances: good matches 0.20-0.26, weak matches 0.35+.
CONFIDENCE_THRESHOLD = 0.35