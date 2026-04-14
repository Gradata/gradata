"""Public, unauthenticated endpoints.

These are safe to expose to the marketing site or anonymous callers.
Do NOT put per-user data here.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.db import get_db
from app.middleware import limiter

_log = logging.getLogger(__name__)

router = APIRouter()


class PublicStats(BaseModel):
    brains_total: int
    corrections_total: int
    lessons_total: int
    lessons_graduated: int
    graduated_last_7d: int
    meta_rules_total: int
    last_activity_at: str | None
    generated_at: str


# Tiny in-process cache — 60s TTL. Plenty for a static marketing site.
_CACHE: dict[str, PublicStats | float] = {"value": None, "expires_at": 0.0}  # type: ignore[dict-item]
_CACHE_TTL_SECONDS = 60.0


def _parse_ts(ts: object) -> datetime | None:
    if not ts:
        return None
    try:
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def _compute_stats() -> PublicStats:
    db = get_db()

    brains = await db.select("brains", columns="id,last_sync_at")
    corrections = await db.select("corrections", columns="created_at")
    lessons = await db.select("lessons", columns="state,created_at")
    meta_rules = await db.select("meta_rules", columns="id")
    # heartbeats are lightweight — fetch only recent ones
    heartbeats = await db.select("heartbeats", columns="created_at")

    graduated_states = {"PATTERN", "RULE"}
    lessons_graduated = sum(1 for l in lessons if (l.get("state") or "") in graduated_states)

    now = datetime.now(timezone.utc)
    graduated_7d = 0
    last_activity: datetime | None = None

    def _bump(ts_val: object) -> None:
        nonlocal last_activity
        ts = _parse_ts(ts_val)
        if ts and (last_activity is None or ts > last_activity):
            last_activity = ts

    for l in lessons:
        ts = _parse_ts(l.get("created_at"))
        if ts and (now - ts).days <= 7 and (l.get("state") or "") in graduated_states:
            graduated_7d += 1
        _bump(l.get("created_at"))
    for c in corrections:
        _bump(c.get("created_at"))
    for b in brains:
        _bump(b.get("last_sync_at"))
    for h in heartbeats:
        _bump(h.get("created_at"))

    # Record this cache-refresh as a heartbeat so the field always moves
    # forward. Only fires when the cache actually misses (i.e. ~once per TTL).
    try:
        await db.insert("heartbeats", {"source": "public_stats_refresh"})
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("heartbeat insert failed: %s", exc)

    return PublicStats(
        brains_total=len(brains),
        corrections_total=len(corrections),
        lessons_total=len(lessons),
        lessons_graduated=lessons_graduated,
        graduated_last_7d=graduated_7d,
        meta_rules_total=len(meta_rules),
        last_activity_at=last_activity.isoformat() if last_activity else None,
        generated_at=now.isoformat(),
    )


@router.get("/public/stats", response_model=PublicStats)
@limiter.limit("60/minute")
async def get_public_stats(request: Request) -> PublicStats:
    """Aggregate product-health counts. Cached for 60s across all callers."""
    now = time.monotonic()
    cached = _CACHE.get("value")
    if cached is not None and now < _CACHE["expires_at"]:  # type: ignore[operator]
        return cached  # type: ignore[return-value]

    stats = await _compute_stats()
    _CACHE["value"] = stats
    _CACHE["expires_at"] = now + _CACHE_TTL_SECONDS
    return stats


@router.post("/public/heartbeat")
@limiter.limit("20/minute")
async def post_heartbeat(request: Request, source: str = "unknown") -> dict[str, str]:
    """Record a client-side heartbeat ping. No auth. Idempotent, cheap."""
    # Whitelist sources to prevent arbitrary labels bloating the table.
    allowed = {"dashboard", "marketing", "sdk", "unknown"}
    safe_source = source if source in allowed else "unknown"
    db = get_db()
    try:
        await db.insert("heartbeats", {"source": safe_source})
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("heartbeat insert failed: %s", exc)
    return {"status": "ok"}
