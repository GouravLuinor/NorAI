"""P1 abuse-protection middleware: inbound rate limiting + security headers.

Single-container friendly (in-process state, no Redis). Two pure-ASGI
middlewares keep SSE streaming untouched (no BaseHTTPMiddleware buffering):

- RateLimitMiddleware: token-bucket limits keyed by caller identity
  (bearer-token hash > X-Guest-Id > client IP) per route family.
- SecurityHeadersMiddleware: nosniff / DENY / Referrer-Policy / HSTS /
  production-only CSP applied to every response, including 429s.

Limits are deliberately generous for legit users and only trip under abuse;
tune via NORAI_RATE_* env vars without code changes.
"""

import hashlib
import math
import os
import re
import time

__all__ = [
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "DailyCounter",
]


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


# ── Route families ────────────────────────────────────────────────────────────
# (path regex, bucket name, capacity env var, default capacity, window seconds)
#
# NOTE: poll routes MUST be listed first — middleware matches the first rule
# that fires. Status polling + quota checks need a generous bucket (120/min)
# so the pipeline progress bar never triggers a 429 storm (BUG-05 fix).
_RATE_RULES = [
    # Exempt status polling + quota from strict bucketing (2/sec is plenty).
    (re.compile(r"^/process/[^/]+/status$"), "poll", "NORAI_RATE_POLL", 120, 60),
    (re.compile(r"^/quota$"), "poll", "NORAI_RATE_POLL", 120, 60),
    (re.compile(r"^/chat"), "chat", "NORAI_RATE_CHAT", 30, 60),
    (re.compile(r"^/quiz/"), "quiz", "NORAI_RATE_QUIZ", 30, 60),
    (re.compile(r"^/(process|estimate)\b"), "process", "NORAI_RATE_PROCESS", 10, 3600),
    (re.compile(r"^/threads\b"), "threads", "NORAI_RATE_THREADS", 60, 60),
]

_PRUNE_EVERY = 4096
_IDLE_EVICT_SECONDS = 7200


class _TokenBucketLimiter:
    def __init__(self, capacity: int, window_seconds: float):
        self.capacity = float(capacity)
        self.refill_per_sec = capacity / window_seconds
        self.window_seconds = window_seconds
        # key -> (tokens, last_refill_monotonic)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._ops = 0

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
        allowed = tokens >= 1.0
        self._buckets[key] = (tokens - 1.0, now) if allowed else (tokens, now)
        self._ops += 1
        if self._ops % _PRUNE_EVERY == 0:
            cutoff = now - max(self.window_seconds * 2, _IDLE_EVICT_SECONDS)
            self._buckets = {k: v for k, v in self._buckets.items() if v[1] > cutoff}
        return allowed

    def retry_after(self, key: str) -> int:
        tokens, last = self._buckets.get(key, (self.capacity, time.monotonic()))
        deficit = 1.0 - min(
            self.capacity, tokens + (time.monotonic() - last) * self.refill_per_sec
        )
        if deficit <= 0:
            return 1
        return max(1, math.ceil(deficit / self.refill_per_sec))


_limiters = {
    name: _TokenBucketLimiter(_env_int(env, default), window)
    for _pattern, name, env, default, window in _RATE_RULES
}


def _identity(scope) -> str:
    headers = {
        k.decode("latin-1").lower(): v.decode("latin-1")
        for k, v in scope.get("headers", [])
    }
    auth = headers.get("authorization", "")
    if auth.startswith(("Bearer ", "bearer ")):
        # Stable per-credential key without decoding/validating the JWT here.
        return "u:" + hashlib.sha256(auth.encode()).hexdigest()[:16]
    guest = headers.get("x-guest-id", "")
    if guest:
        return "g:" + guest[:48]
    client = scope.get("client")
    if client and client[0]:
        return "ip:" + str(client[0])
    return "anon"


class RateLimitMiddleware:
    """Token-bucket rate limiting on abuse-sensitive route families."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        matched = None
        for pattern, name, _env, _default, _window in _RATE_RULES:
            if pattern.match(path):
                matched = name
                break
        if matched is None:
            await self.app(scope, receive, send)
            return

        key = f"{matched}:{_identity(scope)}"
        limiter = _limiters[matched]
        if limiter.allow(key):
            await self.app(scope, receive, send)
            return

        retry = str(limiter.retry_after(key)).encode()
        body = (
            b'{"detail": "You\'re going too fast. Please wait a moment and try again."}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", retry),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


# ── Security headers ──────────────────────────────────────────────────────────
# CSP enforced only in production: dev relies on Vite HMR/inline bootstrap.
# img-src covers the markdown image allowlist (markdown.tsx mirrors this list).
_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob: https://i.ytimg.com https://img.youtube.com "
        "https://upload.wikimedia.org https://commons.wikimedia.org",
        "media-src 'self' blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
    ]
)


class SecurityHeadersMiddleware:
    """Baseline security headers on every HTTP response.

    CSP is added only when NORAI_ENV=production|prod so local Vite dev
    (inline bootstrap / HMR websockets) keeps working untouched.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _v in headers}

                def add(name: bytes, value: bytes):
                    if name not in present:
                        headers.append((name, value))

                add(b"x-content-type-options", b"nosniff")
                add(b"x-frame-options", b"DENY")
                add(b"referrer-policy", b"strict-origin-when-cross-origin")
                # HSTS only makes sense behind TLS (Render/Caddy terminate it).
                proto = b""
                for k, v in scope.get("headers", []):
                    if k.lower() == b"x-forwarded-proto":
                        proto = v
                        break
                if proto == b"https":
                    add(
                        b"strict-transport-security",
                        b"max-age=31536000; includeSubDomains",
                    )
                if os.environ.get("NORAI_ENV", "").lower() in ("production", "prod"):
                    add(b"content-security-policy", _CSP.encode())
            await send(message)

        await self.app(scope, receive, send_with_headers)


class DailyCounter:
    """Per-key counters that reset when the UTC date changes.

    Used for guest lecture caps (keyed by IP) and the global demo-tutor
    budget (single fixed key). In-memory by design — a restart resets it,
    which merely widens the window for one day and is acceptable here.
    """

    def __init__(self, limit: int):
        self.limit = limit
        self._day = ""
        self._counts: dict[str, int] = {}

    def check_and_increment(self, key: str) -> bool:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if today != self._day:
            self._day = today
            self._counts = {}
        current = self._counts.get(key, 0)
        if current >= self.limit:
            return False
        self._counts[key] = current + 1
        return True

    @property
    def remaining(self) -> int:
        return max(0, self.limit - sum(self._counts.values()))
