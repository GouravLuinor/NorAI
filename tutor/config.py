"""
config.py

Config block for the tutor package, following the same convention as
notes_generator.py / assessment_generator.py: constants up top, a
load_llm()-style function for client setup, .env loaded once on import.

Deliberately reuses GEMINI_API_KEY (not GOOGLE_API_KEY) as the env var
name, matching every other NorAI pipeline — langchain-google-genai
defaults to reading GOOGLE_API_KEY itself, but we pass the key
explicitly to ChatGoogleGenerativeAI instead of relying on that
default, so this package doesn't require a second, differently-named
API key env var alongside the one the rest of NorAI already uses.
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

# Constants

MODEL_NAME = "gemma-4-26b-a4b-it"

# Temperature for tutor responses. Slightly above 0 since conversational
# answers benefit from a little natural variation, but still fairly
# deterministic — this isn't creative writing, it's explaining material
# from a fixed source (and once Phase 3 adds retrieval, answers should
# stay close to the retrieved context rather than wandering).
TEMPERATURE = 0.4

CHECKPOINT_DIR = Path("outputs/tutor")
CHECKPOINT_DB_PATH = CHECKPOINT_DIR / "checkpoints.sqlite"


def get_api_key() -> str:
    """
    Read GEMINI_API_KEY from the environment, matching every other
    NorAI generator. Raises clearly rather than letting
    ChatGoogleGenerativeAI fail later with a less obvious error about
    a missing GOOGLE_API_KEY.
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY not found.")

    return api_key