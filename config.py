"""
config.py — Centralized Configuration for NorAI Pipeline and Subsystems.

This top-level file defines canonical constants, environment setup,
and API key resolution used across backend, ingestion, visual, extraction,
notes generation, assessment, flashcards, and tutor modules.
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# ── Canonical Pipeline & LLM Defaults ─────────────────────────────────────────
MODEL_NAME = "gemini-3.1-flash-lite"
DEFAULT_MODEL_NAME = MODEL_NAME

DEFAULT_FRAME_INTERVAL_SECONDS = 8
DEFAULT_SEGMENTS_PER_CHUNK = 15
DEFAULT_MAX_RETRIES = 8
DEFAULT_RPM_LIMIT = 12
MAX_FRAME_HEIGHT = 720  # Max screenshot resolution (720p) for storage & OCR efficiency

TEMPERATURE = 0.4

# ── Transcription Backend & Chunking ─────────────────────────────────────────
NORAI_TRANSCRIPTION_BACKEND = os.environ.get("NORAI_TRANSCRIPTION_BACKEND", "gemini")
NORAI_AUDIO_CHUNK_MINUTES = int(os.environ.get("NORAI_AUDIO_CHUNK_MINUTES", "18"))

# ── Adaptive Chunking (P1.8 + Dynamic Content Scaling) ────────────────────────
# Long lectures get larger chunks so the number of extraction LLM calls stays
# bounded. TARGET_MAX_CHUNKS scales the chunk count; MAX_SEGMENTS_PER_CHUNK
# caps how large a single chunk may grow (≈ 2.8 min of audio at ~10.5 seg/min)
# ensuring fine-grained technical concepts are never over-compressed.
TARGET_MAX_CHUNKS = 40
MAX_SEGMENTS_PER_CHUNK = 30

# ── Pre-flight Estimator (P1.8) ───────────────────────────────────────────────
# Default segments-per-minute heuristic (measured: 88 whisper segments over a
# 505.76s lecture ≈ 10.44 seg/min). Re-fit from real runs via calibration.
DEFAULT_SEGS_PER_MIN = 10.5
# Free-trial duration gate (mirrors the env override used in orchestrator).
MAX_FREE_DURATION_MIN = int(os.environ.get("MAX_FREE_DURATION_MIN", "15"))

# ── Lemon Squeezy billing (P2.5) ──────────────────────────────────────────────
# Env-driven checkout / customer-portal URLs surfaced by GET /billing.
# Leave unset until the store exists — /billing returns null for them.
LEMONSQUEEZY_CHECKOUT_STARTER_URL = os.environ.get("LEMONSQUEEZY_CHECKOUT_STARTER_URL", "")
LEMONSQUEEZY_CHECKOUT_PRO_URL = os.environ.get("LEMONSQUEEZY_CHECKOUT_PRO_URL", "")
LEMONSQUEEZY_CUSTOMER_PORTAL_URL = os.environ.get("LEMONSQUEEZY_CUSTOMER_PORTAL_URL", "")

# ── Model pricing (P6.5) ──────────────────────────────────────────────────────
# USD per 1M tokens used by the cost dashboard (`GET /usage`). Sources:
#   gemini-3.1-flash-lite — $0.25 input / $1.50 output / $0.025 cached input
#   gemini-3.5-flash-lite — $0.30 input / $2.50 output / $0.03 cached input
#   gemini-embedding-2   — $0.20 input / $0.00 output
def _price(name: str, default: float) -> float:
    return float(os.environ.get(f"NORAI_MODEL_PRICE_{name}", str(default)))

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-3.1-flash-lite": {
        "input_per_1M": _price("FLASH_LITE_INPUT", 0.25),
        "output_per_1M": _price("FLASH_LITE_OUTPUT", 1.50),
        "cached_input_per_1M": _price("FLASH_LITE_CACHED_INPUT", 0.025),
    },
    "gemini-3.5-flash-lite": {
        "input_per_1M": _price("FLASH_35_LITE_INPUT", 0.30),
        "output_per_1M": _price("FLASH_35_LITE_OUTPUT", 2.50),
        "cached_input_per_1M": _price("FLASH_35_LITE_CACHED_INPUT", 0.03),
    },
    "gemini-embedding-2": {
        "input_per_1M": _price("EMBEDDING_INPUT", 0.20),
        "output_per_1M": _price("EMBEDDING_OUTPUT", 0.0),
    },
}


def model_price(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
) -> float:
    """Estimated USD cost for a call against `model` (fallback: $0, unknown model).

    P7.x: cached input tokens (served from a context cache) are billed at the
    model's cached rate, which is cheaper than regular input. `input_tokens`
    should be the NON-cached portion; pass `cached_input_tokens` separately so
    the two rates are never mixed.
    """
    price = MODEL_PRICING.get(model)
    if price is None:
        return 0.0
    return (
        (input_tokens / 1_000_000) * price.get("input_per_1M", 0.0)
        + (cached_input_tokens / 1_000_000) * price.get("cached_input_per_1M", 0.0)
        + (output_tokens / 1_000_000) * price.get("output_per_1M", 0.0)
    )

# ── YouTube PO-token provider (P8.x) ──────────────────────────────────────────
# The Docker image runs `bgutil-pot server` (bgutil-ytdlp-pot-provider-rs) on
# this host/port. yt-dlp's `web` client issues a proof-of-origin token through
# the provider so downloads survive YouTube's bot check on datacenter IPs. When
# unset / unreachable, ingest falls back to the non-POT strategies below.
POT_SERVER_URL = os.environ.get("NORAI_POT_SERVER_URL", "http://127.0.0.1:4416")

# ── Seeded Public Demo Lectures (P5.4) ───────────────────────────────────────
# Canonical IDs of the 3 permanently-public demo workspaces hydrated from
# seed_data/ at startup. Shared by backend/main.py (display + access bypass) and
# backend/jobs.py (gc_sweep must NEVER delete demo dirs — they have no DB row).
DEMO_LECTURE_IDS = frozenset({
    "ab648382-638f-4dde-b7c1-4007a2e638bb",
    "e54d7376-0e7b-472a-9ca6-9b21ad0b2710",
    "506dd685-05f9-43df-8d09-5b944c7392f5",
})

# ── Directory & Database Paths ────────────────────────────────────────────────
OUTPUTS_DIR = Path("outputs")
CHECKPOINT_DIR = OUTPUTS_DIR / "tutor"
CHECKPOINT_DB_PATH = CHECKPOINT_DIR / "checkpoints.sqlite"

# ── Tutor Graph Cache (P4.4) ──────────────────────────────────────────────────
# Each lecture caches its own compiled graph + AsyncSqliteSaver connection in
# backend/dependencies.py. Cap the cache (LRU) so long-lived processes don't
# leak an unbounded number of open sqlite connections / compiled graphs.
TUTOR_MAX_CACHED_GRAPHS = int(os.environ.get("NORAI_TUTOR_MAX_CACHED_GRAPHS", "32"))

# ── Tutor Context Cache (P7.x) ────────────────────────────────────────────────
# Gemini context caching for long conversations: a rolling prefix (system prompt
# + persona + summary + stable lecture context) is cached and reused across
# turns at the discounted cached-input rate. TTL is short because the prefix is
# re-created whenever the conversation summary changes (see tutor/cache.py).
TUTOR_CACHE_TTL_SECONDS = int(os.environ.get("NORAI_TUTOR_CACHE_TTL_SECONDS", "1800"))

# ── Pipeline Job Queue (P4.1) ─────────────────────────────────────────────────
# DB-backed queue + in-process worker pool (backend/jobs.py). Env-overridable.
MAX_CONCURRENT_PIPELINES = int(os.environ.get("NORAI_MAX_CONCURRENT_PIPELINES", "1"))
MAX_PER_USER_PIPELINES = int(os.environ.get("NORAI_MAX_PER_USER_PIPELINES", "1"))
# How often the supervisor scans for work / stale jobs.
PIPELINE_POLL_INTERVAL_SEC = 2.0
# A 'processing' job whose heartbeat is older than this is presumed stuck
# (crashed worker / server restart) and is re-queued or failed.
PIPELINE_STUCK_TIMEOUT_SEC = int(os.environ.get("NORAI_PIPELINE_STUCK_TIMEOUT_MIN", "15")) * 60
PIPELINE_MAX_ATTEMPTS = int(os.environ.get("NORAI_PIPELINE_MAX_ATTEMPTS", "3"))
# Worker touches heartbeat_at on the Lecture row every this many seconds so
# long single stages (e.g. transcription) never look stuck.
PIPELINE_HEARTBEAT_INTERVAL_SEC = 30
# P4.2 — GC: upload files older than this are purged; lecture dirs with no DB
# row and older than this are purged.
UPLOAD_GC_AGE_HOURS = 24
ORPHAN_DIR_GC_AGE_DAYS = 7

# Append-only JSONL recording every pipeline run's actuals + planned values.
# The estimator re-fits its heuristics from this file (see backend/estimator.py).
METRICS_FILE = Path(os.environ.get("NORAI_METRICS_FILE", "outputs/pipeline_metrics.jsonl"))


def get_api_key() -> str:
    """
    Read GEMINI_API_KEY from environment.
    Raises ValueError if key is not found.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment.")
    return api_key
