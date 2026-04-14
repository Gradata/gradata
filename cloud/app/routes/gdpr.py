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

import asyncio
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


async def _require_active_user(user_id: str) -> None:
    """Raise 404 if the caller's account has been soft-deleted.

    ``get_current_user_id`` only verifies the JWT signature; once a user hits
    POST /me/delete their ``users.deleted_at`` is set but their JWT is still
    valid for its TTL. Every GDPR read handler must re-check the account is
    active before returning data or the user can keep exfiltrating after
    erasure. Raises 404 rather than 403 to avoid leaking account existence.
    """
    db = get_db()
    rows = await db.select(
        "users",
        columns="id,deleted_at",
        filters={"id": user_id},
    )
    if rows and rows[0].get("deleted_at"):
        raise HTTPException(status_code=404, detail="Account not found")


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


def _created_at_range(rows: list[dict]) -> tuple[str | None, str | None]:
    """Return (oldest, newest) ``created_at`` across rows, ignoring missing values."""
    vals = [r.get("created_at") for r in rows if r.get("created_at")]
    if not vals:
        return None, None
    return min(vals), max(vals)


# Child tables that hang off ``brain_id``. Order matters only for stable output.
_BRAIN_CHILD_TABLES: tuple[str, ...] = ("corrections", "lessons", "events", "meta_rules")


