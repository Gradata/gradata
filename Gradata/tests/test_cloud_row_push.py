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
    (tmp_path / ".tenant_id").write_text("11111111-2222-3333-4444-555555555555", encoding="utf-8")
    conn = sqlite3.connect(tmp_path / "system.db")
    conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, ts TEXT, type TEXT, tenant_id TEXT)")
    conn.execute(
        "INSERT INTO events (ts, type, tenant_id) VALUES (?, ?, ?)",
        ("2026-04-17T00:00:00Z", "correction", "11111111-2222-3333-4444-555555555555"),
    )
    conn.execute(
        "INSERT INTO events (ts, type, tenant_id) VALUES (?, ?, ?)",
        ("2026-04-17T00:00:00Z", "other", "other-tenant"),
    )
    conn.execute(
        "CREATE TABLE sync_state (brain_id TEXT PRIMARY KEY, last_push_at TEXT, updated_at TEXT)"
    )
    conn.commit()
    conn.close()
    return tmp_path


def test_disabled_by_default(brain: Path):
    assert _cloud_sync.enabled() is False
    assert _cloud_sync.push(brain) == {}


def test_disabled_without_credentials(brain: Path, monkeypatch):
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
        return len(rows), None

    with patch.object(_cloud_sync, "_post", side_effect=fake_post):
        result = _cloud_sync.push(brain)

    events_rows = next((r for t, r in captured if t == "events"), [])
    # Only our tenant's row goes up; "other-tenant" row is filtered.
    assert len(events_rows) == 1
    assert events_rows[0]["brain_id"] == "11111111-2222-3333-4444-555555555555"
    assert result.get("events") == 1


def test_push_updates_sync_state(brain: Path, monkeypatch):
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    with patch.object(_cloud_sync, "_post", return_value=(1, None)):
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
    with patch.object(_cloud_sync, "_post", return_value=(0, None)) as mp:
        _cloud_sync.push(brain)

    called_tables = [c.args[0] for c in mp.call_args_list]
    assert "lessons" not in called_tables


def test_push_records_constraint_error(brain: Path, monkeypatch):
    """A 23505 constraint violation must leave a cloud_push_error.json for doctor."""
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    err = {
        "code": 409,
        "message": '{"code":"23505","message":"duplicate key"}',
        "constraint_violation": True,
    }
    with patch.object(_cloud_sync, "_post", return_value=(0, err)):
        _cloud_sync.push(brain)

    error_file = brain / "cloud_push_error.json"
    assert error_file.exists(), "expected cloud_push_error.json to be written"
    import json as _json

    payload = _json.loads(error_file.read_text())
    assert payload["constraint_violation"] is True
    assert payload["code"] == 409
    assert payload["table"] == "events"
    assert "recorded_at" in payload


def test_push_clears_error_on_success(brain: Path, monkeypatch):
    """A successful full push must remove any stale cloud_push_error.json."""
    monkeypatch.setenv(_cloud_sync.ENV_ENABLED, "1")
    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    stale = brain / "cloud_push_error.json"
    stale.write_text('{"code":409,"constraint_violation":true}', encoding="utf-8")

    with patch.object(_cloud_sync, "_post", return_value=(1, None)):
        _cloud_sync.push(brain)

    assert not stale.exists(), "successful push should clear prior error file"


def test_post_constraint_violation_logs_error(caplog, monkeypatch):
    """HTTP 409 / Postgres 23505 must log at ERROR, not WARNING."""
    import io
    import logging
    import urllib.error

    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    err = urllib.error.HTTPError(
        url="https://example.supabase.co/rest/v1/events",
        code=409,
        msg="Conflict",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"code":"23505","message":"duplicate key value"}'),
    )
    with patch.object(_cloud_sync.urllib.request, "urlopen", side_effect=err):
        caplog.set_level(logging.ERROR, logger="gradata.cloud_sync")
        accepted, error = _cloud_sync._post(
            "events", [{"id": 1, "brain_id": "t", "ts": "2026-04-24T00:00:00Z"}]
        )

    assert accepted == 0
    assert error is not None
    assert error["constraint_violation"] is True
    assert error["code"] == 409
    assert any(
        "constraint violation" in r.message and r.levelno == logging.ERROR for r in caplog.records
    ), (
        f"expected ERROR-level constraint log; saw: {[(r.levelno, r.message) for r in caplog.records]}"
    )


def test_post_error_body_scrubs_row_values(monkeypatch):
    """PostgREST 23505 `details`/`hint` echo conflicting row values. Those must
    never land in the persisted error message because `gradata doctor` prints
    the file verbatim."""
    import io
    import urllib.error

    monkeypatch.setenv(_cloud_sync.ENV_URL, "https://example.supabase.co")
    monkeypatch.setenv(_cloud_sync.ENV_KEY, "fake-key")

    secret_detail = "Key (id)=(super-secret-tenant-uuid-abc123) already exists."
    body = (
        b'{"code":"23505","message":"duplicate key value violates unique constraint '
        b'\\"events_brain_type_created_at_unique\\"","details":"'
        + secret_detail.encode()
        + b'","hint":"row data: data_json=leaked-conversation"}'
    )
    err = urllib.error.HTTPError(
        url="https://example.supabase.co/rest/v1/events",
        code=409,
        msg="Conflict",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(body),
    )
    with patch.object(_cloud_sync.urllib.request, "urlopen", side_effect=err):
        _accepted, error = _cloud_sync._post(
            "events", [{"id": 1, "brain_id": "t", "ts": "2026-04-24T00:00:00Z"}]
        )

    assert error is not None
    persisted = error["message"]
    # Safe fields retained.
    assert "23505" in persisted
    assert "events_brain_type_created_at_unique" in persisted
    # Row values (details, hint) stripped.
    assert "super-secret-tenant-uuid-abc123" not in persisted
    assert "leaked-conversation" not in persisted
    assert "data_json" not in persisted


def test_scrub_error_body_handles_non_json():
    """A non-JSON body (e.g. HTML 502 page) must not crash and must not leak."""
    scrubbed = _cloud_sync._scrub_error_body("<html>error</html>")
    assert "non-json" in scrubbed
    assert "<html>" not in scrubbed
