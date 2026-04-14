"""Team / workspace member management endpoints (JWT only)."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
        brains = await db.select(
            "brains",
            columns="id,last_sync_at",
            filters={"workspace_id": workspace_id, "user_id": member_user_id},
        )
        sync_times = [b["last_sync_at"] for b in brains if b.get("last_sync_at")]
        last_sync_at = max(sync_times) if sync_times else None

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
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=7)).isoformat()

    invite_data = {
        "workspace_id": workspace_id,
        "email": str(body.email),
        "role": body.role.value,
        "invited_by": user_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": now.isoformat(),
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

    new_role = body.role.value
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


# ---------------------------------------------------------------------------
# Team aggregate stats — powers /team overview + leaderboard
# ---------------------------------------------------------------------------


class TeamMemberStat(BaseModel):
    user_id: str
    display_name: str | None = None
    email: str | None = None
    role: str
    last_sync_at: str | None = None
    corrections_week: int = 0
    correction_delta_pct: float = 0.0
    rules_graduated_30d: int = 0
    active: bool = False


class TeamStatsResponse(BaseModel):
    corrections_week: int = 0
    rules_graduated_30d: int = 0
    avg_delta_pct: float = 0.0
    active_brains: int = 0
    total_members: int = 0
    members: list[TeamMemberStat] = []


def _parse_iso(ts: object) -> datetime | None:
    if not ts:
        return None
    try:
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@router.get("/workspaces/{workspace_id}/team-stats", response_model=TeamStatsResponse)
async def get_team_stats(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> TeamStatsResponse:
    """Aggregate team activity for the leaderboard. Caller must belong to the workspace."""
    await _require_member(workspace_id, user_id)
    db = get_db()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    month_ago = now - timedelta(days=30)
    active_cutoff = now - timedelta(days=14)

    members = await db.select("workspace_members", filters={"workspace_id": workspace_id})
    brains = await db.select("brains", filters={"workspace_id": workspace_id})

    # Group brains by member.
    brains_by_user: dict[str, list[dict]] = {}
    brain_to_user: dict[str, str] = {}
    for b in brains:
        uid = b.get("user_id")
        if uid:
            brains_by_user.setdefault(uid, []).append(b)
            brain_to_user[b["id"]] = uid

    # Single fetch for all corrections + lessons across the workspace.
    workspace_brain_ids = set(brain_to_user.keys())
    all_corrections = await db.select("corrections", columns="brain_id,created_at")
    all_lessons = await db.select("lessons", columns="brain_id,state,created_at")

    corr_this: dict[str, int] = {}
    corr_prior: dict[str, int] = {}
    rules_30d: dict[str, int] = {}
    for c in all_corrections:
        bid = c.get("brain_id")
        if bid not in workspace_brain_ids:
            continue
        uid = brain_to_user[bid]
        ts = _parse_iso(c.get("created_at"))
        if ts is None:
            continue
        if ts >= week_ago:
            corr_this[uid] = corr_this.get(uid, 0) + 1
        elif two_weeks_ago <= ts < week_ago:
            corr_prior[uid] = corr_prior.get(uid, 0) + 1

    for l in all_lessons:
        bid = l.get("brain_id")
        if bid not in workspace_brain_ids:
            continue
        uid = brain_to_user[bid]
        if (l.get("state") or "") != "RULE":
            continue
        ts = _parse_iso(l.get("created_at"))
        if ts and ts >= month_ago:
            rules_30d[uid] = rules_30d.get(uid, 0) + 1

    rows: list[TeamMemberStat] = []
    active_count = 0
    total_corr_week = 0
    total_rules_30d = 0
    delta_sum = 0.0
    delta_n = 0

    for m in members:
        uid = m.get("user_id")
        if not uid:
            continue
        member_brains = brains_by_user.get(uid, [])
        last_sync: datetime | None = None
        for b in member_brains:
            ts = _parse_iso(b.get("last_sync_at"))
            if ts and (last_sync is None or ts > last_sync):
                last_sync = ts
        is_active = last_sync is not None and last_sync >= active_cutoff
        if is_active:
            active_count += 1

        this_week = corr_this.get(uid, 0)
        prior_week = corr_prior.get(uid, 0)
        delta = ((this_week - prior_week) / prior_week * 100.0) if prior_week else 0.0
        if prior_week or this_week:
            delta_sum += delta
            delta_n += 1

        total_corr_week += this_week
        total_rules_30d += rules_30d.get(uid, 0)

        rows.append(
            TeamMemberStat(
                user_id=uid,
                display_name=m.get("display_name"),
                email=m.get("email"),
                role=m.get("role", "member"),
                last_sync_at=last_sync.isoformat() if last_sync else None,
                corrections_week=this_week,
                correction_delta_pct=round(delta, 1),
                rules_graduated_30d=rules_30d.get(uid, 0),
                active=is_active,
            )
        )

    return TeamStatsResponse(
        corrections_week=total_corr_week,
        rules_graduated_30d=total_rules_30d,
        avg_delta_pct=round(delta_sum / delta_n, 1) if delta_n else 0.0,
        active_brains=active_count,
        total_members=len(rows),
        members=rows,
    )
