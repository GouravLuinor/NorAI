"""
Retrieval configuration for Phase 3.
Kept separate from config.py so tutor core (LLM, checkpointer) and retrieval
(vector index, embeddings) can evolve independently without touching each other.
"""

import os

# ── Embedding model ───────────────────────────────────────────────────────────
# New indexes are built with EMBEDDING_MODEL; each index records its model and
# queries are embedded with that lecture's model, so both kinds keep working.
#   embeddinggemma-300m-q4 (default): on-box ONNX (tutor/local_embedding.py),
#     no API quota. The free Gemini embedding tier (100/min + a daily cap) ran
#     out first, at ~3.5 index docs per lecture-minute.
#   gemini-embedding-2: better retrieval (transcript hit@4: English .85 vs .83,
#     romanized Hinglish .87 vs .79) at an API call per 100 docs.
#     - Does NOT accept task_type= parameter — task instructions go in prompt text.
#     - gemini-embedding-exp-03-07 / gemini-embedding-001 are deprecated; don't use.
LOCAL_EMBEDDING_MODEL = "embeddinggemma-300m-q4"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_MODEL = os.environ.get("NORAI_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL)
EMBEDDING_DIMS = 768  # both models; 768 / 1536 / 3072 all recommended for Gemini.
# Indexes written before docs.json recorded a model were all Gemini.
LEGACY_INDEX_MODEL = GEMINI_EMBEDDING_MODEL

# ── Phase 4: screenshot retrieval ─────────────────────────────────────────────

TOP_K_IMAGES = 2  # Number of images to retrieve per query
# Screenshots further than this (cosine distance, caption+OCR vs question) are
# not shown to the model. Calibrated on the answer eval (tutor/evals) for
# Gemini; the local model's distances run larger, mapped at the same quantile.
IMAGE_MAX_DISTANCE_BY_MODEL = {GEMINI_EMBEDDING_MODEL: 0.30, LOCAL_EMBEDDING_MODEL: 0.55}

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
# Based on observed distances: good matches 0.20-0.26, weak matches 0.35+
# (Gemini); the local model's top hits sit at a median 0.40 (Gemini 0.23).
CONFIDENCE_THRESHOLD_BY_MODEL = {GEMINI_EMBEDDING_MODEL: 0.35, LOCAL_EMBEDDING_MODEL: 0.65}
CONFIDENCE_THRESHOLD = CONFIDENCE_THRESHOLD_BY_MODEL[GEMINI_EMBEDDING_MODEL]  # legacy default


def confidence_threshold(model: str) -> float:
    return CONFIDENCE_THRESHOLD_BY_MODEL.get(model, CONFIDENCE_THRESHOLD)


def image_max_distance(model: str) -> float:
    env = os.environ.get("NORAI_IMAGE_MAX_DISTANCE")
    return float(env) if env else IMAGE_MAX_DISTANCE_BY_MODEL.get(model, 0.30)