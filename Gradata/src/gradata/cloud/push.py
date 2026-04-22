"""Client for the unified ``POST /events/push`` endpoint.

Reads rows from the local ``events`` table that have not yet been pushed for
this device, chunks them into batches, and POSTs each batch with exponential
backoff. Watermark advances via ``sync_state.last_push_event_id`` on success.

The endpoint contract (per Phase-1 plan):

    POST {api_base}/events/push
    Authorization: Bearer <credential>
    Body:
      {
        "brain_id": "<tenant_id>",
        "device_id": "dev_<32hex>",
        "events": [ {event_id, ...}, ... ]
      }
    Response 2xx: {"accepted": <int>, "rejected": [...]}

Safety properties:
  - Never raises from ``push_pending_events``: returns a summary dict.
  - Honours ``_credentials.kill_switch_set()`` — exits early when on.
  - Skips entirely when cloud sync is disabled or no credential resolves.
  - Advances watermark only after every batch of a run succeeds.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from gradata import __version__ as _sdk_version
from gradata._http import require_https
from gradata._migrations.device_uuid import get_or_create_device_id
from gradata._tenant import tenant_for
from gradata.cloud import _credentials as _creds
from gradata.cloud._sync_state import _ensure_schema as _ensure_sync_state_schema
from gradata.cloud.sync import load_config

log = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0


def _fetch_events_since(
    conn: sqlite3.Connection,
    last_event_id: str | None,
    limit: int,
    tenant_id: str,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` rows from ``events`` with event_id > watermark.

    Rows are scoped to the caller's ``tenant_id`` (plus legacy rows written
    before tenant tagging, where ``tenant_id IS NULL``). Without this filter,
    a brain that ever held rows from another tenant would upload them under
    the current tenant's identity — the request body stamps the whole batch
    with ``tenant_id`` regardless of each row's origin.
    """
    cursor_clause = ""
    params: list[Any] = [tenant_id]
    if last_event_id:
        cursor_clause = "AND event_id > ?"
        params.append(last_event_id)

    sql = f"""
        SELECT event_id, type, source, session, ts, data_json, tags_json,
               device_id, content_hash, correction_chain_id, origin_agent
        FROM events
        WHERE event_id IS NOT NULL
          AND (tenant_id = ? OR tenant_id IS NULL)
          {cursor_clause}
        ORDER BY event_id ASC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        (
            ev_id,
            ev_type,
            source,
            session,
            ts,
            data_json,
            tags_json,
            device_id,
            content_hash,
            corr_chain,
            origin_agent,
        ) = row
        try:
            data = json.loads(data_json) if data_json else None
        except (TypeError, json.JSONDecodeError):
            data = None
        try:
            tags = json.loads(tags_json) if tags_json else []
        except (TypeError, json.JSONDecodeError):
            tags = []
        out.append(
            {
                "event_id": ev_id,
                "type": ev_type,
                "source": source,
                "session": session,
                "ts": ts,
                "data": data,
                "tags": tags,
                "device_id": device_id,
                "content_hash": content_hash,
                "correction_chain_id": corr_chain,
                "origin_agent": origin_agent,
            }
        )
    return out


def _read_watermark(
    conn: sqlite3.Connection,
    tenant_id: str,
    device_id: str,
) -> str | None:
    """Return ``sync_state.last_push_event_id`` scoped to (tenant, device)."""
    try:
        row = conn.execute(
            "SELECT last_push_event_id FROM sync_state WHERE tenant_id = ? AND device_id = ?",
            (tenant_id, device_id),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row and row[0] else None


def _write_watermark(
    conn: sqlite3.Connection,
    tenant_id: str,
    device_id: str,
    new_event_id: str,
    now_iso: str,
) -> None:
    """Upsert ``sync_state`` for (tenant, device) with the new watermark.

    ``brain_id`` is encoded as ``"{tenant_id}:{device_id}"`` so the legacy
    PRIMARY KEY on ``brain_id`` naturally scopes per-device. The ON CONFLICT
    target is the composite ``(tenant_id, device_id)`` unique index so two
    devices on the same tenant never overwrite each other's watermarks.
    """
    composite_brain_id = f"{tenant_id}:{device_id}"
    conn.execute(
        """
        INSERT INTO sync_state (brain_id, device_id, tenant_id,
                                last_push_event_id, last_push_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(tenant_id, device_id) DO UPDATE SET
            brain_id = excluded.brain_id,
            last_push_event_id = excluded.last_push_event_id,
            last_push_at = excluded.last_push_at,
            updated_at = excluded.updated_at
        """,
        (composite_brain_id, device_id, tenant_id, new_event_id, now_iso, now_iso),
    )
    conn.commit()


def _post_batch(
    url: str,
    credential: str,
    body: dict[str, Any],
    timeout: float,
    max_retries: int,
    backoff_base: float,
) -> tuple[bool, dict[str, Any] | None]:
    """POST a single batch with exponential backoff. Returns (ok, response)."""
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {credential}",
        "Content-Type": "application/json",
        "User-Agent": f"gradata-sdk/{_sdk_version} events-push",
    }

    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8") if resp else ""
                parsed = json.loads(raw) if raw else {}
                return True, parsed
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                log.warning("events/push rejected (HTTP %s): %s", e.code, e.reason)
                return False, None
            log.debug("events/push transient HTTP %s (attempt %s)", e.code, attempt + 1)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            log.debug("events/push transport error (attempt %s): %s", attempt + 1, e)

        if attempt < max_retries:
            time.sleep(backoff_base * (2**attempt))

    return False, None


def push_pending_events(
    brain_dir: str | Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Push all pending events for this device to the cloud.

    Returns a summary dict.
    """
    summary: dict[str, Any] = {
        "status": "ok",
        "events_pushed": 0,
        "batches": 0,
        "last_event_id": None,
    }

    # Validate tunables up front — negative backoff or retries would either
    # spin forever, hammer the endpoint, or pass a negative delay to
    # ``time.sleep`` (raises). The public contract is "return a summary,
    # never raise", so reject garbage inputs explicitly.
    try:
        chunk_size_i = int(chunk_size)
        max_retries_i = int(max_retries)
        backoff_base_f = float(backoff_base)
        timeout_f = float(timeout)
    except (TypeError, ValueError):
        summary["status"] = "error"
        summary["reason"] = "invalid_params"
        return summary
    if chunk_size_i < 1 or max_retries_i < 0 or backoff_base_f < 0 or timeout_f <= 0:
        summary["status"] = "error"
        summary["reason"] = "invalid_params"
        return summary

    brain = Path(brain_dir).resolve()
    db = brain / "system.db"
    if not db.is_file():
        summary["status"] = "error"
        summary["reason"] = "no_db"
        return summary

    if _creds.kill_switch_set():
        summary["status"] = "kill_switch"
        return summary

    try:
        config = load_config(brain)
    except Exception as exc:
        log.debug("events/push: config load failed: %s", exc)
        summary["status"] = "error"
        summary["reason"] = "config_load_failed"
        return summary

    if not config.sync_enabled:
        summary["status"] = "disabled"
        return summary

    resolved = config.token.strip() or _creds.resolve_credential()
    if not resolved:
        summary["status"] = "no_credential"
        return summary

    # Use the shared endpoint resolver so env overrides (``GRADATA_ENDPOINT``
    # / ``GRADATA_CLOUD_API_BASE``) apply symmetrically to push and pull.
    api_base = _creds.resolve_endpoint(fallback=config.api_base or "").rstrip("/")
    try:
        require_https(api_base, "api_base")
    except ValueError as exc:
        log.error("events/push refused — %s", exc)
        summary["status"] = "error"
        summary["reason"] = "https_required"
        return summary

    url = f"{api_base}/events/push"
    tenant_id = tenant_for(brain)
    device_id = get_or_create_device_id(brain)
    now_iso = _dt.datetime.now(_dt.UTC).isoformat()

    try:
        conn = sqlite3.connect(str(db))
    except sqlite3.Error as exc:
        log.debug("events/push: sqlite connect failed: %s", exc)
        summary["status"] = "error"
        summary["reason"] = "db_error"
        return summary
    try:
        _ensure_sync_state_schema(conn, db)
        watermark = _read_watermark(conn, tenant_id, device_id)
        batches = 0
        pushed = 0
        last_id = watermark
        while True:
            events = _fetch_events_since(conn, last_id, chunk_size_i, tenant_id)
            if not events:
                break
            body = {
                "brain_id": tenant_id,
                "device_id": device_id,
                "events": events,
            }
            ok, resp = _post_batch(
                url,
                resolved,
                body,
                timeout=timeout_f,
                max_retries=max_retries_i,
                backoff_base=backoff_base_f,
            )
            if not ok:
                summary["status"] = "error"
                summary["reason"] = "batch_failed_after_retries"
                summary["events_pushed"] = pushed
                summary["batches"] = batches
                summary["last_event_id"] = last_id
                return summary

            # Advance watermark only when the server accepted every event in
            # the batch. A partial 2xx (rejected list, or accepted < sent)
            # would otherwise permanently skip rejected rows on the next run.
            resp_dict = resp or {}
            rejected = list(resp_dict.get("rejected") or [])
            accepted_raw = resp_dict.get("accepted")
            try:
                accepted = int(accepted_raw) if accepted_raw is not None else len(events)
            except (TypeError, ValueError):
                accepted = -1
            if rejected or accepted != len(events):
                summary["status"] = "error"
                summary["reason"] = "batch_rejected"
                summary["events_pushed"] = pushed
                summary["batches"] = batches
                summary["last_event_id"] = last_id
                summary["rejected"] = rejected
                return summary

            batches += 1
            pushed += len(events)
            last_id = events[-1]["event_id"]
            _write_watermark(conn, tenant_id, device_id, last_id, now_iso)

        summary["events_pushed"] = pushed
        summary["batches"] = batches
        summary["last_event_id"] = last_id
        return summary
    except sqlite3.Error as exc:
        # The public contract is "return a summary dict, never raise" — a
        # locked or corrupted system.db shouldn't crash the caller. The
        # watermark is only advanced after a successful _write_watermark,
        # so partial progress through the loop is safe to report.
        log.debug("events/push: sqlite workflow failed: %s", exc)
        summary["status"] = "error"
        summary["reason"] = "db_error"
        return summary
    finally:
        conn.close()


__all__ = ["push_pending_events"]
