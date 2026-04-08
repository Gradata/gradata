"""Sliding-window query budgeting — rate limiting and burst detection.

Tracks per-endpoint call timestamps using ``time.monotonic()`` and a
``collections.defaultdict``.  Zero external dependencies.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class QueryBudget:
    """Sliding-window rate limiter with burst anomaly detection.

    Parameters
    ----------
    window_seconds:
        Length of the sliding window in seconds (default 300 = 5 min).
    max_calls:
        Maximum allowed calls per endpoint inside the window.
    """

    def __init__(self, window_seconds: float = 300, max_calls: int = 500) -> None:
        self.window_seconds = window_seconds
        self.max_calls = max_calls
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    # ── Core API ──────────────────────────────────────────────────────

    def record(self, endpoint: str) -> None:
        """Log a call timestamp for *endpoint*."""
        self._calls[endpoint].append(time.monotonic())

    def count(self, endpoint: str) -> int:
        """Return the number of calls for *endpoint* inside the current window.

        Expired entries are pruned as a side-effect.
        """
        self._prune(endpoint)
        return len(self._calls[endpoint])

    def is_rate_exceeded(self, endpoint: str) -> bool:
        """Return ``True`` if *endpoint* has exceeded ``max_calls``."""
        return self.count(endpoint) > self.max_calls

    def detect_anomalies(self, endpoint: str) -> dict:
        """Detect burst anomalies for *endpoint*.

        A burst is flagged when:
        1. There are at least 10 calls in the window, **and**
        2. The rate in the most recent 5-second sub-window exceeds 3x
           the average rate across the full window.

        Returns a dict with a ``burst`` boolean flag.
        """
        self._prune(endpoint)
        timestamps = list(self._calls[endpoint])

        if len(timestamps) < 10:
            return {"burst": False}

        now = time.monotonic()
        window_start = timestamps[0]
        window_duration = now - window_start
        if window_duration <= 0:
            return {"burst": False}

        # Split into recent (last 5s sub-window) vs older
        sub_window = 5.0
        cutoff = now - sub_window
        recent = [t for t in timestamps if t >= cutoff]
        older = [t for t in timestamps if t < cutoff]

        if not recent:
            return {"burst": False}

        # If all data falls within the sub-window, compare the last 20%
        # of timestamps against the first 80% by inter-arrival density
        if not older:
            ts_list = list(timestamps)
            n = len(ts_list)
            split = max(1, int(n * 0.8))
            first_chunk = ts_list[:split]
            last_chunk = ts_list[split:]
            if len(first_chunk) < 2 or not last_chunk:
                return {"burst": False}
            first_span = first_chunk[-1] - first_chunk[0]
            last_span = max(now - last_chunk[0], 1e-9)
            if first_span <= 0:
                return {"burst": False}
            first_rate = len(first_chunk) / first_span
            last_rate = len(last_chunk) / last_span
            return {"burst": last_rate > 3 * first_rate}

        # Normal case: compare recent sub-window rate to older rate
        older_duration = cutoff - window_start
        if older_duration <= 0:
            return {"burst": False}

        older_rate = len(older) / older_duration
        recent_duration = now - cutoff
        recent_rate = len(recent) / recent_duration

        return {"burst": recent_rate > 3 * older_rate}

    # ── Internals ─────────────────────────────────────────────────────

    def _prune(self, endpoint: str) -> None:
        """Remove timestamps older than the sliding window."""
        cutoff = time.monotonic() - self.window_seconds
        calls = self._calls[endpoint]
        # Binary-ish fast path: timestamps are monotonically ordered
        while calls and calls[0] < cutoff:
            calls.popleft()
