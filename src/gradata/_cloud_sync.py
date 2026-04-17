"""Push-only cloud sync MVP for Gradata.

Reads rows tagged ``tenant_id = tenant_for(brain_dir)`` from the local
SQLite brain and POSTs them to Supabase via PostgREST. Gated by env:

    GRADATA_CLOUD_SYNC=1          enable sync (default: off)
    GRADATA_CLOUD_URL=https://..  Supabase project URL
    GRADATA_CLOUD_KEY=eyJ...      Supabase anon key (RLS-scoped to tenant)

Design (deliberately small, Karpathy-style):
- One function per table; each is a plain ``SELECT ... WHERE tenant_id = ?``
  filtered by ``last_push_at`` from the ``sync_state`` row.
- A single ``push(brain_dir)`` entrypoint that iterates the table list.
- No background threads, no queues, no retries beyond HTTP status check.
  Failure mode is "skip + log"; the next call will pick up the same rows.
- Visibility defaults to ``private``. Rows with ``visibility='shared'`` or
  ``'global'`` still push under the same tenant_id -- RLS in the cloud
  decides who else can read them.

Not yet implemented (future work, explicitly out of scope):
- Pull / conflict resolution (we're push-only MVP).
- Deletes (cloud rows never get removed by this path).
- Bulk batching beyond one table per HTTP call.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from gradata._tenant import tenant_for

_log = logging.getLogger("gradata.cloud_sync")

ENV_ENABLED: Final[str] = "GRADATA_CLOUD_SYNC"
ENV_URL: Final[str] = "GRADATA_CLOUD_URL"
ENV_KEY: Final[str] = "GRADATA_CLOUD_KEY"

# Tables pushed to the cloud. Order matters only for foreign keys; we keep
# the parent tables first so Supabase FK constraints pass on first try.
PUSH_TABLES: Final[tuple[str, ...]] = (
    "events",
    "lessons",
    "meta_rules",
    "clusters",
    "correction_patterns",
    "rule_provenance",
)


def enabled() -> bool:
    """True when the env flag is set AND both URL/key are present."""
    if os.environ.get(ENV_ENABLED, "").strip() not in ("1", "true", "yes"):
        return False
    return bool(os.environ.get(ENV_URL) and os.environ.get(ENV_KEY))


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _sync_state_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_state'"
    ).fetchone()
    return row is not None


def _last_push_at(conn: sqlite3.Connection, tenant_id: str) -> str | None:
    """Read sync_state.last_push_at. Returns None on first push or pre-migration brain."""
    if not _sync_state_exists(conn):
        return None
    row = conn.execute(
        "SELECT last_push_at FROM sync_state WHERE brain_id = ?",
        (tenant_id,),
    ).fetchone()
    return row[0] if row and row[0] else None


def _mark_push(conn: sqlite3.Connection, tenant_id: str, when: str) -> None:
    """Advance sync_state.last_push_at. No-op on pre-migration brains."""
    if not _sync_state_exists(conn):
        return
    conn.execute(
        """
        INSERT INTO sync_state (brain_id, last_push_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(brain_id) DO UPDATE SET
            last_push_at = excluded.last_push_at,
            updated_at   = excluded.updated_at
        """,
        (tenant_id, when, when),
    )
    conn.commit()


def _rows_since(
    conn: sqlite3.Connection,
    table: str,
    tenant_id: str,
    since: str | None,
) -> list[dict[str, Any]]:
    """Read rows for the given table/tenant created or updated after ``since``.

    Uses whichever timestamp column the table has (``updated_at`` > ``created_at``
    > ``ts``). If none exist, returns all rows for the tenant (one-shot tables
    like ``rule_provenance``).
    """
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if "tenant_id" not in cols:
        return []

    ts_col = next((c for c in ("updated_at", "created_at", "ts") if c in cols), None)
    where = ["tenant_id = ?"]
    params: list[Any] = [tenant_id]
    if since and ts_col:
        where.append(f"{ts_col} > ?")
        params.append(since)

    # table is allowlisted via PUSH_TABLES; column list comes from PRAGMA.
    sql = f"SELECT * FROM {table} WHERE {' AND '.join(where)}"
    cur = conn.execute(sql, params)
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def _post(table: str, rows: list[dict[str, Any]]) -> int:
    """POST rows to Supabase PostgREST. Returns count accepted."""
    if not rows:
        return 0
    url = f"{os.environ[ENV_URL].rstrip('/')}/rest/v1/{table}"
    key = os.environ[ENV_KEY]
    body = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Upsert on primary key so repeat pushes are idempotent.
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        # URL is sourced from GRADATA_CLOUD_URL env; operator-controlled.
        with urllib.request.urlopen(req, timeout=30) as resp:
            if 200 <= resp.status < 300:
                return len(rows)
            _log.warning("cloud_sync: %s returned HTTP %s", table, resp.status)
            return 0
    except urllib.error.HTTPError as e:
        _log.warning("cloud_sync: %s HTTP %s: %s", table, e.code, e.read()[:200])
        return 0
    except urllib.error.URLError as e:
        _log.warning("cloud_sync: %s network error: %s", table, e)
        return 0


def _resolve_db(brain_dir: str | Path) -> Path | None:
    """Return the SQLite path inside ``brain_dir`` if present, else None.

    Accepts either the brain directory OR the .db file directly so the caller
    can pass a BrainContext.db_path without a wrapping if-guard.
    """
    p = Path(brain_dir).expanduser().resolve()
    if p.is_file():
        return p if p.exists() else None
    for name in ("system.db", "brain.db"):
        candidate = p / name
        if candidate.exists():
            return candidate
    return None


def push(brain_dir: str | Path) -> dict[str, int]:
    """Push pending rows for this tenant to the cloud.

    Returns a dict mapping ``table -> rows_pushed``. A no-op when
    :func:`enabled` is False; safe to call unconditionally from hot paths.

    Watermark semantics: ``sync_state.last_push_at`` only advances when every
    table that had pending rows also successfully pushed them all. Any partial
    failure leaves the watermark unchanged so the next call retries.
    """
    if not enabled():
        return {}

    db_path = _resolve_db(brain_dir)
    if db_path is None:
        return {}
    brain = db_path.parent

    tenant_id = tenant_for(brain)
    conn = sqlite3.connect(db_path)
    try:
        since = _last_push_at(conn, tenant_id)
        pushed: dict[str, int] = {}
        all_ok = True
        started = _iso_now()
        for table in PUSH_TABLES:
            rows = _rows_since(conn, table, tenant_id, since)
            if not rows:
                continue
            accepted = _post(table, rows)
            pushed[table] = accepted
            if accepted != len(rows):
                all_ok = False
        if pushed and all_ok:
            _mark_push(conn, tenant_id, started)
        return pushed
    finally:
        conn.close()


__all__ = ["PUSH_TABLES", "enabled", "push"]
