"""Minimal ULID generator — no external dependency.

26-char Crockford base32 string: 10 chars of 48-bit millisecond timestamp
+ 16 chars of 80-bit randomness. Lexicographically sortable by time,
globally unique in practice (collision probability 1/2^80 within a ms).

We roll our own because adding a dep for ~20 lines of code is not worth
the supply-chain surface. If a future caller needs the full `python-ulid`
API (monotonic, parsing back to components), swap this out.
"""

from __future__ import annotations

import os
import time

# Crockford base32: no I, L, O, U.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_ulid(ts_ms: int | None = None) -> str:
    """Return a new ULID string. ``ts_ms`` lets callers backfill historical ts."""
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    ts_ms &= (1 << 48) - 1
    rand = int.from_bytes(os.urandom(10), "big")
    return _encode(ts_ms, 10) + _encode(rand, 16)


def ulid_from_iso(iso_ts: str) -> str:
    """Build a ULID whose timestamp component matches ``iso_ts`` (ISO 8601).

    Used by Migration 002 to backfill event_id on historical rows so the
    leading 10 chars still sort-align with the original ``events.ts``.
    """
    from datetime import UTC, datetime

    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return new_ulid()
    # Naive ISO strings (no tzinfo) yield local-time ts on ``dt.timestamp()``,
    # which makes ULID backfill non-deterministic across machines. Treat
    # missing tzinfo as UTC — matches how the events pipeline stores ``ts``.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    ts_ms = int(dt.timestamp() * 1000)
    return new_ulid(ts_ms=ts_ms)
