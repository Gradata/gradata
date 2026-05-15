"""Unit tests for sync_queue primitives (#194, day 1).

Covers schema creation via the brain migration module plus CRUD over the
``sync_queue`` table through :mod:`gradata._sync_queue`.
"""

from __future__ import annotations

import sqlite3
import time

import pytest

from gradata import _sync_queue
from gradata._migrations import _BASE_TABLES, _MIGRATIONS


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the sync_queue schema applied.

    Pulls the canonical DDL straight from ``gradata._migrations`` so we
    are testing the same schema a real brain would get.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for sql in _BASE_TABLES:
        if "sync_queue" in sql:
            conn.execute(sql)
    for sql in _MIGRATIONS:
        if "sync_queue" in sql:
            conn.execute(sql)
    conn.commit()
    return conn


def test_sync_queue_enqueue_returns_int_and_peek_finds_row():
    conn = _make_conn()
    payload = {"draft": "hello", "final": "Hello.", "meta": {"n": 1}}

    row_id = _sync_queue.enqueue(conn, "correction", payload)

    assert isinstance(row_id, int)
    assert row_id > 0

    pending = _sync_queue.peek_pending(conn)
    assert len(pending) == 1
    row = pending[0]
    assert row["id"] == row_id
    assert row["kind"] == "correction"
    # Payload roundtrips exactly through json.dumps/loads.
    assert row["payload"] == payload
    assert row["attempts"] == 0
    assert isinstance(row["enqueued_at"], float)


def test_sync_queue_peek_pending_respects_limit_and_fifo_order():
    conn = _make_conn()
    ids = [_sync_queue.enqueue(conn, "event", {"i": i}) for i in range(5)]

    pending = _sync_queue.peek_pending(conn, limit=3)
    assert [r["id"] for r in pending] == ids[:3]


def test_sync_queue_mark_synced_removes_from_peek_pending():
    conn = _make_conn()
    id_a = _sync_queue.enqueue(conn, "correction", {"x": 1})
    id_b = _sync_queue.enqueue(conn, "lesson", {"x": 2})

    _sync_queue.mark_synced(conn, [id_a])

    pending_ids = [r["id"] for r in _sync_queue.peek_pending(conn)]
    assert id_a not in pending_ids
    assert id_b in pending_ids

    # synced_at should be a float timestamp on row A.
    row = conn.execute(
        "SELECT synced_at FROM sync_queue WHERE id = ?", (id_a,)
    ).fetchone()
    assert row["synced_at"] is not None
    assert float(row["synced_at"]) <= time.time() + 1.0


def test_sync_queue_mark_failed_increments_attempts_and_keeps_row_pending():
    conn = _make_conn()
    row_id = _sync_queue.enqueue(conn, "event", {"k": "v"})

    _sync_queue.mark_failed(conn, [row_id], "boom: network unreachable")
    _sync_queue.mark_failed(conn, [row_id], "boom again")

    pending = _sync_queue.peek_pending(conn)
    assert len(pending) == 1
    assert pending[0]["id"] == row_id
    assert pending[0]["attempts"] == 2

    row = conn.execute(
        "SELECT last_error, synced_at FROM sync_queue WHERE id = ?", (row_id,)
    ).fetchone()
    assert row["last_error"] == "boom again"
    assert row["synced_at"] is None


def test_sync_queue_mark_failed_truncates_long_error_to_500_chars():
    conn = _make_conn()
    row_id = _sync_queue.enqueue(conn, "event", {})
    long_err = "x" * 5000

    _sync_queue.mark_failed(conn, [row_id], long_err)

    row = conn.execute(
        "SELECT last_error FROM sync_queue WHERE id = ?", (row_id,)
    ).fetchone()
    assert len(row["last_error"]) == 500
    assert row["last_error"] == "x" * 500


def test_sync_queue_kind_constraint_rejects_invalid_value():
    conn = _make_conn()
    with pytest.raises(sqlite3.IntegrityError):
        _sync_queue.enqueue(conn, "foo", {"bad": True})


def test_sync_queue_empty_id_lists_are_noops():
    conn = _make_conn()
    # Should not raise, should not touch the DB.
    _sync_queue.mark_synced(conn, [])
    _sync_queue.mark_failed(conn, [], "nope")

    pending = _sync_queue.peek_pending(conn)
    assert pending == []
