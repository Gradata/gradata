"""GDPR endpoints — Article 15 (export), Article 17 (erasure), data summary.

All routes are JWT-authenticated (dashboard use). The SDK key path is
intentionally rejected: right-of-erasure requests must come from a
verified human session.

* ``GET  /me/export``        — dump everything we store on the caller
* ``GET  /me/data-summary``  — counts + date range for the settings UI
* ``POST /me/delete``        — schedule soft delete + 30-day purge

Notes:
    * The inline-export threshold is 10 MB. Larger payloads would return a
      signed Supabase Storage URL (TODO: wire up bucket + signed URL once
      we see real payloads breach the threshold — 99% of users won't).
    * Actual row purge (hard delete) is done by a nightly Railway cron
      (out of scope for this PR — see ``006_soft_delete.sql`` TODO).
    * Rate limit on /me/export is enforced via the ``gdpr_export_requests``
      ledger: max 1 call per rolling 24h per user.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user_id
from app.db import get_db
from app.models import (
    DataExportResponse,
    DataSummaryResponse,
    DeleteAccountResponse,
)

_log = logging.getLogger(__name__)

router = APIRouter()

INLINE_EXPORT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
EXPORT_RATE_WINDOW = timedelta(hours=24)
PURGE_GRACE_PERIOD = timedelta(days=30)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


async def _collect_user_brains(user_id: str, *, include_deleted: bool = False) -> list[dict]:
    """Return brains owned by ``user_id``. Filters soft-deleted by default."""
    db = get_db()
    rows = await db.select("brains", filters={"user_id": user_id})
    if include_deleted:
        return rows
    return [r for r in rows if not r.get("deleted_at")]


async def _collect_user_workspaces(user_id: str, *, include_deleted: bool = False) -> list[dict]:
    """Return workspaces the user owns (not workspaces they're a member of)."""
    db = get_db()
    rows = await db.select("workspaces", filters={"owner_id": user_id})
    if include_deleted:
        return rows
    return [r for r in rows if not r.get("deleted_at")]


def _min_created_at(rows: list[dict]) -> str | None:
    vals = [r.get("created_at") for r in rows if r.get("created_at")]
    return min(vals) if vals else None


def _max_created_at(rows: list[dict]) -> str | None:
    vals = [r.get("created_at") for r in rows if r.get("created_at")]
    return max(vals) if vals else None


# ---------------------------------------------------------------------------
# GET /me/data-summary
# ---------------------------------------------------------------------------


@router.get("/me/data-summary", response_model=DataSummaryResponse)
async def data_summary(
    user_id: str = Depends(get_current_user_id),
) -> DataSummaryResponse:
    """Return counts + oldest/newest timestamps for the account settings UI."""
    db = get_db()

    workspaces = await _collect_user_workspaces(user_id)
    brains = await _collect_user_brains(user_id)
    brain_ids = [b["id"] for b in brains]

    all_corrections: list[dict] = []
    all_lessons: list[dict] = []
    all_events: list[dict] = []
    all_meta_rules: list[dict] = []

    for bid in brain_ids:
        all_corrections.extend(await db.select("corrections", filters={"brain_id": bid}))
        all_lessons.extend(await db.select("lessons", filters={"brain_id": bid}))
        all_events.extend(await db.select("events", filters={"brain_id": bid}))
        all_meta_rules.extend(await db.select("meta_rules", filters={"brain_id": bid}))

    all_rows = workspaces + brains + all_corrections + all_lessons + all_events + all_meta_rules
    return DataSummaryResponse(
        user_id=user_id,
        workspaces=len(workspaces),
        brains=len(brains),
        corrections=len(all_corrections),
        lessons=len(all_lessons),
        meta_rules=len(all_meta_rules),
        events=len(all_events),
        oldest_record=_min_created_at(all_rows),
        newest_record=_max_created_at(all_rows),
    )


# ---------------------------------------------------------------------------
# GET /me/export
# ---------------------------------------------------------------------------


async def _enforce_export_rate_limit(user_id: str) -> None:
    """Raise 429 if the user already exported within EXPORT_RATE_WINDOW."""
    db = get_db()
    rows = await db.select(
        "gdpr_export_requests",
        columns="id,created_at",
        filters={"user_id": user_id},
    )
    if not rows:
        return
    cutoff = _utcnow() - EXPORT_RATE_WINDOW
    for r in rows:
        created = r.get("created_at")
        if not created:
            continue
        # Accept both datetime and ISO-string forms.
        if isinstance(created, str):
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                continue
        elif isinstance(created, datetime):
            created_dt = created
        else:
            continue
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        if created_dt >= cutoff:
            raise HTTPException(
                status_code=429,
                detail="Data export is rate-limited to 1 request per 24 hours.",
            )


@router.get("/me/export", response_model=DataExportResponse)
async def export_me(
    user_id: str = Depends(get_current_user_id),
) -> DataExportResponse:
    """Export all user data as JSON (GDPR Article 15 — right of access).

    Rate-limited to 1 call per user per 24 hours. Small payloads (<10 MB)
    are returned inline; larger ones would be served via a signed URL
    (not yet required in production).
    """
    await _enforce_export_rate_limit(user_id)
    db = get_db()

    # Record the export request BEFORE generating the payload to shrink the
    # TOCTOU window between _enforce_export_rate_limit and the ledger insert.
    # A concurrent request arriving between the check and this insert will
    # either see this row (and 429) or race by milliseconds; either way the
    # 24h window bounds abuse. For true atomicity we'd need either a DB
    # uniqueness constraint on (user_id, date_bucket) or a row-level lock,
    # neither of which the current PostgREST wrapper exposes.
    await db.insert(
        "gdpr_export_requests",
        {"user_id": user_id, "created_at": _iso(_utcnow())},
    )

    workspaces = await _collect_user_workspaces(user_id, include_deleted=True)
    brains = await _collect_user_brains(user_id, include_deleted=True)
    brain_ids = [b["id"] for b in brains]

    corrections: list[dict] = []
    lessons: list[dict] = []
    events: list[dict] = []
    meta_rules: list[dict] = []
    for bid in brain_ids:
        corrections.extend(await db.select("corrections", filters={"brain_id": bid}))
        lessons.extend(await db.select("lessons", filters={"brain_id": bid}))
        events.extend(await db.select("events", filters={"brain_id": bid}))
        meta_rules.extend(await db.select("meta_rules", filters={"brain_id": bid}))

    payload: dict[str, Any] = {
        "schema_version": 1,
        "user_id": user_id,
        "generated_at": _iso(_utcnow()),
        "workspaces": workspaces,
        "brains": brains,
        "corrections": corrections,
        "lessons": lessons,
        "meta_rules": meta_rules,
        "events": events,
    }

    serialized = json.dumps(payload, default=str)
    size_bytes = len(serialized.encode("utf-8"))
    _log.info("GDPR export generated for user=%s size=%d", user_id, size_bytes)

    response = DataExportResponse(
        user_id=user_id,
        generated_at=payload["generated_at"],
        size_bytes=size_bytes,
        format="json",
    )
    if size_bytes <= INLINE_EXPORT_MAX_BYTES:
        response.data = payload
    else:
        # TODO: write to Supabase Storage and return a signed URL.
        # For now, surface a clear error so ops gets paged if it happens.
        raise HTTPException(
            status_code=507,
            detail=(
                "Export payload exceeds 10MB inline cap. Signed-URL delivery "
                "is not yet implemented. Contact privacy@gradata.ai."
            ),
        )
    return response


# ---------------------------------------------------------------------------
# POST /me/delete
# ---------------------------------------------------------------------------


async def _send_deletion_confirmation(user_id: str, email: str | None) -> None:
    """Send the 'your account is scheduled for deletion' email.

    Deliberately a stub: we don't have an ESP wired in yet. Logged so ops
    can verify the request landed while we build the email pipeline.
    Tracked follow-up: wire to the admin/ESP client once provider is chosen.
    """
    _log.info("GDPR deletion confirmation queued user=%s email=%s", user_id, email)


@router.post("/me/delete", response_model=DeleteAccountResponse, status_code=202)
async def delete_me(
    user_id: str = Depends(get_current_user_id),
) -> DeleteAccountResponse:
    """Soft-delete the caller's account (GDPR Article 17 — right to erasure).

    Cascades ``deleted_at`` to workspaces they own and brains they own.
    Actual row purge happens 30 days later via nightly cron (TODO).
    Returns 202 Accepted — deletion is scheduled, not immediate.
    """
    db = get_db()
    now = _utcnow()
    purge_after = now + PURGE_GRACE_PERIOD
    now_iso = _iso(now)
    purge_iso = _iso(purge_after)

    # Idempotency: if this user is already soft-deleted, return the existing
    # ledger state instead of re-cascading. Repeated calls otherwise reset
    # the 30-day purge window and re-tombstone owned rows for no reason.
    existing_rows = await db.select(
        "users",
        columns="id,email,deleted_at,purge_after",
        filters={"id": user_id},
    )
    if existing_rows and existing_rows[0].get("deleted_at"):
        existing = existing_rows[0]
        return DeleteAccountResponse(
            status="accepted",
            user_id=user_id,
            deleted_at=existing["deleted_at"],
            purge_after=existing.get("purge_after") or purge_iso,
        )

    # Tombstone the user row. Upsert so we don't 500 if the row is absent.
    await db.upsert(
        "users",
        {
            "id": user_id,
            "deleted_at": now_iso,
            "purge_after": purge_iso,
        },
    )

    # Cascade to workspaces they own.
    # NOTE: per-row UPDATE (N+1) is intentional — db.select has no IN/transaction
    # support yet. Tracked follow-up: switch to a single PATCH with PostgREST
    # `id=in.(...)` filter once SupabaseClient grows that helper.
    owned_workspaces = await _collect_user_workspaces(user_id, include_deleted=False)
    for ws in owned_workspaces:
        await db.update(
            "workspaces",
            data={"deleted_at": now_iso},
            filters={"id": ws["id"]},
        )

    # Cascade to brains they own.
    owned_brains = await _collect_user_brains(user_id, include_deleted=False)
    for b in owned_brains:
        await db.update(
            "brains",
            data={"deleted_at": now_iso},
            filters={"id": b["id"]},
        )

    # Resolve email from the shadow users table if present (best-effort).
    # Reuses the pre-cascade fetch above to avoid a second round-trip.
    email: str | None = existing_rows[0].get("email") if existing_rows else None
    await _send_deletion_confirmation(user_id, email)

    _log.info(
        "GDPR soft-delete user=%s workspaces=%d brains=%d purge_after=%s",
        user_id,
        len(owned_workspaces),
        len(owned_brains),
        purge_iso,
    )

    return DeleteAccountResponse(
        status="accepted",
        user_id=user_id,
        deleted_at=now_iso,
        purge_after=purge_iso,
    )
