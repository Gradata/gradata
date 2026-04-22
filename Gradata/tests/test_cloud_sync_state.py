"""Watermark persistence for ``/events/pull`` resumption."""

from __future__ import annotations

from gradata import Brain
from gradata.cloud._sync_state import get_pull_cursor, update_pull_cursor


def test_empty_brain_returns_none(tmp_path):
    result = get_pull_cursor(tmp_path / "system.db", tenant_id="tenant-a", device_id="dev_a")
    assert result is None


def test_round_trip(tmp_path):
    brain = Brain(tmp_path)
    # Force system.db into existence via an event emit.
    brain.emit("TEST", "src", {"x": 1}, [])

    db = tmp_path / "system.db"
    assert update_pull_cursor(db, tenant_id="tenant-a", device_id="dev_a", cursor="01JN000000001")
    assert get_pull_cursor(db, tenant_id="tenant-a", device_id="dev_a") == "01JN000000001"


def test_overwrite_advances_cursor(tmp_path):
    brain = Brain(tmp_path)
    brain.emit("TEST", "src", {"x": 1}, [])

    db = tmp_path / "system.db"
    update_pull_cursor(db, tenant_id="t", device_id="dev_a", cursor="01JN01")
    update_pull_cursor(db, tenant_id="t", device_id="dev_a", cursor="01JN02")
    assert get_pull_cursor(db, tenant_id="t", device_id="dev_a") == "01JN02"


def test_empty_cursor_is_noop(tmp_path):
    brain = Brain(tmp_path)
    brain.emit("TEST", "src", {"x": 1}, [])

    db = tmp_path / "system.db"
    # Seed a real cursor first so the no-op assertion actually protects
    # against regressions that clear stored cursors on empty writes.
    assert update_pull_cursor(db, tenant_id="t", device_id="dev_a", cursor="01JN99") is True
    assert get_pull_cursor(db, tenant_id="t", device_id="dev_a") == "01JN99"

    assert update_pull_cursor(db, tenant_id="t", device_id="dev_a", cursor="") is False
    # Empty cursor must leave the previously stored value untouched.
    assert get_pull_cursor(db, tenant_id="t", device_id="dev_a") == "01JN99"
