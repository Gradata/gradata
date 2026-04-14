"""Brain registration, listing, detail, update, and soft-delete endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import (
    get_brain_for_request,
    get_current_brain,
    get_current_user_id,
    get_current_user_id_flexible,
)
from app.db import get_db
from app.models import BrainDetail, UpdateBrainRequest

_log = logging.getLogger(__name__)

router = APIRouter()


class ConnectRequest(BaseModel):
    brain_name: str = "default"
    domain: str = ""
    manifest: dict = {}


class ConnectResponse(BaseModel):
    brain_id: str
    status: str = "connected"


async def _brain_detail(db, brain: dict) -> BrainDetail:
    """Build a BrainDetail with lesson and correction counts."""
    brain_id = brain["id"]
    lessons = await db.select("lessons", columns="id", filters={"brain_id": brain_id})
    corrections = await db.select("corrections", columns="id", filters={"brain_id": brain_id})
    return BrainDetail(
        id=brain_id,
        user_id=brain["user_id"],
        name=brain.get("brain_name"),
        domain=brain.get("domain"),
        lesson_count=len(lessons),
        correction_count=len(corrections),
        last_sync=brain.get("last_sync_at"),
        created_at=brain.get("created_at"),
    )


@router.post("/brains/connect", response_model=ConnectResponse)
async def connect_brain(
    body: ConnectRequest,
    brain: dict = Depends(get_current_brain),
) -> ConnectResponse:
    """Register/reconnect a brain. Called by CloudClient.connect()."""
    _log.info("Brain connected: %s (name=%s)", brain["id"], body.brain_name)
    return ConnectResponse(brain_id=brain["id"])


@router.get("/brains", response_model=list[BrainDetail])
async def list_brains(user_id: str = Depends(get_current_user_id_flexible)) -> list[BrainDetail]:
    """List all brains for the authenticated user. Returns [] for new users."""
    db = get_db()
    rows = await db.select(
        "brains",
        columns="id,user_id,brain_name,domain,last_sync_at,created_at",
        filters={"user_id": user_id},
    )
    if not rows:
        return []

    brain_ids = [r["id"] for r in rows]
    # Two batched fetches instead of 2*N — count lessons + corrections per brain.
    lessons = await db.select("lessons", columns="brain_id", in_={"brain_id": brain_ids})
    corrections = await db.select("corrections", columns="brain_id", in_={"brain_id": brain_ids})
    lesson_count: dict[str, int] = {}
    correction_count: dict[str, int] = {}
    for l in lessons:
        bid = l.get("brain_id")
        if bid:
            lesson_count[bid] = lesson_count.get(bid, 0) + 1
    for c in corrections:
        bid = c.get("brain_id")
        if bid:
            correction_count[bid] = correction_count.get(bid, 0) + 1

    return [
        BrainDetail(
            id=row["id"],
            user_id=row["user_id"],
            name=row.get("brain_name"),
            domain=row.get("domain"),
            lesson_count=lesson_count.get(row["id"], 0),
            correction_count=correction_count.get(row["id"], 0),
            last_sync=row.get("last_sync_at"),
            created_at=row.get("created_at"),
        )
        for row in rows
    ]


class CreateBrainRequest(BaseModel):
    brain_name: str = "default"
    domain: str = ""


@router.post("/brains", response_model=BrainDetail, status_code=201)
async def create_brain(
    body: CreateBrainRequest,
    user_id: str = Depends(get_current_user_id),
) -> BrainDetail:
    """Explicitly create a new brain for the authenticated user.

    Used as a fallback when the signup auto-trigger didn't create one, and as
    the primary path for users who want multiple named brains. A workspace is
    auto-created if the user doesn't belong to one yet.
    """
    db = get_db()

    # Find or create a workspace for the user.
    memberships = await db.select(
        "workspace_members", columns="workspace_id", filters={"user_id": user_id}
    )
    if memberships:
        workspace_id = memberships[0]["workspace_id"]
    else:
        ws_rows = await db.insert(
            "workspaces",
            {"name": "My Workspace", "owner_id": user_id, "plan": "free"},
        )
        if not ws_rows:
            raise HTTPException(status_code=500, detail="Failed to create workspace")
        workspace_id = ws_rows[0]["id"]
        await db.insert(
            "workspace_members",
            {"workspace_id": workspace_id, "user_id": user_id, "role": "owner"},
        )

    # Generate a cloud-scope API key so the SDK can authenticate right away.
    # Delegate to the canonical helper so prefix + entropy stays consistent.
    from app.routes.api_keys import _generate_key
    api_key = _generate_key()

    brain_rows = await db.insert(
        "brains",
        {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "brain_name": body.brain_name,
            "domain": body.domain,
            "api_key": api_key,
        },
    )
    if not brain_rows:
        raise HTTPException(status_code=500, detail="Failed to create brain")
    b = brain_rows[0]
    _log.info("Brain created: %s (user=%s workspace=%s)", b["id"], user_id, workspace_id)
    return BrainDetail(
        id=b["id"],
        user_id=b["user_id"],
        name=b.get("brain_name"),
        domain=b.get("domain"),
        lesson_count=0,
        correction_count=0,
        last_sync=b.get("last_sync_at"),
        created_at=b.get("created_at"),
    )


@router.get("/brains/{brain_id}", response_model=BrainDetail)
async def get_brain(brain: dict = Depends(get_brain_for_request)) -> BrainDetail:
    """Return a single brain with lesson and correction counts."""
    return await _brain_detail(get_db(), brain)


@router.patch("/brains/{brain_id}", response_model=BrainDetail)
async def update_brain(
    body: UpdateBrainRequest,
    brain: dict = Depends(get_brain_for_request),
) -> BrainDetail:
    """Update a brain's name or domain."""
    db = get_db()

    updates: dict = {}
    if body.brain_name is not None:
        updates["brain_name"] = body.brain_name
    if body.domain is not None:
        updates["domain"] = body.domain

    if updates:
        await db.update("brains", data=updates, filters={"id": brain["id"]})
        brain = {**brain, **updates}

    return await _brain_detail(db, brain)


