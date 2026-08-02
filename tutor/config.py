"""
tutor/config.py — Re-exports configuration from top-level config.py for tutor subsystem.
"""

from config import (
    MODEL_NAME,
    DEFAULT_MODEL_NAME,
    DEFAULT_FRAME_INTERVAL_SECONDS,
    DEFAULT_SEGMENTS_PER_CHUNK,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RPM_LIMIT,
    TEMPERATURE,
    CHECKPOINT_DIR,
    CHECKPOINT_DB_PATH,
    get_api_key,
)