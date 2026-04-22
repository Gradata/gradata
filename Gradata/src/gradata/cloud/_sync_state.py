"""Per-brain/per-device watermark persistence for ``/events/pull`` and push.

Thin SQLite wrapper around the ``sync_state`` table introduced by
``_migrations/003_add_sync_state.py``. Key is ``(tenant_id, device_id)``.

Used by:
- ``cloud.pull.pull_events`` to persist ``last_pull_cursor`` after a
  successful apply so the next pull can resume incrementally.
- ``cloud.push`` to persist ``last_push_event_id`` (already wired in
  Phase 1 — re-exported here for a single canonical API surface).

Never raises — watermark loss is recoverable by replaying the stream.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)


_SCHEMA_ENSURED: set[str] = set()


def _ensure_schema(conn: sqlite3.Connection, db_path: Path) -> None:
    """Idempotently create ``sync_state`` + required columns.

    Normally Migration 003 lands this table. This helper lets a callsite
    use the cursor API on brains that predate 003 (or where migrations
    haven't run yet in a test fixture).
    """
    key = str(db_path)
    if key in _SCHEMA_ENSURED:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_state (
            brain_id TEXT PRIMARY KEY,
            last_push_at TEXT,
            updated_at TEXT
        )
        """
    )
    for col, decl in (
        ("tenant_id", "TEXT"),
        ("device_id", "TEXT"),
        ("last_push_event_id", "TEXT"),
        ("last_pull_cursor", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE sync_state ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()
    _SCHEMA_ENSURED.add(key)


def _connect(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA busy_timeout=5000")
        _ensure_schema(conn, db_path)
        return conn
    except sqlite3.Error as exc:
        _log.debug("sync_state connect failed: %s", exc)
        return None


def update_pull_cursor(
    db_path: Path,
    *,
    tenant_id: str,
    device_id: str,
    cursor: str,
) -> bool:
    """Persist ``cursor`` as the latest pulled watermark. Returns True on success."""
    if not cursor:
        return False
    conn = _connect(db_path)
    if conn is None:
        return False
    now = datetime.now(UTC).isoformat()
    try:
        with contextlib.closing(conn):
            conn.execute(
                """
                INSERT INTO sync_state (brain_id, tenant_id, device_id, last_pull_cursor, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(brain_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    device_id = excluded.device_id,
                    last_pull_cursor = excluded.last_pull_cursor,
                    updated_at = excluded.updated_at
                """,
                (tenant_id, tenant_id, device_id, cursor, now),
            )
            conn.commit()
        return True
    except sqlite3.Error as exc:
        _log.debug("update_pull_cursor failed: %s", exc)
        return False


def get_pull_cursor(
    db_path: Path,
    *,
    tenant_id: str,
    device_id: str,
) -> str | None:
    """Return the last persisted pull cursor for ``(tenant_id, device_id)`` or None."""
    conn = _connect(db_path)
    if conn is None:
        return None
    try:
        with contextlib.closing(conn):
            row = conn.execute(
                "SELECT last_pull_cursor FROM sync_state WHERE tenant_id = ? AND device_id = ?",
                (tenant_id, device_id),
            ).fetchone()
    except sqlite3.Error as exc:
        _log.debug("get_pull_cursor failed: %s", exc)
        return None
    return row[0] if row and row[0] else None


__all__ = ["get_pull_cursor", "update_pull_cursor"]
