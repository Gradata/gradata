"""GET /brains/{brain_id}/lessons — lesson browsing with filtering and pagination."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from app.auth import get_brain_for_request
from app.db import get_db

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/brains/{brain_id}/lessons")
async def list_lessons(
    brain: dict = Depends(get_brain_for_request),
    state: str | None = Query(None, description="Filter by lesson state (RULE, PATTERN, etc.)"),
    category: str | None = Query(None, description="Filter by category"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: str | None = Query(None, description="Sort field: confidence"),
) -> list[dict]:
    """List lessons for a brain with optional filtering and pagination."""
    db = get_db()

    filters: dict = {"brain_id": brain["id"]}
    if state:
        filters["state"] = state
    if category:
        filters["category"] = category

    rows = await db.select(
        "lessons",
        columns="id,brain_id,category,description,state,confidence,fire_count,recurrence_days,created_at",
        filters=filters,
    )

    # PostgREST eq can't express min_confidence; filter in-process.
    if min_confidence is not None:
        rows = [r for r in rows if (r.get("confidence") or 0.0) >= min_confidence]

    if sort == "confidence":
        rows.sort(key=lambda r: r.get("confidence") or 0.0, reverse=True)

    return rows[offset : offset + limit]
