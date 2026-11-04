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

# ── Shared Gemini Retry Policy (audit P5.2) ───────────────────────────────────
# THE single backoff formula used by backend/gemini_client.invoke_with_policy:
#   wait = RETRY_BACKOFF_BASE * (attempt + 1) + uniform(RETRY_JITTER_MIN,
#                                                       RETRY_JITTER_MAX)
# Attempt count comes from DEFAULT_MAX_RETRIES; every attempt is gated on the
# shared RPM limiter (DEFAULT_RPM_LIMIT / env NORAI_RPM_LIMIT). Env-tunable so
# deployments can soften/flatten the curve without code changes.
RETRY_BACKOFF_BASE = float(os.environ.get("NORAI_RETRY_BACKOFF_BASE", "5"))
RETRY_JITTER_MIN = float(os.environ.get("NORAI_RETRY_JITTER_MIN", "0.5"))
RETRY_JITTER_MAX = float(os.environ.get("NORAI_RETRY_JITTER_MAX", "3.0"))

# ── Transcription Backend & Chunking ─────────────────────────────────────────
NORAI_TRANSCRIPTION_BACKEND = os.environ.get("NORAI_TRANSCRIPTION_BACKEND", "gemini")
NORAI_AUDIO_CHUNK_MINUTES = int(os.environ.get("NORAI_AUDIO_CHUNK_MINUTES", "18"))

# ── Adaptive Chunking (P1.8 + Dynamic Content Scaling) ────────────────────────
# Long lectures get larger chunks so the structure call's chunk-tagged
# transcript stays a bounded number of chunks. TARGET_MAX_CHUNKS scales the
# chunk count; MAX_SEGMENTS_PER_CHUNK caps how large a single chunk may grow
# (≈ 2.8 min of audio at ~10.5 seg/min) so chapter boundaries stay fine-grained.
TARGET_MAX_CHUNKS = 40
MAX_SEGMENTS_PER_CHUNK = 30

# ── Pre-flight Estimator (P1.8) ───────────────────────────────────────────────
# Default segments-per-minute heuristic (measured: 88 whisper segments over a
# 505.76s lecture ≈ 10.44 seg/min). Re-fit from real runs via calibration.
DEFAULT_SEGS_PER_MIN = 10.5
# Free-trial duration gate (mirrors the env override used in orchestrator).
MAX_FREE_DURATION_MIN = int(os.environ.get("MAX_FREE_DURATION_MIN", "60"))
# Lecture-minutes every Free account gets per 30-day period. NorAI launches
# free-only on the Gemini free tier, so this is the main cost guard.
FREE_MONTHLY_MINUTES = int(os.environ.get("NORAI_FREE_MINUTES", "60"))
DEFAULT_TRIAL_QUOTA_MINUTES = FREE_MONTHLY_MINUTES

# ── Run mode & intake sources ────────────────────────────────────────────────
# One codebase, two ways to run it (see docs/INGESTION_PLAN.md):
#   NORAI_MODE=hosted (default): Supabase login, quotas, rate limits.
#   NORAI_MODE=local: a single-user install on your own PC with your own Gemini
#     key. No login (everything runs as the local user), no quotas, SQLite.
#     Bind to 127.0.0.1 only; the backend refuses to start with NORAI_ENV=production.
# Functions, not constants, so tests can flip the env at runtime.
# upload = a video or document file; link = any other http(s) URL (web page,
# Google Docs/Slides, Dropbox, direct file), fetched through documents/fetch.py.
SOURCE_TYPES = ("youtube", "gdrive", "upload", "link")
# yt-dlp is blocked on datacenter IPs (2026-11-01 probe), so hosted installs
# leave YouTube off unless NORAI_SOURCES names it.
_HOSTED_DEFAULT_SOURCES = ("gdrive", "upload", "link")


def run_mode() -> str:
    return "local" if os.environ.get("NORAI_MODE", "hosted").strip().lower() == "local" else "hosted"


def is_local_mode() -> bool:
    return run_mode() == "local"


def dev_access() -> bool:
    """True when the single local user owns everything on disk: local mode, or
    the developer flags NORAI_DEV_ACCESS / NORAI_DEV_INSECURE_AUTH."""
    return (
        is_local_mode()
        or os.environ.get("NORAI_DEV_ACCESS", "0") == "1"
        or os.environ.get("NORAI_DEV_INSECURE_AUTH", "0") == "1"
    )


def enabled_sources() -> tuple[str, ...]:
    """Intake source types this install accepts, in SOURCE_TYPES order.
    NORAI_SOURCES (comma-separated) overrides the per-mode default; unknown
    names are ignored."""
    raw = os.environ.get("NORAI_SOURCES", "").strip()
    if raw:
        wanted = {s.strip().lower() for s in raw.split(",") if s.strip()}
    else:
        wanted = set(SOURCE_TYPES if is_local_mode() else _HOSTED_DEFAULT_SOURCES)
    return tuple(s for s in SOURCE_TYPES if s in wanted)


