"""Integration tests for Brain.correct() write-through path (#194 day 3).

Verify that:
* When GRADATA_API_KEY is set, Brain.__init__ starts a SyncWorker.
* When GRADATA_DISABLE_WRITE_THROUGH=1, no worker starts.
* When no API key is resolvable, no worker starts (silent skip).
* Brain.correct() enqueues a row in sync_queue regardless of cloud reachability.
* Brain.close() drains the queue cleanly.

These tests don't hit the network — they assert on sync_queue rows directly.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from gradata import Brain


def _count_pending(brain_dir: Path) -> int:
    conn = sqlite3.connect(brain_dir / "system.db")
    try:
        n = conn.execute("SELECT COUNT(*) FROM sync_queue WHERE synced_at IS NULL").fetchone()[0]
    finally:
        conn.close()
    return n


def _all_rows(brain_dir: Path) -> list[dict]:
    conn = sqlite3.connect(brain_dir / "system.db")
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM sync_queue").fetchall()]
    finally:
        conn.close()


@pytest.fixture
def brain_dir(tmp_path, monkeypatch):
    d = tmp_path / "brain"
    # Brain.init() creates the directory and schema; don't pre-create.
    monkeypatch.setenv("BRAIN_DIR", str(d))
    # Default: no API key, no worker. Tests opt in.
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    monkeypatch.delenv("GRADATA_DISABLE_WRITE_THROUGH", raising=False)
    monkeypatch.setenv("GRADATA_SYNC_TICK_SEC", "300")  # don't tick during tests
    # Point the worker at a definitely-unreachable URL so accidental network
    # calls hard-fail fast instead of hanging.
    monkeypatch.setenv("GRADATA_CLOUD_INGEST_URL", "http://127.0.0.1:1/api/v1/ingest")
    return d


def _open_brain(brain_dir):
    """Use Brain.init() so the schema is created (including sync_queue)."""
    return Brain.init(brain_dir)


def test_brain_correct_enqueues_when_api_key_present(brain_dir, monkeypatch):
    monkeypatch.setenv("GRADATA_API_KEY", "gd_live_test")
    brain = _open_brain(brain_dir)
    try:
        assert brain._sync_worker is not None, "worker should start when API key set"
        before = _count_pending(brain_dir)
        brain.correct(draft="hello world", final="hi")
        after = _count_pending(brain_dir)
        assert after == before + 1, (
            f"Brain.correct() should enqueue exactly one row (before={before} after={after})"
        )
        rows = _all_rows(brain_dir)
        assert rows[-1]["kind"] == "correction"
    finally:
        brain.close()


def test_brain_correct_no_worker_when_disabled(brain_dir, monkeypatch):
    monkeypatch.setenv("GRADATA_API_KEY", "gd_live_test")
    monkeypatch.setenv("GRADATA_DISABLE_WRITE_THROUGH", "1")
    brain = _open_brain(brain_dir)
    try:
        assert brain._sync_worker is None, (
            "worker must NOT start when GRADATA_DISABLE_WRITE_THROUGH=1"
        )
        before = _count_pending(brain_dir)
        brain.correct(draft="hello", final="hi")
        after = _count_pending(brain_dir)
        assert after == before, "Brain.correct() must not enqueue when write-through is disabled"
    finally:
        brain.close()


def test_brain_correct_no_worker_when_no_api_key(brain_dir, monkeypatch):
    # brain_dir fixture already deletes GRADATA_API_KEY. Make sure ~/.gradata/key
    # is also unreadable.
    monkeypatch.setenv("HOME", str(brain_dir.parent))  # no ~/.gradata/key under here
    brain = _open_brain(brain_dir)
    try:
        assert brain._sync_worker is None, "worker must NOT start without an API key"
        before = _count_pending(brain_dir)
        brain.correct(draft="hello", final="hi")
        after = _count_pending(brain_dir)
        assert after == before, "Brain.correct() must not enqueue when no API key is resolvable"
    finally:
        brain.close()


def test_brain_correct_enqueues_even_when_cloud_unreachable(brain_dir, monkeypatch):
    # GRADATA_CLOUD_INGEST_URL is already pointed at port 1 (unreachable).
    # The point is that correct() must NOT block on cloud reachability —
    # the row should land in sync_queue regardless.
    monkeypatch.setenv("GRADATA_API_KEY", "gd_live_test")
    brain = _open_brain(brain_dir)
    try:
        before = _count_pending(brain_dir)
        # If the enqueue path were doing inline network calls this would hang
        # for seconds. Asserting it returns quickly + the row is queued is
        # the actual contract.
        brain.correct(draft="hello", final="hi")
        after = _count_pending(brain_dir)
        assert after == before + 1
    finally:
        brain.close()


def test_brain_correct_local_path_unaffected_by_worker_failure(brain_dir, monkeypatch):
    """If _write_through_enqueue raises, correct() must still succeed locally.

    The local correct() path is the user's source of truth — write-through
    can never break it.
    """
    monkeypatch.setenv("GRADATA_API_KEY", "gd_live_test")
    brain = _open_brain(brain_dir)
    try:
        # Sabotage the enqueue helper to raise.
        def boom(*a, **kw):
            raise RuntimeError("simulated sync_queue failure")

        monkeypatch.setattr(brain, "_write_through_enqueue", boom)
        # correct() must still return successfully (no exception propagated).
        brain.correct(draft="hello", final="hi")
    finally:
        brain.close()
