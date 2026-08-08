"""In-memory sliding window rate limiter for the /sub/{token} endpoint.

No Redis dependency — suitable for single-node deployments.
"""

from __future__ import annotations

import time
from collections import defaultdict

_DEFAULT_WINDOW_SECONDS = 60
_DEFAULT_MAX_REQUESTS = 10


class SlidingWindowRateLimiter:
    """Per-IP sliding window counter.

    Usage::

        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        if limiter.is_rate_limited("1.2.3.4"):
            return 429
    """

    def __init__(
        self,
        max_requests: int = _DEFAULT_MAX_REQUESTS,
        window_seconds: int = _DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # IP -> sorted list of request timestamps
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, ip: str) -> bool:
        """Return True if the IP has exceeded the limit within the window.

        Note: this method auto-records the request.  For login rate
        limiting where we only want to record failures, use
        ``check_only`` + ``_record_failure`` instead.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        # Prune old entries
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]
        if len(self._hits[ip]) >= self.max_requests:
            return True
        self._hits[ip].append(now)
        return False

    def check_only(self, ip: str) -> bool:
        """Check if rate-limited WITHOUT recording a hit.

        Used by the login endpoint: check first, then record only on failure.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]
        return len(self._hits[ip]) >= self.max_requests

    def _record_failure(self, ip: str) -> None:
        """Record a single failure hit for the given IP."""
        self._hits[ip].append(time.monotonic())

    def retry_after(self, ip: str) -> int:
        """Return seconds until the oldest request in the window expires."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]
        if not self._hits[ip]:
            return 1
        return max(1, int(self._hits[ip][0] - cutoff) + 1)


# Global instance shared across requests
subscription_rate_limiter = SlidingWindowRateLimiter()
