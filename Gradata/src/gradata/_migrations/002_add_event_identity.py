# ruff: noqa: N999  # numbered migration module — digit prefix is intentional
"""Migration 002: add event_id / device_id / content_hash to events.

Unblocks multi-device sync:
- ``event_id``         — ULID, globally unique, time-ordered. Primary cloud key.
- ``device_id``        — which machine wrote the event (authorship, ordering).
- ``content_hash``     — sha256(canonical-JSON({type, source, data})). Dedup
                         across transcript replays and push retries.
- ``correction_chain_id`` — groups a correction → lesson → graduation chain.
- ``origin_agent``     — which subagent or CLI surface emitted it. Debug only.

All five columns are nullable — existing writers keep working unchanged. The
``emit()`` path will be taught to populate them in a follow-up commit; this
migration is schema-only + chunked backfill of historical rows so nothing
looks NULL in steady state.

Backfill:
- ``event_id``     — ULID whose 48-bit timestamp component is derived from
                     ``events.ts`` via ``ulid_from_iso``. Preserves the
                     useful property that event_ids sort like timestamps.
- ``device_id``    — current device's id (from ``<brain>/.device_id``).
                     Per council: no ``legacy-*`` prefix; historical rows
                     belong to *this* machine because this is where they
                     were produced.
- ``content_hash`` — sha256 over canonical-JSON of ``{type, source, data}``
                     (same fields the emit-time hasher will use).

Chunked 10_000 rows per transaction so a brain with millions of events does
not hold a single enormous write lock. Progress is idempotent — re-running
resumes from the first row still missing an event_id.
"""

from __future__ import annotations

import argparse
import hashlib
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

NAME = "002_add_event_identity"

CHUNK_SIZE = 10_000

NEW_COLUMNS: list[tuple[str, str]] = [
    ("event_id", "TEXT"),
    ("device_id", "TEXT"),
    ("content_hash", "TEXT"),
    ("correction_chain_id", "TEXT"),
    ("origin_agent", "TEXT"),
]


def _canonical_content_hash(ev_type: str, source: str | None, data_json: str | None) -> str:
    """sha256 over canonical JSON of {type, source, data}.

    Canonical means: sort_keys + separators=(',', ':') + ensure_ascii=False.
    Any two events with the same payload produce the same hash regardless of
    how Python happened to spell the dict at write time.
    """
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


def plan(conn: sqlite3.Connection) -> dict:
    if not table_exists(conn, "events"):
        return {"actions": [], "backfill_rows": 0}

    actions: list[str] = []
    for col, decl in NEW_COLUMNS:
        if (
            conn.execute(
                "SELECT 1 FROM pragma_table_info('events') WHERE name = ?", (col,)
            ).fetchone()
            is None
        ):
            actions.append(f"ALTER events ADD {col} {decl}")

    for idx, cols in [
        ("idx_events_event_id", "event_id"),
        ("idx_events_device_id", "device_id"),
        ("idx_events_content_hash", "content_hash"),
    ]:
        actions.append(f"ensure index {idx}({cols})")

    # Rows needing backfill: event_id IS NULL is the canonical signal.
    try:
        to_backfill = conn.execute("SELECT COUNT(*) FROM events WHERE event_id IS NULL").fetchone()[
            0
        ]
    except sqlite3.OperationalError:
        # Column doesn't exist yet — everything needs backfill.
        to_backfill = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    return {
        "actions": actions,
        "backfill_rows": to_backfill,
        "chunk_size": CHUNK_SIZE,
    }


def up(conn: sqlite3.Connection, tenant_id: str) -> dict:
    """Apply migration. ``tenant_id`` is unused here but the runner passes it positionally."""
    del tenant_id  # event identity is device-scoped, not tenant-scoped
    summary: dict = {
        "columns_added": [],
        "indexes_created": [],
        "rows_backfilled": 0,
        "chunks_committed": 0,
    }

    if not table_exists(conn, "events"):
        return summary

    # 1. Schema — all nullable so concurrent writers keep working.
    for col, decl in NEW_COLUMNS:
        if add_column_if_missing(conn, "events", col, decl):
            summary["columns_added"].append(f"events.{col}")

    # 2. Indexes.
    if create_index_if_missing(conn, "idx_events_event_id", "events", "event_id"):
        summary["indexes_created"].append("idx_events_event_id")
    if create_index_if_missing(conn, "idx_events_device_id", "events", "device_id"):
        summary["indexes_created"].append("idx_events_device_id")
    if create_index_if_missing(conn, "idx_events_content_hash", "events", "content_hash"):
        summary["indexes_created"].append("idx_events_content_hash")

    # 3. Chunked backfill. Resolve device_id once — assigned to every
    # historical row on this machine (per council: no legacy-* prefix).
    brain_dir = _brain_dir_for(conn)
    device_id = get_or_create_device_id(brain_dir)

    while True:
        rows = conn.execute(
            "SELECT id, ts, type, source, data_json FROM events WHERE event_id IS NULL LIMIT ?",
            (CHUNK_SIZE,),
        ).fetchall()
        if not rows:
            break
        updates: list[tuple[str, str, str, int]] = []
        for row_id, ts, ev_type, source, data_json in rows:
            eid = ulid_from_iso(ts or "")
            chash = _canonical_content_hash(ev_type, source, data_json)
            updates.append((eid, device_id, chash, row_id))
        conn.executemany(
            "UPDATE events SET event_id = ?, device_id = ?, content_hash = ? WHERE id = ?",
            updates,
        )
        summary["rows_backfilled"] += len(updates)
        summary["chunks_committed"] += 1
        # Intermediate commit: lets other writers make progress between chunks.
        # The runner's outer commit still fences the migration-applied row so
        # partial work is safely resumable on next startup.
        conn.commit()

    return summary


def _brain_dir_for(conn: sqlite3.Connection) -> Path:
    """Best-effort resolution of the brain directory from an open connection."""
    row = conn.execute("PRAGMA database_list").fetchone()
    # row = (seq, name, file)
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
        print(f"  backfill {p['backfill_rows']} rows (chunk={p['chunk_size']})")

        if args.dry_run:
            print("\n(dry-run) no changes made")
            return 0

        print("\n--- applying ---")
        summary = up(conn, tenant_id="")
        mark_applied(
            conn,
            NAME,
            rows_affected=summary["rows_backfilled"],
            notes=json.dumps({k: v for k, v in summary.items() if k != "rows_backfilled"}),
        )
        conn.commit()
        print(f"columns_added    : {summary['columns_added']}")
        print(f"indexes_created  : {summary['indexes_created']}")
        print(f"rows_backfilled  : {summary['rows_backfilled']}")
        print(f"chunks_committed : {summary['chunks_committed']}")
        print("\nOK")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main())
