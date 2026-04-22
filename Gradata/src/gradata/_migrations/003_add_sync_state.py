# ruff: noqa: N999  # numbered migration module — digit prefix is intentional
"""Migration 003: sync_state table + per-device watermark columns.

Creates ``sync_state`` if it does not already exist and adds the three
watermark columns the ``gradata.cloud`` push/pull client needs:

- ``device_id``           — which machine this row belongs to. Pairs with
                            ``tenant_id`` (added by Migration 001) so the
                            composite key ``(tenant_id, device_id)`` scopes
                            watermarks per machine.
- ``last_push_event_id``  — highest ULID this device has successfully
                            shipped to ``/events/push``. Resume point.
- ``last_pull_cursor``    — opaque cursor returned by ``/events/pull``.
                            Used to avoid re-downloading own events.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runner import (  # type: ignore[import-not-found]
    add_column_if_missing,
    create_index_if_missing,
    has_applied,
    mark_applied,
    resolve_brain_db,
    table_exists,
)

NAME = "003_add_sync_state"

SYNC_STATE_SQL = """
CREATE TABLE IF NOT EXISTS sync_state (
    brain_id TEXT PRIMARY KEY,
    last_push_at TEXT,
    updated_at TEXT
)
"""

NEW_COLUMNS: list[tuple[str, str]] = [
    ("device_id", "TEXT"),
    ("last_push_event_id", "TEXT"),
    ("last_pull_cursor", "TEXT"),
    ("tenant_id", "TEXT"),  # idempotent — Migration 001 may have added it already
]


def plan(conn: sqlite3.Connection) -> dict:
    actions: list[str] = []
    if not table_exists(conn, "sync_state"):
        actions.append("CREATE TABLE sync_state")
    for col, decl in NEW_COLUMNS:
        if (
            conn.execute(
                "SELECT 1 FROM pragma_table_info('sync_state') WHERE name = ?",
                (col,),
            ).fetchone()
            is None
        ):
            actions.append(f"ALTER sync_state ADD {col} {decl}")
    actions.append("ensure index idx_sync_state_device(device_id)")
    actions.append("ensure index idx_sync_state_tenant_device(tenant_id, device_id)")
    return {"actions": actions}


def up(conn: sqlite3.Connection, tenant_id: str) -> dict:
    summary: dict = {
        "columns_added": [],
        "indexes_created": [],
        "table_created": False,
        "rows_backfilled": 0,
    }

    if not table_exists(conn, "sync_state"):
        conn.execute(SYNC_STATE_SQL)
        summary["table_created"] = True

    for col, decl in NEW_COLUMNS:
        if add_column_if_missing(conn, "sync_state", col, decl):
            summary["columns_added"].append(f"sync_state.{col}")

    # Backfill tenant_id on any pre-existing rows so the composite key
    # ``(tenant_id, device_id)`` is populated end-to-end even on brains
    # upgraded through 001 → 003 in a single startup.
    cur = conn.execute(
        "UPDATE sync_state SET tenant_id = ? WHERE tenant_id IS NULL",
        (tenant_id,),
    )
    if cur.rowcount:
        summary["rows_backfilled"] += cur.rowcount

    if create_index_if_missing(conn, "idx_sync_state_device", "sync_state", "device_id"):
        summary["indexes_created"].append("idx_sync_state_device")
    if create_index_if_missing(
        conn,
        "idx_sync_state_tenant_device",
        "sync_state",
        "tenant_id, device_id",
    ):
        summary["indexes_created"].append("idx_sync_state_tenant_device")

    return summary


def _main() -> int:
    ap = argparse.ArgumentParser(description=f"Run migration {NAME}")
    ap.add_argument("--brain", help="Path to brain directory or system.db")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = resolve_brain_db(args.brain)
    if not db_path.exists():
        print(f"ERROR: brain DB not found at {db_path}", file=sys.stderr)
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tenant_uuid import get_or_create_tenant_id  # type: ignore[import-not-found]

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        if has_applied(conn, NAME) and not args.dry_run:
            print(f"Already applied: {NAME} (no-op)")
            return 0

        p = plan(conn)
        print("\n--- plan ---")
        for a in p["actions"]:
            print(f"  {a}")
        if args.dry_run:
            print("\n(dry-run) no changes made")
            return 0

        tid = get_or_create_tenant_id(db_path.parent)
        summary = up(conn, tenant_id=tid)
        mark_applied(
            conn,
            NAME,
            rows_affected=summary["rows_backfilled"],
            notes=json.dumps({k: v for k, v in summary.items() if k != "rows_backfilled"}),
        )
        conn.commit()
        print(f"table_created    : {summary['table_created']}")
        print(f"columns_added    : {summary['columns_added']}")
        print(f"indexes_created  : {summary['indexes_created']}")
        print(f"rows_backfilled  : {summary['rows_backfilled']}")
        print("\nOK")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main())
