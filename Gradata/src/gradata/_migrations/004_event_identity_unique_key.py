# ruff: noqa: N999  # numbered migration module — digit prefix is intentional
"""Migration 004: make event identity unique on (brain_id, event_id)."""

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
from _ulid import ulid_from_iso  # type: ignore[import-not-found]
from device_uuid import get_or_create_device_id  # type: ignore[import-not-found]

NAME = "004_event_identity_unique_key"


def plan(conn: sqlite3.Connection) -> dict:
    if not table_exists(conn, "events"):
        return {"actions": []}
    return {
        "actions": [
            "DROP INDEX idx_events_dedup",
            "DROP INDEX idx_events_dedup_tenant",
            "ALTER events ADD brain_id TEXT",
            "ensure UNIQUE index idx_events_brain_event_id(brain_id, event_id)",
        ]
    }


def up(conn: sqlite3.Connection, tenant_id: str) -> dict:
    summary: dict = {
        "columns_added": [],
        "indexes_created": [],
        "indexes_dropped": [],
        "rows_backfilled": 0,
    }
    if not table_exists(conn, "events"):
        return summary

    if add_column_if_missing(conn, "events", "brain_id", "TEXT"):
        summary["columns_added"].append("events.brain_id")
    for col, decl in [
        ("event_id", "TEXT"),
        ("device_id", "TEXT"),
        ("content_hash", "TEXT"),
        ("correction_chain_id", "TEXT"),
        ("origin_agent", "TEXT"),
    ]:
        if add_column_if_missing(conn, "events", col, decl):
            summary["columns_added"].append(f"events.{col}")

    for idx in ("idx_events_dedup", "idx_events_dedup_tenant"):
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name = ?",
            (idx,),
        ).fetchone():
            conn.execute(f"DROP INDEX {idx}")
            summary["indexes_dropped"].append(idx)

    brain_dir = _brain_dir_for(conn)
    device_id = get_or_create_device_id(brain_dir)
    rows = conn.execute(
        "SELECT id, ts, type, source, data_json FROM events "
        "WHERE brain_id IS NULL OR event_id IS NULL OR device_id IS NULL OR content_hash IS NULL"
    ).fetchall()
    updates: list[tuple[str, str, str, str, int]] = []
    for row_id, ts, ev_type, source, data_json in rows:
        event_id = ulid_from_iso(ts or "")
        content_hash = _canonical_content_hash(ev_type, source, data_json)
        updates.append((tenant_id, event_id, device_id, content_hash, row_id))
    if updates:
        conn.executemany(
            "UPDATE events SET "
            "brain_id = COALESCE(brain_id, ?), "
            "event_id = COALESCE(event_id, ?), "
            "device_id = COALESCE(device_id, ?), "
            "content_hash = COALESCE(content_hash, ?) "
            "WHERE id = ?",
            updates,
        )
        summary["rows_backfilled"] = len(updates)

    if create_index_if_missing(
        conn,
        "idx_events_brain_event_id",
        "events",
        "brain_id, event_id",
        unique=True,
    ):
        summary["indexes_created"].append("idx_events_brain_event_id")
    return summary


def _canonical_content_hash(ev_type: str, source: str | None, data_json: str | None) -> str:
    import hashlib

    try:
        data = json.loads(data_json) if data_json else {}
    except (json.JSONDecodeError, TypeError):
        data = {"_raw": data_json}
    canonical = json.dumps(
        {"type": ev_type, "source": source or "", "data": data},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _brain_dir_for(conn: sqlite3.Connection) -> Path:
    row = conn.execute("PRAGMA database_list").fetchone()
    if row and row[2]:
        return Path(row[2]).resolve().parent
    return Path.cwd()


def _main() -> int:
    ap = argparse.ArgumentParser(description=f"Run migration {NAME}")
    ap.add_argument("--brain", help="Path to brain directory or system.db")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = resolve_brain_db(args.brain)
    if not db_path.exists():
        print(f"ERROR: brain DB not found at {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(str(db_path))
    try:
        if has_applied(conn, NAME) and not args.dry_run:
            print(f"Already applied: {NAME} (no-op)")
            return 0
        p = plan(conn)
        print("\n--- plan ---")
        for action in p["actions"]:
            print(f"  {action}")
        if args.dry_run:
            print("\n(dry-run) no changes made")
            return 0
        summary = up(conn, tenant_id="")
        mark_applied(
            conn,
            NAME,
            rows_affected=summary["rows_backfilled"],
            notes=json.dumps({k: v for k, v in summary.items() if k != "rows_backfilled"}),
        )
        conn.commit()
        print(json.dumps(summary, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main())
