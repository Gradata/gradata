"""Team / workspace member management endpoints (JWT only)."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user_id
from app.db import get_db
from app.models import (
    InviteRequest,
    InviteResponse,
    MemberResponse,
    UpdateRoleRequest,
)

_log = logging.getLogger(__name__)

router = APIRouter()

INVITE_BASE_URL = "https://app.gradata.ai/invites"


async def _get_member(workspace_id: str, user_id: str) -> dict | None:
    """Return the workspace_members row for (workspace_id, user_id) or None."""
    db = get_db()
    rows = await db.select(
        "workspace_members",
        filters={"workspace_id": workspace_id, "user_id": user_id},
    )
    return rows[0] if rows else None


async def _require_member(workspace_id: str, user_id: str) -> dict:
    """Raise 403 unless the caller belongs to the workspace."""
    membership = await _get_member(workspace_id, user_id)
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    return membership


async def _require_admin(workspace_id: str, user_id: str) -> dict:
    """Raise 403 unless the caller is owner or admin of the workspace."""
    membership = await _require_member(workspace_id, user_id)
    if membership.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin or owner role required")
    return membership


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[MemberResponse],
)
async def list_members(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list[MemberResponse]:
    """List workspace members. Caller must belong to the workspace."""
    await _require_member(workspace_id, user_id)
    db = get_db()

    members = await db.select(
        "workspace_members",
        filters={"workspace_id": workspace_id},
    )

    results: list[MemberResponse] = []
    for m in members:
        member_user_id = m["user_id"]
        # Pull the user's most recent brain in this workspace for last_sync_at.
        brains = await db.select(
            "brains",
            columns="id,last_sync_at",
            filters={"workspace_id": workspace_id, "user_id": member_user_id},
        )
        last_sync_at: str | None = None
        for b in brains:
            ts = b.get("last_sync_at")
            if ts and (last_sync_at is None or ts > last_sync_at):
                last_sync_at = ts

        results.append(
            MemberResponse(
                user_id=member_user_id,
                email=m.get("email"),
                display_name=m.get("display_name"),
                role=m.get("role", "member"),
                joined_at=m.get("joined_at"),
                last_sync_at=last_sync_at,
            )
        )
    return results


@router.post(
    "/workspaces/{workspace_id}/invites",
    response_model=InviteResponse,
    status_code=201,
)
async def create_invite(
    workspace_id: str,
    body: InviteRequest,
    user_id: str = Depends(get_current_user_id),
) -> InviteResponse:
    """Invite a teammate by email. Caller must be owner or admin."""
    await _require_admin(workspace_id, user_id)
    db = get_db()

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    created_at = datetime.now(timezone.utc).isoformat()

    invite_data = {
        "workspace_id": workspace_id,
        "email": str(body.email),
        "role": body.role.value if hasattr(body.role, "value") else body.role,
        "invited_by": user_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": created_at,
    }

    rows = await db.insert("workspace_invites", invite_data)
    inserted = rows[0] if rows else invite_data

    invite_id = inserted.get("id") or "pending"
    accept_url = f"{INVITE_BASE_URL}/{token}"

    _log.info(
        "Invite created: workspace=%s email=%s role=%s by=%s",
        workspace_id,
        body.email,
        invite_data["role"],
        user_id,
    )

    return InviteResponse(
        id=str(invite_id),
        email=str(body.email),
        role=invite_data["role"],
        token=token,
        accept_url=accept_url,
        expires_at=inserted.get("expires_at", expires_at),
    )


@router.delete(
    "/workspaces/{workspace_id}/members/{member_user_id}",
    status_code=204,
)
async def remove_member(
    workspace_id: str,
    member_user_id: str,
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Remove a member from the workspace. Owner cannot be removed here."""
    await _require_admin(workspace_id, user_id)
    db = get_db()

    target = await _get_member(workspace_id, member_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    if target.get("role") == "owner":
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the workspace owner; transfer ownership first",
        )

    await db.delete(
        "workspace_members",
        filters={"workspace_id": workspace_id, "user_id": member_user_id},
    )
    _log.info(
        "Removed member: workspace=%s user=%s by=%s",
        workspace_id,
        member_user_id,
        user_id,
    )


@router.patch(
    "/workspaces/{workspace_id}/members/{member_user_id}",
    response_model=MemberResponse,
)
async def update_member_role(
    workspace_id: str,
    member_user_id: str,
    body: UpdateRoleRequest,
    user_id: str = Depends(get_current_user_id),
) -> MemberResponse:
    """Change a member's role. Owner cannot be assigned through this endpoint."""
    await _require_admin(workspace_id, user_id)
    db = get_db()

    new_role = body.role.value if hasattr(body.role, "value") else body.role
    if new_role == "owner":
        raise HTTPException(
            status_code=400,
            detail="Owner role cannot be assigned here; use ownership transfer flow",
        )

    target = await _get_member(workspace_id, member_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    if target.get("role") == "owner":
        raise HTTPException(
            status_code=400,
            detail="Cannot change the owner's role; transfer ownership first",
        )

    await db.update(
        "workspace_members",
        data={"role": new_role},
        filters={"workspace_id": workspace_id, "user_id": member_user_id},
    )

    _log.info(
        "Updated role: workspace=%s user=%s role=%s by=%s",
        workspace_id,
        member_user_id,
        new_role,
        user_id,
    )

    return MemberResponse(
        user_id=member_user_id,
        email=target.get("email"),
        display_name=target.get("display_name"),
        role=new_role,
        joined_at=target.get("joined_at"),
        last_sync_at=None,
    )
