"""POST /api/v1/sync -- receives brain events from SDK."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.auth import get_current_brain
from app.db import get_db
from app.middleware import limiter
from app.models import SyncRequest, SyncResponse

_log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
@limiter.limit("120/minute")
async def sync_brain(
    request: Request,
    body: SyncRequest,
    brain: dict = Depends(get_current_brain),
) -> SyncResponse:
    """Receive corrections, lessons, events, and meta-rules from SDK.

    Called by CloudClient.sync() on end_session() when GRADATA_API_KEY is set.
    The brain is identified by the API key in the Authorization header.
    """
    brain_id = brain["id"]
    db = get_db()

    corrections_count = 0
    lessons_count = 0
    events_count = 0
    meta_rules_count = 0

    # Insert corrections
    if body.corrections:
        rows = [
            {
                "brain_id": brain_id,
                "session": c.session,
                "category": c.category,
                "severity": c.severity.value,
                "description": c.description,
                "draft_preview": c.draft_preview[:500],
                "final_preview": c.final_preview[:500],
                **({"created_at": c.created_at} if c.created_at else {}),
            }
            for c in body.corrections
        ]
        await db.insert("corrections", rows)
        corrections_count = len(rows)

    # Upsert lessons (idempotent by description)
    if body.lessons:
        rows = [
            {
                "brain_id": brain_id,
                "category": l.category,
                "description": l.description,
                "state": l.state.value,
                "confidence": float(l.confidence),
                "fire_count": l.fire_count,
                "recurrence_days": l.recurrence_days,
            }
            for l in body.lessons
        ]
        await db.upsert("lessons", rows)
        lessons_count = len(rows)

    # Insert events
    if body.events:
        rows = [
            {
                "brain_id": brain_id,
                "type": e.type,
                "source": e.source,
                "data": e.data,
                "tags": e.tags,
                "session": e.session,
                **({"created_at": e.created_at} if e.created_at else {}),
            }
            for e in body.events
        ]
        await db.insert("events", rows)
        events_count = len(rows)

        # RULE_PATCHED events are the self-healing audit trail. Populate
        # `rule_patches` from them so the self-healing dashboard has data
        # (otherwise the table stays empty and the UI never lights up).
        patched = [e for e in body.events if e.type == "RULE_PATCHED"]
        if patched:
            categories = sorted({
                (e.data.get("category") or "").upper()
                for e in patched
                if isinstance(e.data, dict) and e.data.get("category")
            })
            if categories:
                # One query per category (our thin PostgREST wrapper only
                # supports eq filters). Small N — one per patched category.
                by_cat: dict[str, list[dict]] = {}
                for cat in categories:
                    rows = await db.select(
                        "lessons",
                        columns="id,category,description",
                        filters={"brain_id": brain_id, "category": cat},
                    )
                    if rows:
                        by_cat[cat] = rows

                def _resolve_lesson_id(cat: str, old_desc: str, new_desc: str) -> str | None:
                    candidates = by_cat.get(cat, [])
                    if not candidates:
                        return None
                    # Prefer a lesson whose current description matches either
                    # side of the patch (ordering-agnostic). Fall back to first.
                    for lesson in candidates:
                        if lesson.get("description") in (new_desc, old_desc):
                            return lesson["id"]
                    return candidates[0]["id"]

                patch_rows: list[dict] = []
                for ev in patched:
                    data = ev.data if isinstance(ev.data, dict) else {}
                    cat = (data.get("category") or "").upper()
                    old_desc = data.get("old_description") or ""
                    new_desc = data.get("new_description") or ""
                    if not cat or not old_desc or not new_desc:
                        continue
                    lesson_id = _resolve_lesson_id(cat, old_desc, new_desc)
                    if lesson_id is None:
                        _log.warning(
                            "rule-patches: no lesson for brain=%s category=%s — skipping",
                            brain_id, cat,
                        )
                        continue
                    row = {
                        "lesson_id": lesson_id,
                        "old_description": old_desc,
                        "new_description": new_desc,
                        "reason": data.get("reason") or "self_healing",
                    }
                    if ev.created_at:
                        row["created_at"] = ev.created_at
                    patch_rows.append(row)
                if patch_rows:
                    await db.insert("rule_patches", patch_rows)

    # Insert meta-rules
    if body.meta_rules:
        rows = [
            {
                "brain_id": brain_id,
                "title": m.title,
                "description": m.description,
                "source_lesson_ids": [],  # Resolved server-side later
            }
            for m in body.meta_rules
        ]
        await db.insert("meta_rules", rows)
        meta_rules_count = len(rows)

    # Update last_sync_at timestamp
    await db.update(
        "brains",
        data={"last_sync_at": datetime.now(timezone.utc).isoformat()},
        filters={"id": brain_id},
    )

    _log.info(
        "Synced brain=%s: %d corrections, %d lessons, %d events, %d meta-rules",
        brain_id, corrections_count, lessons_count, events_count, meta_rules_count,
    )

    return SyncResponse(
        status="ok",
        corrections_synced=corrections_count,
        lessons_synced=lessons_count,
        events_synced=events_count,
        meta_rules_synced=meta_rules_count,
    )
