"""Migration 002 — event_id / device_id / content_hash columns + backfill.

Covers the chunked backfill path: seeds events, invokes the migration
module directly (same entry the runner uses), then asserts schema shape
and backfill contents.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sqlite3

from gradata._migrations import _apply_inline, _apply_numbered
from gradata._migrations.device_uuid import get_or_create_device_id
from tests.conftest import init_brain


def _conn(brain) -> sqlite3.Connection:
    return sqlite3.connect(str(brain.dir / "system.db"))


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _indexes(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA index_list({table})").fetchall()}


def _run_002(brain) -> dict:
    """Invoke Migration 002's up() against the brain's DB, like the runner does."""
    module = importlib.import_module("gradata._migrations.002_add_event_identity")
    with _conn(brain) as conn:
        # Migration 001 must land first so the migrations table exists etc.
        _apply_inline(conn)
        _apply_numbered(conn, brain.dir)
        summary = module.up(conn, tenant_id="unused")
        conn.commit()
        return summary


def _null_identity_columns(brain) -> None:
    """Simulate pre-Migration-002 rows: wipe the identity columns.

    Fresh ``emit()`` now populates event_id/device_id/content_hash directly,
    so to exercise the backfill path we need to undo that on seeded rows.
    """
    with _conn(brain) as conn:
        conn.execute("UPDATE events SET event_id = NULL, device_id = NULL, content_hash = NULL")
        conn.commit()


def test_columns_added(tmp_path):
    brain = init_brain(tmp_path)
    _run_002(brain)
    with _conn(brain) as conn:
        cols = _cols(conn, "events")
    for required in (
        "event_id",
        "device_id",
        "content_hash",
        "correction_chain_id",
        "origin_agent",
    ):
        assert required in cols, f"missing column: {required}"


def test_indexes_created(tmp_path):
    brain = init_brain(tmp_path)
    _run_002(brain)
    with _conn(brain) as conn:
        idx = _indexes(conn, "events")
    assert "idx_events_event_id" in idx
    assert "idx_events_device_id" in idx
    assert "idx_events_content_hash" in idx


def test_historical_rows_backfilled(tmp_path):
    brain = init_brain(tmp_path)
    # Seed then NULL out the identity columns to simulate a pre-002 row.
    brain.emit(
        event_type="TEST_HISTORICAL",
        source="test",
        data={"kind": "seed", "n": 1},
        tags=["pre-migration"],
    )
    _null_identity_columns(brain)
    _run_002(brain)

    with _conn(brain) as conn:
        row = conn.execute(
            "SELECT event_id, device_id, content_hash, ts, type, source, data_json "
            "FROM events WHERE type = 'TEST_HISTORICAL'"
        ).fetchone()

    event_id, device_id, content_hash, ts, ev_type, source, data_json = row
    # event_id: 26-char Crockford base32 ULID
    assert event_id is not None
    assert re.fullmatch(r"[0-9A-HJKMNP-TV-Z]{26}", event_id), event_id
    # device_id: dev_<32 hex>, matches the brain's .device_id file
    expected_device = get_or_create_device_id(brain.dir)
    assert device_id == expected_device
    assert re.fullmatch(r"dev_[0-9a-f]{32}", device_id)
    # content_hash: canonical JSON of {type, source, data}
    data = json.loads(data_json)
    canonical = json.dumps(
        {"type": ev_type, "source": source, "data": data},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert content_hash == expected_hash


def test_migration_is_idempotent(tmp_path):
    brain = init_brain(tmp_path)
    brain.emit("A", "t", {"n": 1}, [])
    _null_identity_columns(brain)
    s1 = _run_002(brain)
    s2 = _run_002(brain)
    # First run backfills the row, second is a no-op (no NULL event_ids left).
    assert s1["rows_backfilled"] >= 1
    assert s2["rows_backfilled"] == 0
    assert s2["columns_added"] == []  # columns already exist


def test_chunked_backfill_covers_all_rows(tmp_path):
    brain = init_brain(tmp_path)
    # Seed enough rows that the chunk loop iterates more than once.
    # CHUNK_SIZE = 10_000 — use a smaller patch so the test stays fast.
    module = importlib.import_module("gradata._migrations.002_add_event_identity")
    original_chunk = module.CHUNK_SIZE
    module.CHUNK_SIZE = 7
    try:
        for i in range(20):
            brain.emit("BULK", "t", {"i": i}, [])
        _null_identity_columns(brain)
        s = _run_002(brain)
    finally:
        module.CHUNK_SIZE = original_chunk

    assert s["chunks_committed"] >= 3, s  # 20 rows / 7 per chunk = 3 chunks
    with _conn(brain) as conn:
        null_count = conn.execute("SELECT COUNT(*) FROM events WHERE event_id IS NULL").fetchone()[
            0
        ]
    assert null_count == 0


def test_content_hash_canonicalises_key_order(tmp_path):
    """Two events that differ only in dict key order must hash identically."""
    module = importlib.import_module("gradata._migrations.002_add_event_identity")
    h1 = module._canonical_content_hash("T", "src", json.dumps({"a": 1, "b": 2}))
    h2 = module._canonical_content_hash("T", "src", json.dumps({"b": 2, "a": 1}))
    assert h1 == h2


def test_device_id_persisted_to_brain_dir(tmp_path):
    brain = init_brain(tmp_path)
    _run_002(brain)
    device_file = brain.dir / ".device_id"
    assert device_file.exists()
    content = device_file.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"dev_[0-9a-f]{32}", content)


def test_new_emit_leaves_identity_columns_null_for_now(tmp_path):
    """emit() does not yet populate identity columns — only Migration 002 backfill does.

    Wiring emit() to write event_id/device_id/content_hash is deferred; this
    test pins the current contract so a future change flips it deliberately.
    """
    brain = init_brain(tmp_path)
    brain.emit("FRESH", "src", {"k": "v"}, [])

    with _conn(brain) as conn:
        row = conn.execute(
            "SELECT event_id, device_id, content_hash FROM events WHERE type = 'FRESH'"
        ).fetchone()
    assert row == (None, None, None)
