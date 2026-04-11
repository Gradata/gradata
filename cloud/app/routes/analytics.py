"""GET /brains/{brain_id}/analytics — aggregated brain metrics."""

from __future__ import annotations

import logging
from collections import Counter

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import get_brain_for_request
from app.db import get_db
from app.models import BrainAnalytics

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()

router = APIRouter()


@router.get("/brains/{brain_id}/analytics", response_model=BrainAnalytics)
async def get_analytics(
    brain_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> BrainAnalytics:
    """Return aggregated metrics for a brain."""
    brain = await get_brain_for_request(brain_id, credentials)
    db = get_db()
    bid = brain["id"]

    lessons, corrections, events = await _fetch_all(db, bid)

    lessons_by_state: dict[str, int] = dict(
        Counter(r.get("state") for r in lessons if r.get("state"))
    )
    corrections_by_severity: dict[str, int] = dict(
        Counter(r.get("severity") for r in corrections if r.get("severity"))
    )
    corrections_by_category: dict[str, int] = dict(
        Counter(r.get("category") for r in corrections if r.get("category"))
    )

    confidences = [r["confidence"] for r in lessons if r.get("confidence") is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    total_lessons = len(lessons)
    rule_count = lessons_by_state.get("RULE", 0)
    graduation_rate = rule_count / total_lessons if total_lessons else 0.0

    return BrainAnalytics(
        total_corrections=len(corrections),
        total_lessons=total_lessons,
        total_events=len(events),
        lessons_by_state=lessons_by_state,
        corrections_by_severity=corrections_by_severity,
        corrections_by_category=corrections_by_category,
        avg_confidence=round(avg_confidence, 4),
        graduation_rate=round(graduation_rate, 4),
        last_sync_at=brain.get("last_sync_at"),
        brain_created_at=brain.get("created_at"),
    )


async def _fetch_all(db, brain_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Fetch lessons, corrections, and events concurrently via sequential awaits."""
    lessons = await db.select("lessons", columns="state,confidence", filters={"brain_id": brain_id})
    corrections = await db.select(
        "corrections", columns="severity,category", filters={"brain_id": brain_id}
    )
    events = await db.select("events", columns="id", filters={"brain_id": brain_id})
    return lessons, corrections, events
