"""POST /telemetry/event — anonymous SDK activation events.

This endpoint is public (no auth). It accepts a tiny fixed-shape JSON
body from the SDK and writes it to ``telemetry_events``. It is strictly
opt-in on the SDK side; by the time a request reaches here, the user
has already consented.

Defensive posture
-----------------
- **Always 202**: never surface 4xx or 5xx to clients. Bots can't map
  our internals by probing, and a transient DB hiccup can't break the
  SDK's activation path.
- **Rate limit**: 100/min per IP (in-memory sliding window). Over-limit
  requests silently drop — still 202, still no DB write.
- **Replay protection**: drop events whose client timestamp is > 1 hour
  old OR > 5 min in the future.
- **Strict schema**: anything outside the known fields is silently
  dropped. Anything malformed gets a 202 with no DB write.
- **No sensitive data** passes this boundary. The SDK payload is
  documented in ``src/gradata/_telemetry.py``.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from app.db import get_db

_log = logging.getLogger(__name__)

router = APIRouter()

# Same set as the SDK. Kept as a literal here so the backend enforces it
# independently of the client.
_ALLOWED_EVENTS = frozenset(
    {
        "brain_initialized",
        "first_correction_captured",
        "first_graduation",
        "first_hook_installed",
    }
)

# Events older than this are rejected (replay protection).
_MAX_AGE = timedelta(hours=1)

# ── In-memory rate limiter: 100 events / 60s / IP ────────────────────
# We roll our own instead of using slowapi so over-limit requests still
# return 202 (matches the "always 202" contract). Memory is bounded per
# IP by RATE_WINDOW; the IPs dict is trimmed opportunistically.
RATE_LIMIT = 100
RATE_WINDOW = 60.0
_rate_state: dict[str, deque[float]] = {}
_rate_lock = Lock()


def _allow(ip: str, now: float | None = None) -> bool:
    """Sliding-window rate check. Returns True if the request should be served."""
    if not ip:
        return True
    current = now if now is not None else time.monotonic()
    cutoff = current - RATE_WINDOW
    with _rate_lock:
        hits = _rate_state.get(ip)
        if hits is None:
            hits = deque()
            _rate_state[ip] = hits
        # Drop expired entries.
        while hits and hits[0] < cutoff:
            hits.popleft()
        if len(hits) >= RATE_LIMIT:
            return False
        hits.append(current)
        # Opportunistic GC so abandoned IPs don't leak memory.
        if len(_rate_state) > 10_000:
            for stale_ip in [k for k, v in _rate_state.items() if not v or v[-1] < cutoff]:
                _rate_state.pop(stale_ip, None)
        return True


def _reset_rate_limiter() -> None:
    """Test-only hook to clear in-memory state between tests."""
    with _rate_lock:
        _rate_state.clear()


class TelemetryEvent(BaseModel):
    """Wire format. Anything not in this shape is dropped silently."""

    event: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=64, max_length=64)  # sha256 hex
    ts: datetime
    sdk_version: str = Field(min_length=1, max_length=32)


_ACCEPTED: dict[str, Literal["accepted"]] = {"status": "accepted"}


def _is_hex64(s: str) -> bool:
    """Guard against user_id being anything other than lowercase hex sha256.

    ``int(s, 16)`` accepts uppercase too, so we explicitly require lowercase
    here to match the SDK's wire format and to keep the dedupe key
    case-canonical in storage.
    """
    if len(s) != 64:
        return False
    if s != s.lower():
        return False
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


async def _record(body: TelemetryEvent, source_ip: str | None) -> None:
    """Insert the event. Errors are logged but never re-raised."""
    try:
        db = get_db()
        await db.insert(
            "telemetry_events",
            {
                "event": body.event,
                "user_id": body.user_id,
                "sdk_version": body.sdk_version,
                "event_ts": body.ts.isoformat(),
                "source_ip": source_ip,
            },
        )
    except Exception as exc:
        # Swallow — public endpoint must not leak DB state.
        _log.warning("telemetry insert failed: %s", exc)


@router.post("/telemetry/event")
async def telemetry_event(request: Request) -> JSONResponse:
    """Accept an activation event. Always returns 202 (public surface)."""
    source_ip = request.client.host if request.client else None

    # Rate limit FIRST so a flood can't DOS the JSON parser.
    if source_ip and not _allow(source_ip):
        return JSONResponse(status_code=202, content=_ACCEPTED)

    # Parse defensively — malformed body = 202 no-op, never 400 or 500.
    try:
        raw = await request.json()
    except Exception:
        return JSONResponse(status_code=202, content=_ACCEPTED)

    if not isinstance(raw, dict):
        return JSONResponse(status_code=202, content=_ACCEPTED)

    try:
        body = TelemetryEvent(**raw)
    except ValidationError:
        return JSONResponse(status_code=202, content=_ACCEPTED)

    # Enforce allow-lists independently of the SDK.
    if body.event not in _ALLOWED_EVENTS:
        return JSONResponse(status_code=202, content=_ACCEPTED)
    if not _is_hex64(body.user_id):
        return JSONResponse(status_code=202, content=_ACCEPTED)

    # Replay protection — event must be recent.
    now = datetime.now(UTC)
    ts = body.ts if body.ts.tzinfo else body.ts.replace(tzinfo=UTC)
    if ts > now + timedelta(minutes=5):
        # Skewed-future event — drop silently.
        return JSONResponse(status_code=202, content=_ACCEPTED)
    if now - ts > _MAX_AGE:
        return JSONResponse(status_code=202, content=_ACCEPTED)

    await _record(body, source_ip)
    return JSONResponse(status_code=202, content=_ACCEPTED)
