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
import re
import threading
import time
from typing import Any, Callable, TypeVar

import config
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


# ── 503 circuit breaker + fallback model ──────────────────────────────────────

def is_unavailable(err: BaseException) -> bool:
    """True for Gemini's "model overloaded" reply (HTTP 503 / UNAVAILABLE)."""
    return getattr(err, "code", None) == 503 or "UNAVAILABLE" in str(err)[:200]


class _FallbackBreaker:
    """Counts consecutive 503s from the primary model; once ``after`` of them
    land it stays open for ``cooldown`` seconds, during which calls go to the
    fallback model. Any primary success closes it."""

    def __init__(self, after: int, cooldown: float, clock: Callable[[], float] = time.monotonic):
        self.after, self.cooldown, self._clock = after, cooldown, clock
        self._fails = 0
        self._open_until = 0.0
        self._lock = threading.Lock()

    def is_open(self) -> bool:
        with self._lock:
            return self._clock() < self._open_until

    def record_failure(self) -> bool:
        """Note a primary 503; returns True if the breaker is open afterwards."""
        with self._lock:
            self._fails += 1
            if self._fails >= self.after:
                self._open_until = self._clock() + self.cooldown
                self._fails = 0
            return self._clock() < self._open_until

    def record_success(self) -> None:
        with self._lock:
            self._fails = 0


class _ModelsWithFallback:
    """``client.models`` with one change: generate_content falls back to
    ``fallback_model`` while the primary is returning 503s. Every other
    attribute is the SDK's own. Calls bound to a context cache are left alone
    (a cache belongs to one model)."""

    def __init__(self, models: Any, primary: str, fallback: str, breaker: _FallbackBreaker):
        self._models, self._primary, self._fallback, self._breaker = models, primary, fallback, breaker

    def __getattr__(self, name: str) -> Any:
        return getattr(self._models, name)

    def generate_content(self, *, model: str, **kwargs: Any) -> Any:
        cfg = kwargs.get("config")
        cached = (cfg.get("cached_content") if isinstance(cfg, dict) else getattr(cfg, "cached_content", None))
        if model != self._primary or cached:
            return self._models.generate_content(model=model, **kwargs)
        if self._breaker.is_open():
            return self._models.generate_content(model=self._fallback, **kwargs)
        try:
            resp = self._models.generate_content(model=model, **kwargs)
        except Exception as e:  # noqa: BLE001
            if is_unavailable(e) and self._breaker.record_failure():
                logger.warning("Gemini %s keeps returning 503; using %s for the next %.0fs",
                               self._primary, self._fallback, self._breaker.cooldown)
                return self._models.generate_content(model=self._fallback, **kwargs)
            raise
        self._breaker.record_success()
        return resp


class _ClientWithFallback:
    """The SDK client, with ``models`` swapped for the fallback-aware wrapper."""

    def __init__(self, client: Any, models: _ModelsWithFallback):
        self._client, self.models = client, models

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def get_client():
    """Return the process-wide ``google.genai.Client`` (thread-safe, lazy).

    Built from ``config.get_api_key()`` so .env loading and missing-key
    validation stay centralized. The first call constructs the client; every
    later call returns the cached instance. Requests time out after
    ``config.GEMINI_REQUEST_TIMEOUT_SEC`` (the retry policy then tries again),
    and generate_content falls back to ``config.FALLBACK_MODEL_NAME`` while the
    primary model keeps answering 503 (see ``_ModelsWithFallback``).
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                genai = _load_genai()
                from google.genai import types  # type: ignore

                client = genai.Client(
                    api_key=get_api_key(),
                    http_options=types.HttpOptions(timeout=int(config.GEMINI_REQUEST_TIMEOUT_SEC * 1000)),
                )
                fallback = config.FALLBACK_MODEL_NAME
                if fallback and fallback != config.MODEL_NAME:
                    breaker = _FallbackBreaker(config.GEMINI_FALLBACK_AFTER_503S,
                                               config.GEMINI_FALLBACK_COOLDOWN_SEC)
                    client = _ClientWithFallback(
                        client, _ModelsWithFallback(client.models, config.MODEL_NAME, fallback, breaker))
                _client = client
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


_RETRY_HINT_RE = re.compile(r"retry in ([0-9.]+)s|'retryDelay': '([0-9.]+)s'")
_MAX_HINTED_WAIT = 90.0


def _server_retry_hint(err: BaseException | None) -> float:
    """Seconds the API asked us to wait (429 RetryInfo), else 0. Retrying
    sooner than this just burns an attempt on another 429."""
    if err is None:
        return 0.0
    m = _RETRY_HINT_RE.search(str(err))
    if not m:
        return 0.0
    return min(float(m.group(1) or m.group(2)), _MAX_HINTED_WAIT)


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
            wait_time = max(_backoff_seconds(attempt), _server_retry_hint(last_err) + 1.0)
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


def empty_reason(resp: Any) -> str:
    """Why a generate_content reply carries no text: the prompt block reason
    or the first candidate's finish reason (e.g. SAFETY, RECITATION)."""
    if resp is None:
        return "no response"
    feedback = getattr(resp, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        return f"prompt blocked: {feedback.block_reason}"
    candidates = getattr(resp, "candidates", None) or []
    if not candidates:
        return "no candidates"
    return f"finish_reason={getattr(candidates[0], 'finish_reason', None)}"


def generate_nonempty(fn: Callable[[], Any], *, node: str, attempts: int = 3) -> Any:
    """``invoke_with_policy(fn)``, re-asking when the reply has no text.

    Flash-lite occasionally returns an empty candidate for a prompt that
    succeeds when re-sent; a deterministic block (SAFETY/RECITATION) comes
    back every time, so the extra asks are capped. Raises ValueError (with the
    finish reason) once ``attempts`` replies were all empty.
    """
    resp = None
    for attempt in range(attempts):
        resp = invoke_with_policy(fn, node=node)
        if resp is not None and resp.text:
            return resp
        logger.warning("[%s] empty response (%s), attempt %d/%d",
                       node, empty_reason(resp), attempt + 1, attempts)
    raise ValueError(f"[{node}] empty or blocked response after {attempts} attempts ({empty_reason(resp)})")
