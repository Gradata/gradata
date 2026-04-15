"""GET /brains/{brain_id}/activity — chronological learning-event feed."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import get_brain_for_request
from app.db import get_db

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()

router = APIRouter()


# Event types that become visible learning activity. Everything else is
# noise for UI purposes.
_VISIBLE_EVENT_TYPES = {
    "graduation",          # lesson promoted to RULE state
    "self-healing",        # rule description auto-evolved
    "recurrence",          # error recurred despite a graduated rule
    "meta-rule-emerged",   # new meta-rule crystallized
    "convergence",         # N users corrected same direction
    "alert",               # correction spike or regression
}


@router.get("/brains/{brain_id}/activity")
async def list_activity(
    brain_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Return visible learning events for a brain, newest first.

    Filters out raw correction events and internal telemetry — only shows
    events the user should care about (graduations, self-healing, etc.).
    """
    brain = await get_brain_for_request(brain_id, credentials)
    db = get_db()

    rows = await db.select(
        "events",
        columns="id,brain_id,type,source,data,tags,session,created_at",
        filters={"brain_id": brain["id"]},
        in_={"type": list(_VISIBLE_EVENT_TYPES)},
    )

    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[offset : offset + limit]
