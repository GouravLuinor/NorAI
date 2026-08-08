import time
import threading
import random

from config import DEFAULT_RPM_LIMIT

class RPMRateLimiter:
    """Allow at most `max_calls` per `window_seconds` using atomic lock checks."""
    def __init__(self, max_calls: int = DEFAULT_RPM_LIMIT, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls = []
        self.lock = threading.Lock()

    def wait(self):
        global TOTAL_LLM_CALLS
        while True:
            sleep_time = 0
            with self.lock:
                now = time.time()
                self.calls = [t for t in self.calls if now - t < self.window]
                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    TOTAL_LLM_CALLS += 1
                    return
                sleep_time = self.window - (now - self.calls[0]) + random.uniform(0.5, 1.5)

            if sleep_time > 0:
                time.sleep(sleep_time)


# Shared global rate limiter singleton across all pipeline modules
# Honours config.DEFAULT_RPM_LIMIT (single source of truth).
_limiter = RPMRateLimiter(max_calls=DEFAULT_RPM_LIMIT, window_seconds=60.0)
rate_limiter = _limiter

# P1.8: monotonically increasing count of rate-limited LLM calls. Every Gemini
# generateContent call in the pipeline passes through `wait()` on this
# singleton, so a per-run delta (snapshot before/after run_pipeline) gives the
# real number of LLM calls — the calibration data for backend/estimator.py.
TOTAL_LLM_CALLS = 0


def reset_call_counter() -> None:
    """Reset the call counter (used by tests)."""
    global TOTAL_LLM_CALLS
    TOTAL_LLM_CALLS = 0


def snapshot_llm_calls() -> int:
    return TOTAL_LLM_CALLS