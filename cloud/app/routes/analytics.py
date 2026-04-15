"""GET /brains/{brain_id}/analytics — aggregated brain metrics."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter

from fastapi import APIRouter, Depends

from app.auth import get_brain_for_request
from app.db import get_db
from app.models import BrainAnalytics

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/brains/{brain_id}/analytics", response_model=BrainAnalytics)
async def get_analytics(brain: dict = Depends(get_brain_for_request)) -> BrainAnalytics:
    """Return aggregated metrics for a brain."""
    db = get_db()
    bid = brain["id"]

    lessons, corrections, events = await asyncio.gather(
        db.select("lessons", columns="state,confidence", filters={"brain_id": bid}),
        db.select("corrections", columns="severity,category", filters={"brain_id": bid}),
        db.select("events", columns="id", filters={"brain_id": bid}),
    )

    lessons_by_state = dict(Counter(r["state"] for r in lessons if r.get("state")))
    corrections_by_severity = dict(
        Counter(r["severity"] for r in corrections if r.get("severity"))
    )
    corrections_by_category = dict(
        Counter(r["category"] for r in corrections if r.get("category"))
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
