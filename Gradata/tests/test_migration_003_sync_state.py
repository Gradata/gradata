"""Migration 003 — sync_state table + per-device watermark columns."""

from __future__ import annotations

import importlib
import sqlite3

from gradata._migrations import _apply_inline, _apply_numbered
from tests.conftest import init_brain


def _conn(brain) -> sqlite3.Connection:
    return sqlite3.connect(str(brain.dir / "system.db"))


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _indexes(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA index_list({table})").fetchall()}


def _apply_all_migrations(brain) -> None:
    with _conn(brain) as conn:
        _apply_inline(conn)
        _apply_numbered(conn, brain.dir)
        conn.commit()


def test_creates_sync_state_if_missing(tmp_path):
    brain = init_brain(tmp_path)
    # init_brain already ran every migration — reset to the pre-003 state:
    # drop the table AND the tracking row so the runner re-applies 003.
    with _conn(brain) as conn:
        conn.execute("DROP TABLE IF EXISTS sync_state")
        conn.execute("DELETE FROM migrations WHERE name = '003_add_sync_state'")
        conn.commit()

    _apply_all_migrations(brain)
    with _conn(brain) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_state'"
        ).fetchone()
    assert row is not None


def test_adds_watermark_columns(tmp_path):
    brain = init_brain(tmp_path)
    _apply_all_migrations(brain)
    with _conn(brain) as conn:
        cols = _cols(conn, "sync_state")
    for required in (
        "brain_id",
        "last_push_at",
        "updated_at",
        "device_id",
        "last_push_event_id",
        "last_pull_cursor",
        "tenant_id",
    ):
        assert required in cols, f"missing column: {required}"


def test_indexes_created(tmp_path):
    brain = init_brain(tmp_path)
    _apply_all_migrations(brain)
    with _conn(brain) as conn:
        idx = _indexes(conn, "sync_state")
    assert "idx_sync_state_device" in idx
    assert "idx_sync_state_tenant_device" in idx


def test_backfills_tenant_id_on_preexisting_rows(tmp_path):
    """A brain that already has rows keyed by brain_id must get tenant_id populated."""
    brain = init_brain(tmp_path)
    # Simulate a pre-Migration-003 brain: create the legacy schema + insert a row.
    with _conn(brain) as conn:
        conn.execute("DROP TABLE IF EXISTS sync_state")
        conn.execute(
            "CREATE TABLE sync_state (brain_id TEXT PRIMARY KEY, last_push_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO sync_state (brain_id, last_push_at, updated_at) "
            "VALUES ('legacy-tenant', '2026-04-20T00:00:00Z', '2026-04-20T00:00:00Z')"
        )
        conn.commit()

    # Force migration 003 to run even if already tracked (clean state).
    with _conn(brain) as conn:
        conn.execute("DELETE FROM migrations WHERE name = '003_add_sync_state'")
        conn.commit()

    _apply_all_migrations(brain)

    with _conn(brain) as conn:
        row = conn.execute(
            "SELECT brain_id, tenant_id FROM sync_state WHERE brain_id = 'legacy-tenant'"
        ).fetchone()
    assert row is not None
    assert row[1] is not None  # tenant_id backfilled


def test_migration_is_idempotent(tmp_path):
    brain = init_brain(tmp_path)
    _apply_all_migrations(brain)
    # Rerun migration 003's up() directly; should be a no-op.
    module = importlib.import_module("gradata._migrations.003_add_sync_state")
    with _conn(brain) as conn:
        s = module.up(conn, tenant_id="tid")
        conn.commit()
    assert s["columns_added"] == []
    assert s["indexes_created"] == []
    assert s["table_created"] is False
