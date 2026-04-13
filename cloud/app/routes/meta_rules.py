"""GET /brains/{brain_id}/meta-rules — universal principles from 3+ lessons."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import get_brain_for_request
from app.db import get_db

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()

router = APIRouter()


@router.get("/brains/{brain_id}/meta-rules")
async def list_meta_rules(
    brain_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List meta-rules for a brain.

    Returns the meta_rules table joined with source lesson counts. Does NOT
    return raw correction text — only synthesized principles (per privacy
    posture: raw corrections never leave the device).
    """
    brain = await get_brain_for_request(brain_id, credentials)
    db = get_db()

    rows = await db.select(
        "meta_rules",
        columns="id,brain_id,title,description,source_lesson_ids,created_at",
        filters={"brain_id": brain["id"]},
    )

    # Sort newest first
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[offset : offset + limit]
