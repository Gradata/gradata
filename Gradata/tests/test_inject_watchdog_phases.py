"""Tests for inject_brain_rules two-phase watchdog injection.

Phase 1 (pre-/clear): pending_handoff.txt → alert + stage post_clear_handoff.txt
Phase 2 (post-/clear): post_clear_handoff.txt → inject handoff into fresh session
"""

from __future__ import annotations

from pathlib import Path

from gradata.hooks import inject_brain_rules as ibr


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_pending(brain_dir: Path, content: str = "## Handoff\nDo the thing.") -> Path:
    sessions = brain_dir / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    hf = sessions / "handoff-test.md"
    hf.write_text(content, encoding="utf-8")
    state = brain_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "pending_handoff.txt").write_text(str(hf), encoding="utf-8")
    return hf


def _write_post_clear(brain_dir: Path, content: str = "## Resumed\nCarry on.") -> None:
    state = brain_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "post_clear_handoff.txt").write_text(content, encoding="utf-8")


# ── Phase 1 tests ─────────────────────────────────────────────────────────────


def test_phase1_alert_injected(tmp_path):
    brain_dir = tmp_path / "brain"
    hf = _write_pending(brain_dir)

    result = ibr._build_watchdog_block(str(brain_dir))

    assert "<watchdog-alert>" in result
    assert str(hf) in result
    assert "Run /clear" in result


def test_phase1_stages_post_clear_file(tmp_path):
    brain_dir = tmp_path / "brain"
    _write_pending(brain_dir, "phase1 content")

    ibr._build_watchdog_block(str(brain_dir))

    post_clear = brain_dir / "state" / "post_clear_handoff.txt"
    assert post_clear.is_file()
    assert "phase1 content" in post_clear.read_text(encoding="utf-8")


def test_phase1_consumes_pending_handoff(tmp_path):
    brain_dir = tmp_path / "brain"
    _write_pending(brain_dir)

    ibr._build_watchdog_block(str(brain_dir))

    assert not (brain_dir / "state" / "pending_handoff.txt").exists()


# ── Phase 2 tests ─────────────────────────────────────────────────────────────


def test_phase2_handoff_injected(tmp_path):
    brain_dir = tmp_path / "brain"
    _write_post_clear(brain_dir, "## Resumed handoff\nNext: fix the thing.")

    result = ibr._build_watchdog_block(str(brain_dir))

    assert "<session-handoff>" in result
    assert "fix the thing" in result


def test_phase2_consumes_post_clear_file(tmp_path):
    brain_dir = tmp_path / "brain"
    _write_post_clear(brain_dir)

    ibr._build_watchdog_block(str(brain_dir))

    assert not (brain_dir / "state" / "post_clear_handoff.txt").exists()


def test_phase2_takes_priority_over_phase1(tmp_path):
    """If both files exist (edge case), post_clear wins — we're already past /clear."""
    brain_dir = tmp_path / "brain"
    _write_pending(brain_dir, "phase1 content")
    _write_post_clear(brain_dir, "phase2 content")

    result = ibr._build_watchdog_block(str(brain_dir))

    assert "<session-handoff>" in result
    assert "phase2 content" in result
    assert "<watchdog-alert>" not in result


# ── no-op paths ───────────────────────────────────────────────────────────────


def test_no_files_returns_empty_string(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    result = ibr._build_watchdog_block(str(brain_dir))

    assert result == ""
