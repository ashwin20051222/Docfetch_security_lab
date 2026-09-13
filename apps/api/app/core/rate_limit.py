from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.config import get_settings


class SlidingWindowLimiter:
    """In-memory sliding-window rate limiter keyed by (group, client_key).

    Per-process only. A multi-worker deployment should back this with Redis;
    the configuration surface exposed via /api/v1/health remains identical.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, window_seconds: float = 60.0, limit: int = 30) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > window_seconds:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True

    def remaining(self, key: str, window_seconds: float = 60.0, limit: int = 30) -> int:
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > window_seconds:
                dq.popleft()
            return max(0, limit - len(dq))

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitRule:
    def __init__(self, group: str, limit: int):
        self.group = group
        self.limit = limit


def default_rules() -> dict[str, RateLimitRule]:
    s = get_settings()
    return {
        "analyze": RateLimitRule("analyze", s.rate_limit_per_minute),
        "upload": RateLimitRule("upload", s.rate_limit_per_minute),
        "download": RateLimitRule("download", s.download_rate_per_minute),
        "lab": RateLimitRule("lab", s.rate_limit_per_minute),
    }


limiter = SlidingWindowLimiter()

__all__ = ["limiter", "client_key", "RateLimitRule", "default_rules"]