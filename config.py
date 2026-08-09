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

TEMPERATURE = 0.4

# ── Adaptive Chunking (P1.8) ──────────────────────────────────────────────────
# Long lectures get larger chunks so the number of extraction LLM calls stays
# bounded. TARGET_MAX_CHUNKS caps the target chunk count; MAX_SEGMENTS_PER_CHUNK
# caps how large a single chunk may grow (≈ 5.5 min of audio at ~10.5 seg/min).
TARGET_MAX_CHUNKS = 24
MAX_SEGMENTS_PER_CHUNK = 60

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

# ── Directory & Database Paths ────────────────────────────────────────────────
OUTPUTS_DIR = Path("outputs")
CHECKPOINT_DIR = OUTPUTS_DIR / "tutor"
CHECKPOINT_DB_PATH = CHECKPOINT_DIR / "checkpoints.sqlite"

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
