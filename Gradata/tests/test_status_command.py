"""Tests for `gradata status` — single-page brain/daemon/cloud summary.

The command must:
- Print a brain summary block (rules, lessons, corrections from system.db)
- Probe the daemon at 127.0.0.1:8765 (best-effort, never blocks)
- Probe cloud sync state (best-effort, never blocks)
- Show a 7d convergence trend
- Never crash on a fresh brain, missing daemon, or no cloud key
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

# Skip if running without the SDK importable
try:
    from gradata.cli import cmd_status
except ImportError:  # pragma: no cover
    pytest.skip("gradata SDK not importable", allow_module_level=True)


def _seed_minimal_brain(brain_dir: Path) -> None:
    """Create a brain dir with a system.db that satisfies Brain() open()."""
    brain_dir.mkdir(parents=True, exist_ok=True)
    db_path = brain_dir / "system.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    # Minimal events table matching production schema columns the test uses.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            session INTEGER,
            type TEXT NOT NULL,
            source TEXT,
            data_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payload_json TEXT,
            kind TEXT,
            enqueued_at REAL,
            synced_at REAL,
            attempts INTEGER DEFAULT 0,
            last_error TEXT
        )
        """
    )
    con.commit()
    con.close()


def _run_status(
    brain_dir: Path, capsys, *, mock_daemon_down: bool = True, mock_cloud_down: bool = True
) -> str:
    """Invoke cmd_status with args.brain_dir and return captured stdout.

    By default this mocks BOTH the daemon /health probe and the cloud /brains
    probe as unreachable, so tests run deterministically regardless of whether
    the developer has a live daemon or cloud key on their machine.
    """
    import contextlib
    import urllib.error
    import urllib.request as _ur

    args = SimpleNamespace(brain_dir=str(brain_dir))
    real_urlopen = _ur.urlopen

    def patched_urlopen(req, *a, **kw):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if mock_daemon_down and "127.0.0.1:8765" in url:
            raise urllib.error.URLError("mocked daemon down")
        if mock_cloud_down and "api.gradata.ai" in url:
            raise urllib.error.URLError("mocked cloud down")
        return real_urlopen(req, *a, **kw)

    _ur.urlopen = patched_urlopen
    try:
        with contextlib.suppress(SystemExit):
            cmd_status(args)
    finally:
        _ur.urlopen = real_urlopen
    captured = capsys.readouterr()
    return captured.out


def test_status_runs_on_fresh_brain(tmp_path, capsys, monkeypatch):
    """Fresh brain (no events, no daemon, no cloud key) — command must
    succeed and print something useful, not crash."""
    brain_dir = tmp_path / "brain"
    _seed_minimal_brain(brain_dir)
    # Make sure there's no real cloud key in this test's view
    monkeypatch.setenv("HOME", str(tmp_path))
    out = _run_status(brain_dir, capsys)

    # Brain block
    assert "Brain:" in out
    assert "Rules graduated: 0" in out
    assert "Lessons: 0" in out
    assert "Corrections: 0" in out

    # Daemon section (should be "not running" since we didn't start one)
    assert "Daemon:" in out
    assert "not running" in out

    # Cloud section (should report "not configured" since HOME has no key file)
    assert "Cloud:" in out
    assert "not configured" in out

    # Convergence
    assert "Convergence" in out


def test_status_with_corrections(tmp_path, capsys, monkeypatch):
    """Brain with seeded CORRECTION events — counts must appear in output."""
    brain_dir = tmp_path / "brain"
    _seed_minimal_brain(brain_dir)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Seed 3 CORRECTION events and a LESSON_CHANGE
    con = sqlite3.connect(brain_dir / "system.db")
    cur = con.cursor()
    cur.executemany(
        "INSERT INTO events(ts, session, type, source, data_json) VALUES (?,?,?,?,?)",
        [
            ("2026-05-19T10:00:00+00:00", 1, "CORRECTION", "test", "{}"),
            ("2026-05-19T11:00:00+00:00", 1, "CORRECTION", "test", "{}"),
            ("2026-05-19T12:00:00+00:00", 2, "CORRECTION", "test", "{}"),
            ("2026-05-19T12:00:01+00:00", 2, "LESSON_CHANGE", "test", "{}"),
            ("2026-05-19T13:00:00+00:00", 2, "RULE_GRADUATED", "test", "{}"),
        ],
    )
    con.commit()
    con.close()

    out = _run_status(brain_dir, capsys)
    assert "Corrections: 3" in out
    assert "Lessons: 1" in out
    assert "Rules graduated: 1" in out
    # Last correction timestamp should appear
    assert "Last correction:" in out


def test_status_does_not_crash_on_missing_db(tmp_path, capsys, monkeypatch):
    """If system.db doesn't exist yet (brand-new brain), don't crash."""
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    # Intentionally do NOT create system.db
    monkeypatch.setenv("HOME", str(tmp_path))

    # _get_brain() will likely try to init or open; this test just
    # checks the status path tolerates schema absence. If _get_brain
    # itself crashes, we accept SystemExit but should NOT see a
    # traceback escape.
    try:
        _run_status(brain_dir, capsys)
    except Exception as e:
        pytest.fail(f"cmd_status raised on missing-db brain: {e}")


def test_status_with_sync_queue_drained(tmp_path, capsys, monkeypatch):
    """sync_queue with all rows synced should report 'drained'."""
    brain_dir = tmp_path / "brain"
    _seed_minimal_brain(brain_dir)
    monkeypatch.setenv("HOME", str(tmp_path))

    con = sqlite3.connect(brain_dir / "system.db")
    cur = con.cursor()
    cur.executemany(
        "INSERT INTO sync_queue(payload_json, kind, enqueued_at, synced_at) VALUES (?,?,?,?)",
        [("{}", "correction", 1700000000.0, 1700000010.0)] * 3,
    )
    con.commit()
    con.close()

    out = _run_status(brain_dir, capsys)
    assert "Sync queue: drained (3 synced)" in out


def test_status_with_pending_sync(tmp_path, capsys, monkeypatch):
    """sync_queue with pending rows should report the pending count."""
    brain_dir = tmp_path / "brain"
    _seed_minimal_brain(brain_dir)
    monkeypatch.setenv("HOME", str(tmp_path))

    con = sqlite3.connect(brain_dir / "system.db")
    cur = con.cursor()
    cur.executemany(
        "INSERT INTO sync_queue(payload_json, kind, enqueued_at, synced_at) VALUES (?,?,?,?)",
        [
            ("{}", "correction", 1700000000.0, None),
            ("{}", "correction", 1700000001.0, None),
            ("{}", "correction", 1700000002.0, 1700000010.0),
        ],
    )
    con.commit()
    con.close()

    out = _run_status(brain_dir, capsys)
    assert "Sync queue: 2 pending / 3 total" in out
