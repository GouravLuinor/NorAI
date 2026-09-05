"""
backend/gemini_client.py — Shared Gemini client factory + single retry/RPM
policy (audit Phase 5.2).

ONE construction site for google.genai.Client across the repo:

    from backend.gemini_client import get_client, invoke_with_policy

    client = get_client()           # thread-safe, cached, built lazily from
                                    # config.get_api_key() — never at import time

    text = invoke_with_policy(      # THE retry/RPM policy for Gemini calls
        lambda: client.models.generate_content(...),
        node="notes",
    )

Policy (single source of truth — do NOT hand-roll backoff loops):
  * RPM: every attempt is gated on backend.ratelimit.rate_limiter, which reads
    config.DEFAULT_RPM_LIMIT (env: NORAI_RPM_LIMIT). Callables must NOT call
    `_limiter.wait()` themselves any more — one wait per attempt, counted once.
    Embedding calls opt out (`rate_limited=False`): they draw on a separate
    quota and were never rate-limited.
  * Backoff: config.RETRY_BACKOFF_BASE * (attempt + 1) +
    uniform(config.RETRY_JITTER_MIN, config.RETRY_JITTER_MAX) seconds between
    attempts (5s, 10s, 15s, … + jitter by default).
  * Attempts: config.DEFAULT_MAX_RETRIES unless overridden per call.
  * Terminal errors are NEVER retried: ValueError and its subclasses (this
    codebase's terminal/validation semantics — cf. orchestrator's
    TerminalPipelineError(ValueError)) propagate immediately. Opt back in with
    retry_value_errors=True ONLY where a ValueError is a deliberate transient
    signal (e.g. an empty/blocked LLM response worth one more try).
  * Exhaustion raises RuntimeError(f"[{node}] failed after N retries.") — the
    same failure contract the previous hand-rolled loops exposed to callers
    and to backend/jobs.py's stage-failure handling.

Importing this module performs no SDK import and builds no network client;
the google.genai import and Client construction both happen lazily inside
get_client().
"""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any, Callable, TypeVar

from config import (
    DEFAULT_MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    RETRY_JITTER_MAX,
    RETRY_JITTER_MIN,
    get_api_key,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ── Shared client factory ─────────────────────────────────────────────────────

_genai: Any | None = None  # cached google.genai module (lazy SDK import)
_client: Any | None = None  # cached genai.Client (lazy construction)
_client_lock = threading.Lock()


def _load_genai() -> Any:
    """Import google-genai on first use so importing this module stays free of
    third-party dependencies (offline tests import the factory freely)."""
    global _genai
    if _genai is None:
        try:
            from google import genai as _g  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "google-genai is required. Install it with: pip install google-genai"
            ) from exc
        _genai = _g
    return _genai


def get_client():
    """Return the process-wide ``google.genai.Client`` (thread-safe, lazy).

    Built from ``config.get_api_key()`` so .env loading and missing-key
    validation stay centralized. The first call constructs the client; every
    later call returns the cached instance.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = _load_genai().Client(api_key=get_api_key())
    return _client


def reset_client() -> None:
    """Drop the cached client (used by tests); next get_client() rebuilds it."""
    global _client
    with _client_lock:
        _client = None


# ── THE single retry/RPM policy ───────────────────────────────────────────────

def _backoff_seconds(attempt: int) -> float:
    """Shared exponential-backoff wait before the next attempt."""
    return RETRY_BACKOFF_BASE * (attempt + 1) + random.uniform(
        RETRY_JITTER_MIN, RETRY_JITTER_MAX
    )


def invoke_with_policy(
    fn: Callable[[], T],
    *,
    node: str,
    max_retries: int | None = None,
    rate_limited: bool = True,
    retry_value_errors: bool = False,
) -> T:
    """Run ``fn()`` under THE shared Gemini retry/RPM policy; return its result.

    Args:
        fn: zero-arg callable performing exactly ONE API attempt (RPM gating
            is applied around it — do not wait inside).
        node: short stage/node label used in log lines (e.g. "notes",
            "extract", "Chapter 3 visual batch").
        max_retries: total attempts allowed; defaults to config's
            DEFAULT_MAX_RETRIES.
        rate_limited: gate each attempt on the shared RPM limiter
            (config.DEFAULT_RPM_LIMIT / env NORAI_RPM_LIMIT). Embeddings pass
            False (separate quota, never gated).
        retry_value_errors: False (default) treats ValueError subclasses as
            terminal/validation failures and re-raises immediately without
            burning retries. Set True only where a ValueError is a deliberate
            transient retry signal (empty/blocked response semantics).

    Raises:
        ValueError: terminal/validation error, propagated without retrying
            (unless retry_value_errors=True).
        RuntimeError: after ``max_retries`` failed attempts (chained to the
            last underlying error), matching the old hand-rolled loops.
    """
    attempts = max_retries if max_retries is not None else DEFAULT_MAX_RETRIES

    # Local import keeps this module's dependency graph config-only at import
    # time (backend.ratelimit itself only reads config constants).
    from backend.ratelimit import rate_limiter as limiter

    last_err: BaseException | None = None
    for attempt in range(attempts):
        try:
            if rate_limited:
                limiter.wait()
            return fn()
        except ValueError as e:
            if not retry_value_errors:
                logger.warning(
                    "[%s] terminal/validation error, not retrying: %s", node, e
                )
                raise
            last_err = e
        except Exception as e:  # noqa: BLE001
            from backend.rate_limit_handler import (
                GeminiCooldownTracker,
                GeminiDailyQuotaExceededException,
                is_daily_quota_exhausted,
            )
            if is_daily_quota_exhausted(e):
                logger.error(
                    "[%s] Gemini daily quota (500 RPD) exhausted: %s. Aborting retries.",
                    node,
                    e,
                )
                GeminiCooldownTracker.record_daily_exhaustion()
                raise GeminiDailyQuotaExceededException() from e

            last_err = e

        if attempt < attempts - 1:
            wait_time = _backoff_seconds(attempt)
            logger.warning(
                "[%s] attempt %d/%d failed (%s); retrying in %.1fs...",
                node,
                attempt + 1,
                attempts,
                last_err,
                wait_time,
            )
            time.sleep(wait_time)

    raise RuntimeError(f"[{node}] failed after {attempts} retries.") from last_err
