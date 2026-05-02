"""PR2 spec: dual-write atomicity. Both-or-neither under kill-9 mid-write.

These tests are PATH-AGNOSTIC — they import the public API (Brain) only, not
internal _events.py paths, so they survive a rebase that moves files around.

Invariant under test:
  Every event written via Brain MUST land in BOTH events.jsonl AND system.db,
  OR in NEITHER. A crash mid-write must leave the brain in a recoverable state
  where `gradata doctor --reconcile` (or Brain re-init) brings them back into
  agreement without data loss.

Acceptance:
  test_dualwrite_jsonl_first_then_sqlite — happy path, both written, ordered
  test_dualwrite_kill9_after_jsonl_before_sqlite — JSONL has event, SQLite missing → reconcile replays
  test_dualwrite_kill9_after_sqlite_before_jsonl — should not happen (JSONL is source of truth)
  test_reconcile_idempotent — running reconcile twice = same state
  test_reconcile_detects_split_brain — doctor --reconcile reports drift count
  test_concurrent_writers_serialize — two writers don't interleave events

Fixtures use tmp_path BRAIN_DIR per test (conftest.py already does this).
No new deps. Prefer SQLite WAL + JSONL append-fsync ordering. CAS via
schema_version sentinel acceptable. Two-phase commit NOT required.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.dualwrite


# ---------------------------------------------------------------------------
# Helpers — kill-9 simulation via subprocess so we can pull the plug mid-write
# ---------------------------------------------------------------------------

def _spawn_writer(brain_dir: Path, n_events: int, kill_after: int | None = None) -> int:
    """Spawn a child process that writes n_events to a fresh Brain.

    If kill_after is set, the child is SIGKILLed after writing that many events
    (event count detected by line count of events.jsonl). Returns child pid.
    """
    code = f"""
import os, sys, time
os.environ['BRAIN_DIR'] = {str(brain_dir)!r}
os.environ['GRADATA_DUALWRITE_JSONL_FSYNC_DELAY_MS'] = '50'
from gradata import Brain
b = Brain()
for i in range({n_events}):
    b.observe(f'lesson-{{i}}', kind='correction')
    time.sleep(0.01)
"""
    p = subprocess.Popen([sys.executable, '-c', code])
    if kill_after is not None:
        jsonl = brain_dir / 'events.jsonl'
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if jsonl.exists() and sum(1 for _ in jsonl.open()) >= kill_after:
                os.kill(p.pid, signal.SIGKILL)
                break
            time.sleep(0.01)
    p.wait()
    return p.returncode


def _count_jsonl(brain_dir: Path) -> int:
    p = brain_dir / 'events.jsonl'
    return sum(1 for _ in p.open()) if p.exists() else 0


def _count_sqlite_events(brain_dir: Path) -> int:
    """Count rows in the events table of system.db. Tolerant to schema drift."""
    import sqlite3
    db = brain_dir / 'system.db'
    if not db.exists():
        return 0
    conn = sqlite3.connect(str(db))
    try:
        for table in ('events', 'event_log', 'lessons'):
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
                return cur.fetchone()[0]
            except sqlite3.OperationalError:
                continue
        return 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dualwrite_jsonl_first_then_sqlite(tmp_path, monkeypatch):
    """Happy path. Both stores agree after a normal write batch."""
    monkeypatch.setenv('BRAIN_DIR', str(tmp_path))
    from gradata import Brain
    b = Brain()
    for i in range(10):
        b.observe(f'lesson-{i}', kind='correction')
    assert _count_jsonl(tmp_path) == _count_sqlite_events(tmp_path) == 10


def test_dualwrite_kill9_mid_batch_leaves_jsonl_canonical(tmp_path):
    """Crash mid-batch. JSONL must be ahead of (or equal to) SQLite, never behind."""
    _spawn_writer(tmp_path, n_events=20, kill_after=5)
    j = _count_jsonl(tmp_path)
    s = _count_sqlite_events(tmp_path)
    assert j >= s, f"JSONL ({j}) must not be behind SQLite ({s}) — JSONL is source of truth"
    assert j > 0, "kill-9 fired before any write reached disk — flaky fixture"


def test_reconcile_replays_missing_sqlite_rows(tmp_path):
    """After kill-9 + reopen, Brain.__init__ (or doctor --reconcile) must replay JSONL → SQLite."""
    _spawn_writer(tmp_path, n_events=20, kill_after=5)
    j_before = _count_jsonl(tmp_path)
    s_before = _count_sqlite_events(tmp_path)
    if j_before == s_before:
        pytest.skip("no drift to reconcile — try a more aggressive kill-after")

    # Trigger reconcile — either via Brain.__init__ auto-replay or doctor CLI
    os.environ['BRAIN_DIR'] = str(tmp_path)
    from gradata import Brain
    Brain()  # should auto-replay on init

    assert _count_sqlite_events(tmp_path) == j_before, "reconcile failed to replay JSONL into SQLite"


def test_reconcile_idempotent(tmp_path, monkeypatch):
    """Running reconcile twice produces the same state."""
    monkeypatch.setenv('BRAIN_DIR', str(tmp_path))
    from gradata import Brain
    b = Brain()
    for i in range(5):
        b.observe(f'lesson-{i}', kind='correction')
    snapshot1 = (_count_jsonl(tmp_path), _count_sqlite_events(tmp_path))
    Brain()  # reopen → reconcile pass
    snapshot2 = (_count_jsonl(tmp_path), _count_sqlite_events(tmp_path))
    Brain()  # again
    snapshot3 = (_count_jsonl(tmp_path), _count_sqlite_events(tmp_path))
    assert snapshot1 == snapshot2 == snapshot3


def test_doctor_reconcile_reports_drift(tmp_path):
    """gradata doctor --reconcile must report the drift count it healed."""
    _spawn_writer(tmp_path, n_events=20, kill_after=5)
    j_before = _count_jsonl(tmp_path)
    s_before = _count_sqlite_events(tmp_path)
    drift = j_before - s_before
    if drift <= 0:
        pytest.skip("no drift — fixture didn't crash mid-write")

    env = {**os.environ, 'BRAIN_DIR': str(tmp_path)}
    r = subprocess.run(
        [sys.executable, '-m', 'gradata.cli', 'doctor', '--reconcile'],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert r.returncode == 0, f"doctor --reconcile failed: {r.stderr}"
    assert 'reconcil' in (r.stdout + r.stderr).lower()
    assert _count_sqlite_events(tmp_path) == j_before


def test_concurrent_writers_serialize(tmp_path):
    """Two writers should not produce interleaved partial events in JSONL."""
    p1 = subprocess.Popen([sys.executable, '-c', f"""
import os; os.environ['BRAIN_DIR'] = {str(tmp_path)!r}
from gradata import Brain
b = Brain()
for i in range(20): b.observe(f'A-{{i}}', kind='correction')
"""])
    p2 = subprocess.Popen([sys.executable, '-c', f"""
import os; os.environ['BRAIN_DIR'] = {str(tmp_path)!r}
from gradata import Brain
b = Brain()
for i in range(20): b.observe(f'B-{{i}}', kind='correction')
"""])
    p1.wait()
    p2.wait()

    # Every line in events.jsonl must be a complete JSON object
    jsonl = tmp_path / 'events.jsonl'
    with jsonl.open() as f:
        for ln, line in enumerate(f, 1):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"corrupted line {ln}: {e}")

    assert _count_jsonl(tmp_path) == _count_sqlite_events(tmp_path), \
        "concurrent writers desynced jsonl/sqlite"
