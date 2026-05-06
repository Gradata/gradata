# ruff: noqa: N999  # numbered migration module - digit prefix is intentional
"""Migration 005: session-start injection watermarks."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _runner import (  # type: ignore[import-not-found]
    create_index_if_missing,
    ensure_migrations_table,
    has_applied,
    mark_applied,
    resolve_brain_db,
    table_exists,
)

NAME = "005_injection_log"

INJECTION_LOG_SQL = """
CREATE TABLE IF NOT EXISTS injection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    rule_ids TEXT NOT NULL,
    full_set_hash TEXT NOT NULL
)
"""


def plan(conn: sqlite3.Connection) -> dict:
    actions: list[str] = []
    if not table_exists(conn, "injection_log"):
        actions.append("CREATE TABLE injection_log")
    actions.append("ensure index idx_injection_log_agent_ts(agent_type, ts)")
    return {"actions": actions}


def up(conn: sqlite3.Connection, tenant_id: str | None = None) -> dict:
    del tenant_id
    summary = {"table_created": False, "indexes_created": [], "rows_backfilled": 0}
    if not table_exists(conn, "injection_log"):
        conn.execute(INJECTION_LOG_SQL)
        summary["table_created"] = True
    if create_index_if_missing(
        conn,
        "idx_injection_log_agent_ts",
        "injection_log",
        "agent_type, ts",
    ):
        summary["indexes_created"].append("idx_injection_log_agent_ts")
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
        for a in p["actions"]:
            print(f"  {a}")
        if args.dry_run:
            print("\n(dry-run) no changes made")
            return 0

        summary = up(conn)
        mark_applied(conn, NAME, notes=json.dumps(summary))
        conn.commit()
        print(f"table_created    : {summary['table_created']}")
        print(f"indexes_created  : {summary['indexes_created']}")
        print("\nOK")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main())
