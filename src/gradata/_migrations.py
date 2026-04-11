"""Schema migrations for system.db."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

from gradata._db import get_connection

_BASE_TABLES: list[str] = [
    """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        session INTEGER,
        type TEXT NOT NULL,
        source TEXT,
        data_json TEXT,
        tags_json TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS lesson_transitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_desc TEXT NOT NULL,
        category TEXT NOT NULL,
        old_state TEXT NOT NULL,
        new_state TEXT NOT NULL,
        confidence REAL,
        fire_count INTEGER DEFAULT 0,
        session INTEGER,
        transitioned_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS pending_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_category TEXT NOT NULL,
        lesson_description TEXT NOT NULL,
        draft_text TEXT,
        final_text TEXT,
        severity TEXT,
        correction_event_id TEXT,
        agent_type TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        resolution TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS rule_provenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id TEXT NOT NULL,
        correction_event_id TEXT,
        session INTEGER,
        timestamp TEXT NOT NULL,
        user_context TEXT
    )""",
]

_MIGRATIONS: list[str] = [
    # Events table
    "ALTER TABLE events ADD COLUMN valid_from TEXT",
    "ALTER TABLE events ADD COLUMN valid_until TEXT",
    "ALTER TABLE events ADD COLUMN scope TEXT DEFAULT 'local'",
    "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_events_session_type ON events(session, type)",
    # Meta-rules table (columns added after initial schema)
    "ALTER TABLE meta_rules ADD COLUMN applies_when TEXT",
    "ALTER TABLE meta_rules ADD COLUMN never_when TEXT",
    "ALTER TABLE meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'",
    # Rule provenance index
    "CREATE INDEX IF NOT EXISTS idx_provenance_rule_id ON rule_provenance(rule_id)",
    # Hierarchical rule tree: path column for tree organization
    "ALTER TABLE lesson_transitions ADD COLUMN path TEXT DEFAULT ''",
    # Super-meta-rules table
    "ALTER TABLE super_meta_rules ADD COLUMN applies_when TEXT",
    "ALTER TABLE super_meta_rules ADD COLUMN never_when TEXT",
    "ALTER TABLE super_meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'",
]


def run_migrations(db_path: str | Path) -> int:
    """Apply pending migrations. Returns count applied."""
    if not Path(db_path).exists():
        return 0
    conn = get_connection(db_path)
    applied = 0
    for sql in _BASE_TABLES:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(sql)
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            applied += 1
        except sqlite3.OperationalError:
            pass  # Column/index already exists
    conn.commit()
    conn.close()
    return applied
