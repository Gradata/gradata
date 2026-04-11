"""Brain registration, listing, detail, update, and soft-delete endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.auth import get_brain_for_request, get_current_brain
from app.db import get_db
from app.models import BrainDetail, UpdateBrainRequest

_log = logging.getLogger(__name__)
_bearer = HTTPBearer()

router = APIRouter()


class ConnectRequest(BaseModel):
    brain_name: str = "default"
    domain: str = ""
    manifest: dict = {}


class ConnectResponse(BaseModel):
    brain_id: str
    status: str = "connected"


@router.post("/brains/connect", response_model=ConnectResponse)
async def connect_brain(
    body: ConnectRequest,
    brain: dict = Depends(get_current_brain),
) -> ConnectResponse:
    """Register/reconnect a brain. Called by CloudClient.connect()."""
    _log.info("Brain connected: %s (name=%s)", brain["id"], body.brain_name)
    return ConnectResponse(brain_id=brain["id"])


@router.get("/brains")
async def list_brains(brain: dict = Depends(get_current_brain)) -> list[dict]:
    """List all brains accessible to the authenticated user."""
    db = get_db()
    rows = await db.select(
        "brains",
        columns="id,user_id,brain_name,domain,manifest,last_sync_at,created_at",
        filters={"user_id": brain["user_id"]},
    )
    return rows


@router.get("/brains/{brain_id}", response_model=BrainDetail)
async def get_brain(
    brain_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> BrainDetail:
    """Return a single brain with lesson and correction counts."""
    brain = await get_brain_for_request(brain_id, credentials)
    db = get_db()

    lessons = await db.select("lessons", columns="id", filters={"brain_id": brain_id})
    corrections = await db.select("corrections", columns="id", filters={"brain_id": brain_id})

    return BrainDetail(
        id=brain["id"],
        user_id=brain["user_id"],
        brain_name=brain.get("brain_name"),
        domain=brain.get("domain"),
        last_sync_at=brain.get("last_sync_at"),
        created_at=brain.get("created_at"),
        deleted_at=brain.get("deleted_at"),
        lesson_count=len(lessons),
        correction_count=len(corrections),
    )


@router.patch("/brains/{brain_id}", response_model=BrainDetail)
async def update_brain(
    brain_id: str,
    body: UpdateBrainRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> BrainDetail:
    """Update a brain's name or domain."""
    brain = await get_brain_for_request(brain_id, credentials)
    db = get_db()

    updates: dict = {}
    if body.brain_name is not None:
        updates["brain_name"] = body.brain_name
    if body.domain is not None:
        updates["domain"] = body.domain

    if updates:
        await db.update("brains", data=updates, filters={"id": brain_id})
        brain = {**brain, **updates}

    lessons = await db.select("lessons", columns="id", filters={"brain_id": brain_id})
    corrections = await db.select("corrections", columns="id", filters={"brain_id": brain_id})

    return BrainDetail(
        id=brain["id"],
        user_id=brain["user_id"],
        brain_name=brain.get("brain_name"),
        domain=brain.get("domain"),
        last_sync_at=brain.get("last_sync_at"),
        created_at=brain.get("created_at"),
        deleted_at=brain.get("deleted_at"),
        lesson_count=len(lessons),
        correction_count=len(corrections),
    )


@router.delete("/brains/{brain_id}", status_code=204)
async def delete_brain(
    brain_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> None:
    """Soft-delete a brain by setting deleted_at."""
    await get_brain_for_request(brain_id, credentials)
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.update("brains", data={"deleted_at": now}, filters={"id": brain_id})
    _log.info("Soft-deleted brain=%s", brain_id)
