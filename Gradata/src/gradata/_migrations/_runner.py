"""Migration runner helpers.

Single source of truth for:
- ``migrations`` table (idempotency tracking)
- ``has_applied`` / ``mark_applied``
- Safe column / index existence checks for SQLite
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
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
    """Check whether a migration is recorded as applied. Pure read.

    Returns False if the ``migrations`` table does not yet exist — the
    caller (orchestrator) is responsible for creating it before marking
    anything applied. Keeping this read-only avoids surprise writes when
    tooling probes migration state.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migrations'"
    ).fetchone()
    if row is None:
        return False
    row = conn.execute("SELECT 1 FROM migrations WHERE name = ?", (name,)).fetchone()
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
        (name, datetime.now(UTC).isoformat(), rows_affected, notes),
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
    *,
    unique: bool = False,
) -> bool:
    """Create an index, upgrading a non-UNIQUE version in place when needed.

    When ``unique=True`` and a regular (non-UNIQUE) index with the same name
    already exists, it is dropped and recreated as UNIQUE so ``ON CONFLICT``
    clauses that target the indexed columns resolve correctly. SQLite requires
    a UNIQUE constraint to back any ON CONFLICT target.
    """
    if not table_exists(conn, table):
        return False
    if index_exists(conn, index):
        if not unique:
            return False
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name = ?",
            (index,),
        ).fetchone()
        existing_sql = (row[0] or "") if row else ""
        if "UNIQUE" in existing_sql.upper():
            return False
        # IF EXISTS closes the TOCTOU window between index_exists() and the
        # drop — a concurrent migration could have dropped the index first.
        conn.execute(f"DROP INDEX IF EXISTS {index}")
    kw = "UNIQUE INDEX" if unique else "INDEX"
    conn.execute(f"CREATE {kw} {index} ON {table} ({columns})")
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
