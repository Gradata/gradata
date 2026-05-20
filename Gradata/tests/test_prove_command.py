"""Tests for `gradata prove` — statistical evidence the brain is improving."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from gradata.cli import cmd_prove
except ImportError:
    pytest.skip("gradata SDK not importable", allow_module_level=True)


def _seed_brain(brain_dir: Path) -> None:
    """Create the minimal schema cmd_prove needs."""
    brain_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(brain_dir / "system.db")
    con.execute(
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
    con.commit()
    con.close()


def _add_event(brain_dir: Path, *, ts: str, session: int, etype: str, data: dict | None = None):
    con = sqlite3.connect(brain_dir / "system.db")
    con.execute(
        "INSERT INTO events(ts, session, type, source, data_json) VALUES (?,?,?,?,?)",
        (ts, session, etype, "test", json.dumps(data or {})),
    )
    con.commit()
    con.close()


def _run_prove(brain_dir: Path, capsys, window: str = "30d") -> tuple[str, int]:
    args = SimpleNamespace(brain_dir=str(brain_dir), window=window)
    exit_code = 0
    try:
        cmd_prove(args)
    except SystemExit as e:
        exit_code = int(e.code) if isinstance(e.code, int) else 0
    return capsys.readouterr().out, exit_code


def test_prove_no_events_says_nothing_to_prove(tmp_path, capsys):
    _seed_brain(tmp_path / "brain")
    out, exit_code = _run_prove(tmp_path / "brain", capsys)
    assert "nothing to prove yet" in out
    assert exit_code == 0  # no data ≠ failure


def test_prove_converging_trend_exits_zero(tmp_path, capsys):
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    # 5 sessions with decreasing corrections per session (converging)
    base_ts = "2026-05-15T"
    pattern = [(1, 10), (2, 8), (3, 5), (4, 3), (5, 2)]
    for session, n_corr in pattern:
        for j in range(n_corr):
            _add_event(
                brain_dir,
                ts=f"{base_ts}{10 + session:02d}:{j:02d}:00+00:00",
                session=session,
                etype="CORRECTION",
            )
    out, exit_code = _run_prove(brain_dir, capsys)
    assert "Sessions: 5" in out
    assert "CONVERGING" in out
    assert "Trend slope: -" in out  # negative
    assert exit_code == 0


def test_prove_diverging_trend_exits_one(tmp_path, capsys):
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    # 5 sessions with INCREASING corrections per session (diverging — bad)
    base_ts = "2026-05-15T"
    pattern = [(1, 2), (2, 4), (3, 7), (4, 10), (5, 14)]
    for session, n_corr in pattern:
        for j in range(n_corr):
            _add_event(
                brain_dir,
                ts=f"{base_ts}{10 + session:02d}:{j:02d}:00+00:00",
                session=session,
                etype="CORRECTION",
            )
    out, exit_code = _run_prove(brain_dir, capsys)
    assert "DIVERGING" in out
    assert exit_code == 1  # CI failure signal


def test_prove_shows_top_applied_rules(tmp_path, capsys):
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    # Seed corrections so we have some baseline output
    for s in range(3):
        _add_event(
            brain_dir,
            ts=f"2026-05-15T10:0{s}:00+00:00",
            session=s + 1,
            etype="CORRECTION",
        )
    # Seed rule applications
    for _ in range(5):
        _add_event(
            brain_dir,
            ts="2026-05-15T11:00:00+00:00",
            session=1,
            etype="LESSON_APPLIED",
            data={"lesson_description": "Casual tone"},
        )
    for _ in range(3):
        _add_event(
            brain_dir,
            ts="2026-05-15T11:01:00+00:00",
            session=1,
            etype="LESSON_APPLIED",
            data={"lesson_description": "Use type hints"},
        )
    out, _ = _run_prove(brain_dir, capsys)
    assert "most-applied rules" in out
    assert "Casual tone" in out
    assert "Use type hints" in out


def test_prove_warns_when_corrections_but_no_applications(tmp_path, capsys):
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    # 10 corrections, zero applications
    for s in range(10):
        _add_event(
            brain_dir,
            ts=f"2026-05-15T10:{s:02d}:00+00:00",
            session=s + 1,
            etype="CORRECTION",
        )
    out, _ = _run_prove(brain_dir, capsys)
    assert "WARNING" in out
    assert "zero rule applications" in out


def test_prove_window_filter_excludes_old(tmp_path, capsys):
    """Events outside the window should not be counted."""
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    # Old corrections (200 days ago)
    for s in range(5):
        _add_event(
            brain_dir,
            ts=f"2024-01-01T10:0{s}:00+00:00",
            session=s + 1,
            etype="CORRECTION",
        )
    out, _ = _run_prove(brain_dir, capsys, window="7d")
    assert "nothing to prove yet" in out
