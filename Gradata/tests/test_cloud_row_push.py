"""Tests for gradata._cloud_sync — per-tenant row push MVP."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata import _cloud_sync


@pytest.fixture
def brain(tmp_path: Path, monkeypatch) -> Path:
    """Minimal brain dir with tenant_id and a seeded events table."""
    monkeypatch.delenv(_cloud_sync.ENV_ENABLED, raising=False)
    monkeypatch.delenv(_cloud_sync.ENV_URL, raising=False)
    monkeypatch.delenv(_cloud_sync.ENV_KEY, raising=False)
    (tmp_path / ".tenant_id").write_text(
        "11111111-2222-3333-4444-555555555555", encoding="utf-8"
    )
    conn = sqlite3.connect(tmp_path / "system.db")
    conn.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, ts TEXT, type TEXT, "
        "tenant_id TEXT)"
    )
    conn.execute(
        "INSERT INTO events (ts, type, tenant_id) VALUES (?, ?, ?)",
        ("2026-04-17T00:00:00Z", "correction", "11111111-2222-3333-4444-555555555555"),
    )
    conn.execute(
        "INSERT INTO events (ts, type, tenant_id) VALUES (?, ?, ?)",
        ("2026-04-17T00:00:00Z", "other", "other-tenant"),
    )
    conn.execute(
        "CREATE TABLE sync_state (brain_id TEXT PRIMARY KEY, last_push_at TEXT, "
        "updated_at TEXT)"
    )
    conn.commit()
    conn.close()
    return tmp_path


def test_disabled_by_default(brain: Path):
    assert _cloud_sync.enabled() is False
    assert _cloud_sync.push(brain) == {}


def test_disabled_without_credentials(brain: Path, monkeypatch):  # noqa: ARG001
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    # missing URL/KEY -> still disabled
    assert _cloud_sync.enabled() is False


def test_push_filters_by_tenant(brain: Path, monkeypatch):
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    captured: list[tuple[str, list]] = []

    def fake_post(table, rows):
        captured.append((table, rows))
        return len(rows)

    with patch.object(_cloud_sync, "_post", side_effect=fake_post):
        result = _cloud_sync.push(brain)

    events_rows = next((r for t, r in captured if t == "events"), [])
    # Only our tenant's row goes up; "other-tenant" row is filtered.
    assert len(events_rows) == 1
    assert events_rows[0]["tenant_id"] == "11111111-2222-3333-4444-555555555555"
    assert result.get("events") == 1


def test_push_updates_sync_state(brain: Path, monkeypatch):
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    with patch.object(_cloud_sync, "_post", return_value=1):
        _cloud_sync.push(brain)

    conn = sqlite3.connect(brain / "system.db")
    row = conn.execute(
        "SELECT last_push_at FROM sync_state WHERE brain_id = ?",
        ("11111111-2222-3333-4444-555555555555",),
    ).fetchone()
    conn.close()
    assert row and row[0]  # timestamp was recorded


def test_push_is_noop_when_no_db(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")
    # No system.db in tmp_path
    assert _cloud_sync.push(tmp_path) == {}


def test_skips_tables_without_tenant_id_column(brain: Path, monkeypatch):
    """Tables that haven't been migrated yet should be skipped silently."""
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    # No lessons table at all -> PRAGMA returns empty -> skip
    with patch.object(_cloud_sync, "_post", return_value=0) as mp:
        _cloud_sync.push(brain)

    called_tables = [c.args[0] for c in mp.call_args_list]
    assert "lessons" not in called_tables
