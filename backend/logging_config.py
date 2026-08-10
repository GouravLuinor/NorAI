"""
backend/logging_config.py — P5.1 structured logging.

JSON-formatted, rotating log to `outputs/backend.log` plus a human-readable
console stream. Context (request_id, lecture_id, thread_id, task_id) is carried
via contextvars and merged into every JSON record, so multi-stage work (HTTP
requests, pipeline jobs, chat turns) is traceable end-to-end.

Usage:
    from backend.logging_config import setup_logging, bind, clear_context

    setup_logging()          # once at app startup (idempotent)
    bind(lecture_id="lec-1") # from a handler / worker before logging
    clear_context()          # when the request / job finishes
"""

import contextvars
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path("outputs/backend.log")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("norai_log_ctx", default={})


def bind(**kwargs) -> None:
    """Merge key/value context into the current (request/job) log context."""
    current = dict(_ctx.get())
    current.update(kwargs)
    _ctx.set(current)


def clear_context() -> None:
    """Reset the log context (call when a request/job finishes)."""
    _ctx.set({})


def get_context() -> dict:
    """Current bound log context (used by the tutor LLM usage logger)."""
    return dict(_ctx.get())


class JsonFormatter(logging.Formatter):
    """Render one JSON object per log line, merged with bound context."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(_ctx.get())
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """Idempotently configure the root logger: console + rotating JSON file."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    root.addHandler(console)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)
