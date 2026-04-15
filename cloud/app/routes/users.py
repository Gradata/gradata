"""GET/PATCH /users/me — user profile endpoints (JWT only)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import (
    _bearer,
    _resolve_user_email,
    get_current_user_id,
    verify_jwt_claims,
)
from app.db import get_db
from app.models import NotificationPrefs, UpdateProfileRequest, UserProfile

_log = logging.getLogger(__name__)

router = APIRouter()


def _derive_plan(workspaces: list[dict]) -> str | None:
    """Pick the best plan across the user's workspaces (highest tier wins)."""
    priority = {"free": 0, "cloud": 1, "team": 2, "enterprise": 3}
    best: str | None = None
    best_rank = -1
    for ws in workspaces:
        plan = (ws.get("plan") or "").lower()
        rank = priority.get(plan, -1)
        if rank > best_rank:
            best_rank = rank
            best = plan or None
    return best


@router.get("/users/me", response_model=UserProfile)
async def get_profile(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> UserProfile:
    """Return the authenticated user's profile and workspace memberships."""
    claims = await verify_jwt_claims(credentials.credentials)
    user_id = claims["sub"]
    email = await _resolve_user_email(user_id, claims)

    db = get_db()

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

    brain_rows = await db.select(
        "brains",
        columns="user_id,created_at",
        filters={"user_id": user_id},
    )
    created_at = brain_rows[0].get("created_at") if brain_rows else None

    return UserProfile(
        user_id=user_id,
        email=email,
        plan=_derive_plan(workspaces),
        workspaces=workspaces,
        created_at=created_at,
    )


@router.patch("/users/me", response_model=UserProfile)
async def update_profile(
    body: UpdateProfileRequest,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> UserProfile:
    """Update the authenticated user's display name."""
    claims = await verify_jwt_claims(credentials.credentials)
    user_id = claims["sub"]
    email = await _resolve_user_email(user_id, claims)

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
        email=email,
        plan=_derive_plan(workspaces),
        display_name=body.display_name,
        workspaces=workspaces,
    )


async def _primary_workspace_id(user_id: str) -> str | None:
    """Return the user's primary (first-joined) workspace membership id."""
    db = get_db()
    rows = await db.select(
        "workspace_members",
        columns="workspace_id",
        filters={"user_id": user_id},
    )
    return rows[0]["workspace_id"] if rows else None


@router.get("/users/me/notifications", response_model=NotificationPrefs)
async def get_notifications(
    user_id: str = Depends(get_current_user_id),
) -> NotificationPrefs:
    db = get_db()
    ws_id = await _primary_workspace_id(user_id)
    if not ws_id:
        return NotificationPrefs()
    rows = await db.select(
        "workspace_members",
        columns="notification_prefs",
        filters={"user_id": user_id, "workspace_id": ws_id},
    )
    if not rows or not rows[0].get("notification_prefs"):
        return NotificationPrefs()
    return NotificationPrefs(**rows[0]["notification_prefs"])


@router.put("/users/me/notifications", response_model=NotificationPrefs)
async def update_notifications(
    prefs: NotificationPrefs,
    user_id: str = Depends(get_current_user_id),
) -> NotificationPrefs:
    db = get_db()
    ws_id = await _primary_workspace_id(user_id)
    # Scope the update so a user in multiple workspaces doesn't clobber
    # prefs across all of them. Primary workspace wins until we add per-
    # workspace notification settings in the UI.
    filters: dict[str, str] = {"user_id": user_id}
    if ws_id:
        filters["workspace_id"] = ws_id
    await db.update(
        "workspace_members",
        data={"notification_prefs": prefs.model_dump()},
        filters=filters,
    )
    return prefs
