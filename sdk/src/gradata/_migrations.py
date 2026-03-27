"""
Schema migration system for Gradata system.db.
===================================================
Evolves the events table schema. Brain uses event-sourced architecture:
all facts (outputs, corrections, rule applications) are events, not
separate domain tables.

``run_migrations`` is called from ``Brain.__init__`` on every open.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return True if *column* exists in *table*."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1].lower() == column.lower() for row in rows)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Return True if *table* exists in the database."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def run_migrations(db_path: str | Path) -> None:
    """Apply pending schema migrations to the events table.

    Event-sourced architecture: all brain data lives in the events table.
    OUTPUT, CORRECTION, RULE_APPLICATION, CALIBRATION etc. are event types,
    not separate tables.

    This function ensures the events table has all required columns and
    indexes for the current SDK version.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        # Ensure events table exists (primary creation is in _events.py,
        # but migrations should be safe to run standalone)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                session INTEGER,
                type TEXT NOT NULL,
                source TEXT,
                data_json TEXT,
                tags_json TEXT,
                valid_from TEXT,
                valid_until TEXT,
                scope TEXT DEFAULT 'local'
            )
        """)

        # Ensure indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_type ON events(session, type)")

        # Migrate: add columns that may be missing in older DBs
        for col, defn in [
            ("valid_from", "TEXT"),
            ("valid_until", "TEXT"),
            ("scope", "TEXT DEFAULT 'local'"),
        ]:
            if not _column_exists(conn, "events", col):
                conn.execute(f"ALTER TABLE events ADD COLUMN {col} {defn}")

        conn.commit()
    finally:
        conn.close()
