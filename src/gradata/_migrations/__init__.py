"""Gradata brain schema migrations.

Two layers, applied in order by ``run_migrations(db_path)``:

1. **Inline base tables + idempotent ALTERs** (``_BASE_TABLES``, ``_MIGRATIONS``).
   Historical approach: suppress OperationalError on each statement. Fast to
   author, no tracking, runs every startup. Kept for backward compatibility
   with older brains.

2. **Numbered tracked migrations** (``NNN_name.py``). Each module exposes
   ``NAME`` and ``up(conn, tenant_id)``. The ``migrations`` table records
   which have been applied. Tenant UUID is resolved from ``<brain>/.tenant_id``
   (created on first run).

``Brain.__init__`` calls ``run_migrations`` on every open, so upgrades
happen transparently.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import sqlite3
from pathlib import Path
from types import ModuleType

from gradata._db import get_connection

from ._runner import ensure_migrations_table, has_applied, mark_applied
from .tenant_uuid import get_or_create_tenant_id

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
    "ALTER TABLE events ADD COLUMN valid_from TEXT",
    "ALTER TABLE events ADD COLUMN valid_until TEXT",
    "ALTER TABLE events ADD COLUMN scope TEXT DEFAULT 'local'",
    "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_events_session_type ON events(session, type)",
    "ALTER TABLE meta_rules ADD COLUMN applies_when TEXT",
    "ALTER TABLE meta_rules ADD COLUMN never_when TEXT",
    "ALTER TABLE meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'",
    "CREATE INDEX IF NOT EXISTS idx_provenance_rule_id ON rule_provenance(rule_id)",
    """CREATE TABLE IF NOT EXISTS rule_relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_a_id TEXT NOT NULL,
        rule_b_id TEXT NOT NULL,
        relationship TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        detected_at TEXT NOT NULL
    )""",
    "ALTER TABLE lesson_transitions ADD COLUMN path TEXT DEFAULT ''",
    "ALTER TABLE super_meta_rules ADD COLUMN applies_when TEXT",
    "ALTER TABLE super_meta_rules ADD COLUMN never_when TEXT",
    "ALTER TABLE super_meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'",
]


def _apply_inline(conn: sqlite3.Connection) -> int:
    applied = 0
    for sql in _BASE_TABLES:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(sql)
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            applied += 1
        except sqlite3.OperationalError:
            pass
    return applied


def _numbered_modules() -> list[tuple[str, ModuleType]]:
    """Discover NNN_*.py modules inside this package, sorted numerically."""
    pkg_dir = Path(__file__).resolve().parent
    mods: list[tuple[str, ModuleType]] = []
    for p in sorted(pkg_dir.glob("[0-9][0-9][0-9]_*.py")):
        module = importlib.import_module(f"gradata._migrations.{p.stem}")
        mods.append((p.stem, module))
    return mods


def _apply_numbered(conn: sqlite3.Connection, brain_dir: Path) -> int:
    ensure_migrations_table(conn)
    applied = 0
    tenant_id: str | None = None
    for name, module in _numbered_modules():
        mig_name = getattr(module, "NAME", name)
        if has_applied(conn, mig_name):
            continue
        if tenant_id is None:
            tenant_id = get_or_create_tenant_id(brain_dir)
        up = getattr(module, "up", None)
        if up is None:
            continue
        summary = up(conn, tenant_id) or {}
        rows = int(summary.get("rows_backfilled", 0))
        notes = json.dumps({k: v for k, v in summary.items() if k != "rows_backfilled"})
        mark_applied(conn, mig_name, rows_affected=rows, notes=notes)
        applied += 1
    return applied


def run_migrations(db_path: str | Path) -> int:
    """Apply pending migrations. Returns count applied (inline + numbered)."""
    db_path = Path(db_path)
    if not db_path.exists():
        return 0
    conn = get_connection(db_path)
    try:
        applied = _apply_inline(conn)
        applied += _apply_numbered(conn, db_path.parent)
        conn.commit()
    finally:
        conn.close()
    return applied


__all__ = ["run_migrations"]
