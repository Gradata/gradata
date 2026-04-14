"""GET/PATCH /users/me — user profile endpoints (JWT only)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.auth import get_current_user_id
from app.db import get_db
from app.models import NotificationPrefs, UpdateProfileRequest, UserProfile

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users/me", response_model=UserProfile)
async def get_profile(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> UserProfile:
    """Return the authenticated user's profile and workspace memberships."""
    db = get_db()

    # Fetch workspace memberships
    memberships = await db.select(
        "workspace_members",
        columns="workspace_id,role",
        filters={"user_id": user_id},
    )

    workspace_ids = [m["workspace_id"] for m in memberships]
    workspaces: list[dict] = []
    for ws_id in workspace_ids:
        rows = await db.select("workspaces", filters={"id": ws_id})
        if rows:
            ws = rows[0]
            role = next((m["role"] for m in memberships if m["workspace_id"] == ws_id), None)
            workspaces.append({**ws, "role": role})

    # Fetch user record from brains table (user_id is our identity anchor)
    brain_rows = await db.select(
        "brains",
        columns="user_id,created_at",
        filters={"user_id": user_id},
    )
    created_at = brain_rows[0].get("created_at") if brain_rows else None

    return UserProfile(
        user_id=user_id,
        workspaces=workspaces,
        created_at=created_at,
    )


@router.patch("/users/me", response_model=UserProfile)
async def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> UserProfile:
    """Update the authenticated user's display name."""
    db = get_db()

    await db.update(
        "workspace_members",
        data={"display_name": body.display_name},
        filters={"user_id": user_id},
    )

    _log.info("Updated display_name for user=%s", user_id)

    memberships = await db.select(
        "workspace_members",
        columns="workspace_id,role",
        filters={"user_id": user_id},
    )
    workspaces: list[dict] = []
    for m in memberships:
        rows = await db.select("workspaces", filters={"id": m["workspace_id"]})
        if rows:
            workspaces.append({**rows[0], "role": m["role"]})

    return UserProfile(
        user_id=user_id,
        display_name=body.display_name,
        workspaces=workspaces,
    )


@router.get("/users/me/notifications", response_model=NotificationPrefs)
async def get_notifications(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> NotificationPrefs:
    """Return the authenticated user's notification preferences.

    Stored as a single JSON column on workspace_members for now (one workspace
    per user during launch). Falls back to defaults if no row.
    """
    db = get_db()
    rows = await db.select(
        "workspace_members",
        columns="notification_prefs",
        filters={"user_id": user_id},
    )
    if not rows or not rows[0].get("notification_prefs"):
        return NotificationPrefs()
    return NotificationPrefs(**rows[0]["notification_prefs"])


@router.put("/users/me/notifications", response_model=NotificationPrefs)
async def update_notifications(
    body: NotificationPrefs,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> NotificationPrefs:
    """Replace the authenticated user's notification preferences."""
    db = get_db()
    await db.update(
        "workspace_members",
        data={"notification_prefs": body.model_dump()},
        filters={"user_id": user_id},
    )
    _log.info("Updated notification_prefs for user=%s cadence=%s", user_id, body.digest_cadence)
    return body
