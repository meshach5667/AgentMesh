"""In-process rate and concurrency limits for the inference gateway.

These limits are per control-plane process. Running several API replicas multiplies the effective limit;
a shared store (Redis) is required before horizontal scaling. This is documented in the plan.
"""

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> tuple[bool, float]:
        """Record a hit if under ``limit``. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= limit:
            return False, max(0.0, self.window - (now - hits[0]))
        hits.append(now)
        return True, 0.0

    def reset(self) -> None:
        self._hits.clear()


class ConcurrencyLimiter:
    def __init__(self):
        self._active: dict[str, int] = defaultdict(int)

    def acquire(self, key: str, limit: int) -> bool:
        if self._active[key] >= limit:
            return False
        self._active[key] += 1
        return True

    def release(self, key: str) -> None:
        self._active[key] = max(0, self._active[key] - 1)
        if not self._active[key]:
            del self._active[key]

    def reset(self) -> None:
        self._active.clear()


request_limiter = SlidingWindowLimiter()
concurrency_limiter = ConcurrencyLimiter()