async def _collect_brain_children(brain_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch all child rows (corrections/lessons/events/meta_rules) for every brain.

    Returns a dict keyed by table name. Each (table, brain_id) select runs
    concurrently via ``asyncio.gather`` — the db wrapper has no ``in.(...)``
    support yet, so this still issues N*M round-trips, but at least they
    overlap. If ``brain_ids`` is empty, returns empty lists for every table.
    """
    db = get_db()
    if not brain_ids:
        return {table: [] for table in _BRAIN_CHILD_TABLES}

    tasks = [
        db.select(table, filters={"brain_id": bid})
        for table in _BRAIN_CHILD_TABLES
        for bid in brain_ids
    ]
    results = await asyncio.gather(*tasks)
    out: dict[str, list[dict]] = {table: [] for table in _BRAIN_CHILD_TABLES}
    # Results come back in the same order tasks were scheduled: for each table,
    # len(brain_ids) consecutive result lists.
    for table_idx, table in enumerate(_BRAIN_CHILD_TABLES):
        start = table_idx * len(brain_ids)
        for rows in results[start : start + len(brain_ids)]:
            out[table].extend(rows)
    return out


# ---------------------------------------------------------------------------
# GET /me/data-summary
# ---------------------------------------------------------------------------


@router.get("/me/data-summary", response_model=DataSummaryResponse)
async def data_summary(
    user_id: str = Depends(get_current_user_id),
) -> DataSummaryResponse:
    """Return counts + oldest/newest timestamps for the account settings UI."""
    await _require_active_user(user_id)

    workspaces, brains = await asyncio.gather(
        _collect_user_workspaces(user_id),
        _collect_user_brains(user_id),
    )
    children = await _collect_brain_children([b["id"] for b in brains])

    oldest, newest = _created_at_range(
        workspaces
        + brains
        + children["corrections"]
        + children["lessons"]
        + children["events"]
        + children["meta_rules"]
    )
    return DataSummaryResponse(
        user_id=user_id,
        workspaces=len(workspaces),
        brains=len(brains),
        corrections=len(children["corrections"]),
        lessons=len(children["lessons"]),
        meta_rules=len(children["meta_rules"]),
        events=len(children["events"]),
        oldest_record=oldest,
        newest_record=newest,
    )


# ---------------------------------------------------------------------------
# GET /me/export
# ---------------------------------------------------------------------------


async def _enforce_export_rate_limit(user_id: str) -> None:
    """Raise 429 if the user already exported within EXPORT_RATE_WINDOW."""
    db = get_db()
    # TODO(db-layer): fetch only the most recent row (order_by created_at desc,
    # limit=1) once SupabaseClient.select supports ordering/limits. Today the
    # wrapper only accepts eq filters, so we scan all rows for this user.
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
    await _require_active_user(user_id)
    await _enforce_export_rate_limit(user_id)
    db = get_db()

    workspaces, brains = await asyncio.gather(
        _collect_user_workspaces(user_id, include_deleted=True),
        _collect_user_brains(user_id, include_deleted=True),
    )
    children = await _collect_brain_children([b["id"] for b in brains])

    payload: dict[str, Any] = {
        "schema_version": 1,
        "user_id": user_id,
        "generated_at": _iso(_utcnow()),
        "workspaces": workspaces,
        "brains": brains,
        "corrections": children["corrections"],
        "lessons": children["lessons"],
        "meta_rules": children["meta_rules"],
        "events": children["events"],
    }

    serialized = json.dumps(payload, default=str)
    size_bytes = len(serialized.encode("utf-8"))

    response = DataExportResponse(
        user_id=user_id,
        generated_at=payload["generated_at"],
        size_bytes=size_bytes,
        format="json",
    )
    if size_bytes > INLINE_EXPORT_MAX_BYTES:
        # TODO: write to Supabase Storage and return a signed URL.
        # For now, surface a clear error so ops gets paged if it happens.
        # NOTE: no ledger row is inserted on this failure path — the user gets
        # to retry without burning their 24h quota on an undelivered payload.
        raise HTTPException(
            status_code=507,
            detail=(
                "Export payload exceeds 10MB inline cap. Signed-URL delivery "
                "is not yet implemented. Contact privacy@gradata.ai."
            ),
        )
    response.data = payload

    # Record the successful export AFTER the payload is assembled and the size
    # check passes. This way a 507 (or any earlier exception) does not burn the
    # user's 24h quota on an export they never actually received. TOCTOU note:
    # two concurrent requests could both pass _enforce_export_rate_limit and
    # then both insert — acceptable given the export is idempotent and the
    # window bounds abuse. For true atomicity we'd need a DB-side uniqueness
    # constraint on (user_id, date_bucket), tracked as a follow-up.
    await db.insert(
        "gdpr_export_requests",
        {"user_id": user_id, "created_at": _iso(_utcnow())},
    )
    _log.info("GDPR export generated size=%d", size_bytes)
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
    # Do not log raw user_id or email — this is a GDPR-sensitive path and
    # logs are long-lived / shipped to observability. has_email is enough
    # for ops to confirm the send path vs a silent no-op.
    _log.info("GDPR deletion confirmation queued has_email=%s", bool(email))


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

    # Cascade strategy: use PostgREST ``id=in.(...)`` bulk PATCH so each
    # resource table gets tombstoned in a single round-trip. This collapses
    # the old N+1 per-row loop into 3 writes total (workspaces, brains,
    # users) and removes most of the mid-cascade failure window. Order still
    # matters because the db wrapper has no cross-table transaction: we
    # tombstone subordinates (workspaces, brains) FIRST and the ``users`` row
    # LAST so a mid-cascade failure leaves the account recoverable (still
    # active + some subordinates down) rather than orphaned (user tombstoned
    # + subordinates still live and invisible). A best-effort rollback
    # clears any partial subordinate tombstone before we raise.
    owned_workspaces = await _collect_user_workspaces(user_id, include_deleted=False)
    owned_brains = await _collect_user_brains(user_id, include_deleted=False)
    workspace_ids = [ws["id"] for ws in owned_workspaces]
    brain_ids = [b["id"] for b in owned_brains]

    patched_workspaces = False
    patched_brains = False
    try:
        if workspace_ids:
            await db.update(
                "workspaces",
                data={"deleted_at": now_iso},
                filters={"id": workspace_ids},
            )
            patched_workspaces = True
        if brain_ids:
            await db.update(
                "brains",
                data={"deleted_at": now_iso},
                filters={"id": brain_ids},
            )
            patched_brains = True

        # Subordinates tombstoned — now mark the user deleted. Upsert so we
        # don't 500 if the shadow users row is absent.
        await db.upsert(
            "users",
            {
                "id": user_id,
                "deleted_at": now_iso,
                "purge_after": purge_iso,
            },
        )
    except Exception as exc:
        # Best-effort rollback: revert whichever bulk tombstone(s) already
        # landed so the account stays in a consistent "still active" state.
        # Any rollback failure is swallowed and logged — the user sees a 500
        # and retries.
        _log.error(
            "GDPR soft-delete cascade failed mid-flight patched_workspaces=%s patched_brains=%s",
            patched_workspaces,
            patched_brains,
            exc_info=True,
        )
        if patched_workspaces and workspace_ids:
            try:
                await db.update(
                    "workspaces",
                    data={"deleted_at": None},
                    filters={"id": workspace_ids},
                )
            except Exception:  # pragma: no cover - defensive best-effort
                _log.warning("Rollback failed for workspace tombstones")
        if patched_brains and brain_ids:
            try:
                await db.update(
                    "brains",
                    data={"deleted_at": None},
                    filters={"id": brain_ids},
                )
            except Exception:  # pragma: no cover - defensive best-effort
                _log.warning("Rollback failed for brain tombstones")
        raise HTTPException(
            status_code=500,
            detail="Account deletion failed mid-cascade. Please retry.",
        ) from exc

    # Resolve email from the shadow users table if present (best-effort).
    # Reuses the pre-cascade fetch above to avoid a second round-trip.
    email: str | None = existing_rows[0].get("email") if existing_rows else None
    await _send_deletion_confirmation(user_id, email)

    # No raw user_id / email in logs — this is a compliance-sensitive flow.
    _log.info(
        "GDPR soft-delete workspaces=%d brains=%d purge_after=%s",
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
