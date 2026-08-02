import time
import threading
import random

class RPMRateLimiter:
    """Allow at most `max_calls` per `window_seconds`."""
    def __init__(self, max_calls: int = 14, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls = []
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            self.calls = [t for t in self.calls if now - t < self.window]
            if len(self.calls) >= self.max_calls:
                sleep_time = self.window - (now - self.calls[0]) + random.uniform(0.5, 2.0)
                if sleep_time > 0:
                    print(f"Rate limit: sleeping {sleep_time:.1f}s")
                    time.sleep(sleep_time)
                    self.calls = [t for t in self.calls if time.time() - t < self.window]
            self.calls.append(time.time())


# Shared global rate limiter singleton across all pipeline modules
_limiter = RPMRateLimiter(max_calls=12, window_seconds=60.0)
rate_limiter = _limiter