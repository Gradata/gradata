"""Brain registration and listing endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_brain
from app.db import get_db

_log = logging.getLogger(__name__)

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
    return await db.select("brains", filters={"user_id": brain["user_id"]})
