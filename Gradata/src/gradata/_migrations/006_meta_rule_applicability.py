# ruff: noqa: N999  # numbered migration module - digit prefix is intentional
"""Migration 006: meta-rule applicability observations."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runner import (  # type: ignore[import-not-found]
    add_column_if_missing,
    column_exists,
    ensure_migrations_table,
    has_applied,
    mark_applied,
    resolve_brain_db,
    table_exists,
)

NAME = "006_meta_rule_applicability"


def plan(conn: sqlite3.Connection) -> dict:
    actions: list[str] = []
    if not table_exists(conn, "meta_rules"):
        actions.append("skip: meta_rules table missing")
        return {"actions": actions}
    if not column_exists(conn, "meta_rules", "applicability_observed_count"):
        actions.append("ALTER TABLE meta_rules ADD COLUMN applicability_observed_count INTEGER")
    if not actions:
        actions.append("no-op: columns already present")
    return {"actions": actions}


def up(conn: sqlite3.Connection, tenant_id: str | None = None) -> dict:
    del tenant_id
    summary = {"columns_added": []}
    if add_column_if_missing(conn, "meta_rules", "applicability_observed_count", "INTEGER"):
        summary["columns_added"].append("applicability_observed_count")
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

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        ensure_migrations_table(conn)
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

        summary = up(conn)
        mark_applied(conn, NAME, notes=json.dumps(summary))
        conn.commit()
        print(f"columns_added : {summary['columns_added']}")
        print("\nOK")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main())
