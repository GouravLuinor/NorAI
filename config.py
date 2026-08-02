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

# ── Directory & Database Paths ────────────────────────────────────────────────
OUTPUTS_DIR = Path("outputs")
CHECKPOINT_DIR = OUTPUTS_DIR / "tutor"
CHECKPOINT_DB_PATH = CHECKPOINT_DIR / "checkpoints.sqlite"


def get_api_key() -> str:
    """
    Read GEMINI_API_KEY from environment.
    Raises ValueError if key is not found.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment.")
    return api_key