@router.delete("/brains/{brain_id}", status_code=204)
async def delete_brain(brain: dict = Depends(get_brain_for_request)) -> None:
    """Soft-delete a brain by setting deleted_at."""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.update("brains", data={"deleted_at": now}, filters={"id": brain["id"]})
    _log.info("Soft-deleted brain=%s", brain["id"])


class ClearDemoResponse(BaseModel):
    deleted: int
    by_table: dict[str, int]


@router.post("/brains/{brain_id}/clear-demo", response_model=ClearDemoResponse)
async def clear_demo(brain: dict = Depends(get_brain_for_request)) -> ClearDemoResponse:
    """Delete all demo rows (is_demo=true) scoped to this brain.

    Auth: caller must own the brain. Returns per-table delete counts and a total.
    """
    db = get_db()
    brain_id = brain["id"]

    by_table: dict[str, int] = {}
    total = 0

    for table in ("corrections", "lessons", "meta_rules", "events"):
        deleted = await _delete_demo_rows(db, table, brain_id)
        by_table[table] = deleted
        total += deleted

    brain_rows = await db.select(
        "brains", columns="id,metadata", filters={"id": brain_id}
    )
    if brain_rows and _is_demo(brain_rows[0].get("metadata")):
        await db.delete("brains", filters={"id": brain_id})
        by_table["brains"] = 1
        total += 1
    else:
        by_table["brains"] = 0

    _log.info("Cleared demo data for brain=%s (deleted=%d)", brain_id, total)
    return ClearDemoResponse(deleted=total, by_table=by_table)


async def _delete_demo_rows(db, table: str, brain_id: str) -> int:
    """Fetch rows for the brain, filter by is_demo marker, delete those ids."""
    rows = await db.select(table, columns="id,data", filters={"brain_id": brain_id})
    demo_rows = [r for r in rows if _is_demo(r.get("data"))]
    for row in demo_rows:
        await db.delete(table, filters={"id": row["id"]})
    return len(demo_rows)


def _is_demo(value) -> bool:
    return isinstance(value, dict) and bool(value.get("is_demo"))
