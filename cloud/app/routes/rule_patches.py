"""GET /brains/{brain_id}/rule-patches — self-healing audit trail."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_brain_for_request
from app.db import get_db

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/brains/{brain_id}/rule-patches")
async def list_rule_patches(
    brain: dict = Depends(get_brain_for_request),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Return rule patches for a brain (self-healing audit trail).

    Patches are keyed to lessons, so we fetch all lessons for the brain
    first, then find patches against those lesson IDs.
    """
    db = get_db()

    lessons = await db.select(
        "lessons", columns="id", filters={"brain_id": brain["id"]},
    )
    lesson_ids = [row["id"] for row in lessons]
    if not lesson_ids:
        return []

    # Push the WHERE lesson_id IN (...) filter into PostgREST so we don't
    # haul down the entire rule_patches table on each request.
    patches = await db.select(
        "rule_patches",
        columns="id,lesson_id,old_description,new_description,reason,created_at",
        in_={"lesson_id": lesson_ids},
    )
    patches.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return patches[offset : offset + limit]


@router.post("/brains/{brain_id}/rule-patches/{patch_id}/rollback", status_code=204)
async def rollback_patch(
    patch_id: str,
    brain: dict = Depends(get_brain_for_request),
) -> None:
    """Revert a patch by restoring the lesson's old_description.

    The patch itself is kept for audit — we mark it rolled-back by creating
    an inverse patch so the history is append-only.
    """
    db = get_db()

    rows = await db.select(
        "rule_patches",
        columns="id,lesson_id,old_description,new_description,reason",
        filters={"id": patch_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="patch not found")
    patch = rows[0]

    lesson_rows = await db.select(
        "lessons", columns="id,brain_id", filters={"id": patch["lesson_id"]},
    )
    if not lesson_rows or lesson_rows[0].get("brain_id") != brain["id"]:
        raise HTTPException(status_code=404, detail="patch not found")

    await db.insert(
        "rule_patches",
        {
            "lesson_id": patch["lesson_id"],
            "old_description": patch["new_description"],
            "new_description": patch["old_description"],
            "reason": f"rollback of patch {patch_id}",
        },
    )
    await db.update(
        "lessons",
        {"description": patch["old_description"]},
        filters={"id": patch["lesson_id"]},
    )
