"""Migration 001: add tenant_id, visibility, schema_version.

Makes the brain multi-tenant aware WITHOUT changing how it behaves today.

What this does:
1. Create ``migrations`` + ``tenant_registry`` tables.
2. Ensure ``<brain>/.tenant_id`` exists; read it as "Oliver's tenant UUID".
3. Add ``tenant_id TEXT`` (nullable) to every per-tenant table and backfill
   all existing rows to that UUID.
4. Add ``visibility TEXT DEFAULT 'private'`` to meta_rules / frameworks /
   rule_relationships and backfill NULLs.
5. Add ``schema_version INTEGER DEFAULT 1`` to events.
6. Create ``idx_<table>_tenant`` on each per-tenant table for query perf.
7. Record migration in ``migrations`` table.

Idempotent: re-running is a no-op once applied. Safe.

Dry run:
    python src/gradata/_migrations/001_add_tenant_id.py --brain <path> --dry-run

Apply:
    python src/gradata/_migrations/001_add_tenant_id.py --brain <path>
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# The file name starts with a digit so it's run as a script, not imported
# as a module. Add the parent dir to sys.path for the helper imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runner import (  # type: ignore[import-not-found]  # noqa: E402
    add_column_if_missing,
    column_exists,
    create_index_if_missing,
    has_applied,
    mark_applied,
    resolve_brain_db,
    table_exists,
)
from tenant_uuid import get_or_create_tenant_id  # type: ignore[import-not-found]  # noqa: E402


NAME = "001_add_tenant_id"


# Tables that belong to ONE tenant (add NOT-NULL-intent tenant_id, backfill).
PER_TENANT_TABLES: list[str] = [
    "deals",
    "signals",
    "audit_scores",
    "gate_triggers",
    "lesson_applications",
    "entities",
    "relationships",
    "decisions",
    "pipeline_snapshots",
    "daily_metrics",
    "activity_log",
    "prep_outcomes",
    "events",
    "facts",
    "session_metrics",
    "session_gates",
    "output_classifications",
    "correction_severity",
    "ablation_log",
    "rule_provenance",
    "correction_patterns",
    "tasks",
    "agent_jobs",
    "demo_recordings",
    "pending_approvals",
    "brain_embeddings",
    "brain_fts_content",
    "enrichment_queue",
    "enrichment_processed_files",
    "rule_canary",
    "lesson_transitions",
    "sync_state",
]

# Tables that are "mixed" — some rows may be shareable across tenants.
# Get tenant_id (nullable; NULL = global) AND a visibility column.
MIXED_VISIBILITY_TABLES: list[str] = [
    "meta_rules",
    "frameworks",
    "rule_relationships",
]

# Tables we deliberately DO NOT touch.
#   sqlite_sequence      — sqlite internals
#   sqlite_master        — sqlite internals
#   brain_fts            — FTS5 virtual table (content table handled separately)
#   brain_fts_data/idx/docsize/config — FTS5 shadow tables
#   migrations           — created by the runner
#   tenant_registry      — created by this migration


TENANT_REGISTRY_SQL = """
CREATE TABLE IF NOT EXISTS tenant_registry (
    tenant_id TEXT PRIMARY KEY,
    display_name TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    notes TEXT DEFAULT ''
)
"""


def plan(conn: sqlite3.Connection) -> dict:
    """Return a dict describing what up() would do. Read-only."""
    actions: list[str] = []
    row_backfills: list[tuple[str, int]] = []

    if not table_exists(conn, "tenant_registry"):
        actions.append("CREATE TABLE tenant_registry")

    for t in PER_TENANT_TABLES:
        if not table_exists(conn, t):
            continue
        if not column_exists(conn, t, "tenant_id"):
            actions.append(f"ALTER {t} ADD tenant_id TEXT")
        # Backfill count: rows where tenant_id is NULL (or column doesn't exist -> all rows)
        if column_exists(conn, t, "tenant_id"):
            cnt = conn.execute(
                f"SELECT COUNT(*) FROM {t} WHERE tenant_id IS NULL"
            ).fetchone()[0]
        else:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        if cnt:
            row_backfills.append((t, cnt))
        idx = f"idx_{t}_tenant"
        actions.append(f"ensure index {idx}(tenant_id)")

    for t in MIXED_VISIBILITY_TABLES:
        if not table_exists(conn, t):
            continue
        if not column_exists(conn, t, "tenant_id"):
            actions.append(f"ALTER {t} ADD tenant_id TEXT")
        if not column_exists(conn, t, "visibility"):
            actions.append(f"ALTER {t} ADD visibility TEXT DEFAULT 'private'")

    if table_exists(conn, "events") and not column_exists(
        conn, "events", "schema_version"
    ):
        actions.append("ALTER events ADD schema_version INTEGER DEFAULT 1")

    return {
        "actions": actions,
        "row_backfills": row_backfills,
        "total_rows_to_backfill": sum(c for _, c in row_backfills),
    }


def up(conn: sqlite3.Connection, tenant_id: str) -> dict:
    """Apply the migration. Returns summary dict."""
    summary: dict = {
        "columns_added": [],
        "indexes_created": [],
        "rows_backfilled": 0,
        "tables_backfilled": {},
        "visibility_backfilled": 0,
    }

    # 1. tenant_registry
    conn.execute(TENANT_REGISTRY_SQL)
    conn.execute(
        "INSERT OR IGNORE INTO tenant_registry "
        "(tenant_id, display_name, created_at, is_primary, notes) "
        "VALUES (?, ?, ?, 1, 'primary tenant — first brain, backfilled')",
        (tenant_id, "primary", datetime.now(timezone.utc).isoformat()),
    )

    # 2. Per-tenant tables
    for t in PER_TENANT_TABLES:
        if not table_exists(conn, t):
            continue
        if add_column_if_missing(conn, t, "tenant_id", "TEXT"):
            summary["columns_added"].append(f"{t}.tenant_id")
        # Backfill
        cur = conn.execute(
            f"UPDATE {t} SET tenant_id = ? WHERE tenant_id IS NULL",
            (tenant_id,),
        )
        if cur.rowcount:
            summary["rows_backfilled"] += cur.rowcount
            summary["tables_backfilled"][t] = cur.rowcount
        # Index
        idx = f"idx_{t}_tenant"
        if create_index_if_missing(conn, idx, t, "tenant_id"):
            summary["indexes_created"].append(idx)

    # 3. Mixed visibility tables
    for t in MIXED_VISIBILITY_TABLES:
        if not table_exists(conn, t):
            continue
        if add_column_if_missing(conn, t, "tenant_id", "TEXT"):
            summary["columns_added"].append(f"{t}.tenant_id")
        if add_column_if_missing(
            conn, t, "visibility", "TEXT DEFAULT 'private'"
        ):
            summary["columns_added"].append(f"{t}.visibility")
        # Backfill visibility for pre-existing NULLs
        cur = conn.execute(
            f"UPDATE {t} SET visibility = 'private' WHERE visibility IS NULL"
        )
        summary["visibility_backfilled"] += cur.rowcount
        # Backfill tenant_id: all existing rows belong to primary tenant.
        # Future: admin can promote rows to visibility='global' & tenant_id=NULL.
        cur = conn.execute(
            f"UPDATE {t} SET tenant_id = ? WHERE tenant_id IS NULL",
            (tenant_id,),
        )
        if cur.rowcount:
            summary["rows_backfilled"] += cur.rowcount
            summary["tables_backfilled"][t] = (
                summary["tables_backfilled"].get(t, 0) + cur.rowcount
            )
        idx = f"idx_{t}_tenant"
        if create_index_if_missing(conn, idx, t, "tenant_id"):
            summary["indexes_created"].append(idx)
        idx_v = f"idx_{t}_visibility"
        if create_index_if_missing(conn, idx_v, t, "visibility"):
            summary["indexes_created"].append(idx_v)

    # 4. events.schema_version
    if table_exists(conn, "events") and add_column_if_missing(
        conn, "events", "schema_version", "INTEGER DEFAULT 1"
    ):
        summary["columns_added"].append("events.schema_version")
        conn.execute(
            "UPDATE events SET schema_version = 1 WHERE schema_version IS NULL"
        )

    conn.commit()
    return summary


def _main() -> int:
    ap = argparse.ArgumentParser(description=f"Run migration {NAME}")
    ap.add_argument(
        "--brain",
        help="Path to brain directory or system.db file (defaults to $GRADATA_BRAIN_DIR or ./brain)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without modifying DB",
    )
    args = ap.parse_args()

    db_path = resolve_brain_db(args.brain)
    if not db_path.exists():
        print(f"ERROR: brain DB not found at {db_path}", file=sys.stderr)
        return 2

    brain_dir = db_path.parent
    tid = get_or_create_tenant_id(brain_dir)
    print(f"Brain   : {db_path}")
    print(f"Tenant  : {tid}")

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
        print(
            f"  backfill {p['total_rows_to_backfill']} rows across "
            f"{len(p['row_backfills'])} tables"
        )
        if p["row_backfills"]:
            sample = p["row_backfills"][:10]
            for t, c in sample:
                print(f"    {t:30s} {c:>8} rows")
            if len(p["row_backfills"]) > 10:
                print(f"    ... and {len(p['row_backfills']) - 10} more")

        if args.dry_run:
            print("\n(dry-run) no changes made")
            return 0

        print("\n--- applying ---")
        summary = up(conn, tenant_id=tid)
        mark_applied(
            conn,
            NAME,
            rows_affected=summary["rows_backfilled"],
            notes=f"primary tenant {tid}",
        )
        print(f"columns_added          : {len(summary['columns_added'])}")
        for c in summary["columns_added"]:
            print(f"  + {c}")
        print(f"indexes_created        : {len(summary['indexes_created'])}")
        print(f"rows_backfilled        : {summary['rows_backfilled']}")
        print(f"visibility_backfilled  : {summary['visibility_backfilled']}")
        print("\nOK")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main())
