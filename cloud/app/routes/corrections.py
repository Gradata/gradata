"""GET /brains/{brain_id}/corrections — correction history with filtering."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import get_brain_for_request
from app.db import get_db

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()

router = APIRouter()


@router.get("/brains/{brain_id}/corrections")
async def list_corrections(
    brain_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    severity: str | None = Query(None, description="Filter by severity"),
    category: str | None = Query(None, description="Filter by category"),
    session: int | None = Query(None, description="Filter by session number"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List corrections for a brain with optional filtering and pagination."""
    brain = await get_brain_for_request(brain_id, credentials)
    db = get_db()

    filters: dict = {"brain_id": brain["id"]}
    if severity:
        filters["severity"] = severity
    if category:
        filters["category"] = category
    if session is not None:
        filters["session"] = session

    rows = await db.select(
        "corrections",
        columns="id,brain_id,session,category,severity,description,draft_preview,final_preview,created_at",
        filters=filters,
    )

    return rows[offset : offset + limit]
