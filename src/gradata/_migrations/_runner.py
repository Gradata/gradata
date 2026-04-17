"""Migration runner helpers.

Single source of truth for:
- ``migrations`` table (idempotency tracking)
- ``has_applied`` / ``mark_applied``
- Safe column / index existence checks for SQLite
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL,
    rows_affected INTEGER DEFAULT 0,
    notes TEXT DEFAULT ''
)
"""


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Create the ``migrations`` tracking table. Caller owns the commit."""
    conn.execute(MIGRATIONS_TABLE_SQL)


def has_applied(conn: sqlite3.Connection, name: str) -> bool:
    ensure_migrations_table(conn)
    row = conn.execute(
        "SELECT 1 FROM migrations WHERE name = ?", (name,)
    ).fetchone()
    return row is not None


def mark_applied(
    conn: sqlite3.Connection,
    name: str,
    rows_affected: int = 0,
    notes: str = "",
) -> None:
    """Record a migration as applied. Caller owns the commit so the
    schema-change + tracking row land in one transaction."""
    ensure_migrations_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO migrations (name, applied_at, rows_affected, notes) "
        "VALUES (?, ?, ?, ?)",
        (name, datetime.now(timezone.utc).isoformat(), rows_affected, notes),
    )


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def index_exists(conn: sqlite3.Connection, index: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name = ?", (index,)
    ).fetchone()
    return row is not None


def add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    decl: str,
) -> bool:
    """Returns True if column was added, False if already present."""
    if not table_exists(conn, table):
        return False
    if column_exists(conn, table, column):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    return True


def create_index_if_missing(
    conn: sqlite3.Connection,
    index: str,
    table: str,
    columns: str,
) -> bool:
    if not table_exists(conn, table):
        return False
    if index_exists(conn, index):
        return False
    conn.execute(f"CREATE INDEX {index} ON {table} ({columns})")
    return True


def resolve_brain_db(brain_arg: str | Path | None) -> Path:
    """Resolve the brain SQLite path from a CLI arg or env."""
    import os
    if brain_arg:
        p = Path(brain_arg).expanduser().resolve()
    else:
        env = os.environ.get("GRADATA_BRAIN_DIR", "").strip()
        p = Path(env).expanduser().resolve() if env else Path.cwd() / "brain"
    if p.is_file():
        return p
    return p / "system.db"