# ── Feature Flags ────────────────────────────────────────────────────────────
ENABLE_PAYMENTS = os.environ.get("ENABLE_PAYMENTS", "0") == "1"

# ── Razorpay billing (INR: UPI, cards, netbanking, wallets) ──────────────────
# Use rzp_test_… keys outside production. The key id is public (sent to the
# checkout widget); the key secret and webhook secret must stay server-side.
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
# Checkout is live only when explicitly enabled AND both API keys exist.
PAYMENTS_ENABLED = ENABLE_PAYMENTS and bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

# Plan prices in whole rupees (GST-inclusive list price shown to users).
PLAN_STARTER_PRICE_INR = int(os.environ.get("PLAN_STARTER_PRICE_INR", "149"))
PLAN_PRO_PRICE_INR = int(os.environ.get("PLAN_PRO_PRICE_INR", "449"))

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
# Canonical IDs of the permanent public demo workspaces hydrated from
# seed_data/ at startup. Shared by backend/main.py (display + access bypass) and
# backend/jobs.py (gc_sweep must NEVER delete demo dirs — they have no DB row).
DEMO_LECTURE_IDS = frozenset({
    "8821152f-f6de-49e9-a885-0adaac6ba4cb",
    "01b04840-fddb-4b31-a211-7bb28f189621",
    "c8cab2e7-52b7-4cdc-8386-f440d02f3f45",
    "2e983ee0-ae41-4910-9239-099b34dee04c",
    "5f7225bf-ba41-46b9-aea9-da91c032b515",
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
# Explicit Gemini context caching for the tutor prefix (tutor/cache.py) is OFF
# by default. Measured 2026-10-27: on the free tier every create fails
# (cached-storage quota is 0) and costs two round trips per turn; on a paid key
# the cache is keyed per lecture but embeds a per-thread summary, so concurrent
# threads on one lecture delete each other's caches every turn. Gemini's
# implicit caching already discounts the stable system-prompt prefix.
TUTOR_CONTEXT_CACHE = os.environ.get("NORAI_TUTOR_CONTEXT_CACHE", "0") == "1"

# ── Pipeline Job Queue (P4.1) ─────────────────────────────────────────────────
# DB-backed queue + in-process worker pool (backend/jobs.py). Env-overridable.
# Two lanes, picked from the source (backend/jobs.job_lane): "video" runs ffmpeg
# + transcription (CPU-heavy), "document" only parses text and calls Gemini, so
# a PDF doesn't wait behind a 5-minute video. The Gemini RPM policy
# (backend/gemini_client.py) is shared by both. Per-user caps apply per lane.
MAX_CONCURRENT_PIPELINES = int(os.environ.get("NORAI_MAX_CONCURRENT_PIPELINES", "1"))  # video lane
MAX_CONCURRENT_DOC_PIPELINES = int(os.environ.get("NORAI_MAX_CONCURRENT_DOC_PIPELINES", "2"))
MAX_PER_USER_PIPELINES = int(os.environ.get("NORAI_MAX_PER_USER_PIPELINES", "1"))
# How often the supervisor scans for work / stale jobs.
PIPELINE_POLL_INTERVAL_SEC = 2.0
# A 'processing' job whose heartbeat is older than this is presumed stuck
# (crashed worker / server restart) and is re-queued or failed.
PIPELINE_STUCK_TIMEOUT_SEC = int(os.environ.get("NORAI_PIPELINE_STUCK_TIMEOUT_MIN", "15")) * 60
PIPELINE_MAX_ATTEMPTS = int(os.environ.get("NORAI_PIPELINE_MAX_ATTEMPTS", "3"))
# P2.1: hard wall-clock cap for a single pipeline run. The heartbeat thread
# stops refreshing past this, so the supervisor's stale-heartbeat recovery
# re-queues/fails the job — a hung yt-dlp/ffmpeg/Gemini call can no longer
# starve the worker slots forever.
PIPELINE_MAX_RUNTIME_SEC = int(os.environ.get("NORAI_PIPELINE_MAX_RUNTIME_MIN", "90")) * 60
# Worker touches heartbeat_at on the Lecture row every this many seconds so
# long single stages (e.g. transcription) never look stuck.
PIPELINE_HEARTBEAT_INTERVAL_SEC = 30
# A 'processing' job that THIS process is not running (its worker died with a
# restart / --reload) is re-queued once its heartbeat is this stale — three
# missed beats — instead of waiting out PIPELINE_STUCK_TIMEOUT_SEC, which now
# only applies to jobs still running in this process (hung stages).
PIPELINE_ORPHAN_TIMEOUT_SEC = int(os.environ.get("NORAI_PIPELINE_ORPHAN_TIMEOUT_SEC", str(3 * PIPELINE_HEARTBEAT_INTERVAL_SEC)))
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
