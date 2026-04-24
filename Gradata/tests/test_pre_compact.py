"""Tests for the pre_compact PreCompact hook."""

from __future__ import annotations

from pathlib import Path

from gradata.hooks import pre_compact as pc


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_handoff(brain_dir: Path, content: str = "## Next action\nFix the bug.") -> Path:
    sessions = brain_dir / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    hf = sessions / "handoff-test.md"
    hf.write_text(content, encoding="utf-8")
    state = brain_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "pending_handoff.txt").write_text(str(hf), encoding="utf-8")
    return hf


# ── _read_pending_handoff ─────────────────────────────────────────────────────


def test_read_pending_handoff_returns_content(tmp_path):
    brain_dir = tmp_path / "brain"
    _make_handoff(brain_dir, "handoff body")
    content, pending = pc._read_pending_handoff(brain_dir)
    assert content == "handoff body"
    assert pending is not None and pending.name == "pending_handoff.txt"


def test_read_pending_handoff_missing_returns_none(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    content, pending = pc._read_pending_handoff(brain_dir)
    assert content is None and pending is None


def test_read_pending_handoff_stale_path_returns_none(tmp_path):
    brain_dir = tmp_path / "brain"
    state = brain_dir / "state"
    state.mkdir(parents=True)
    (state / "pending_handoff.txt").write_text("/nonexistent/path.md", encoding="utf-8")
    content, pending = pc._read_pending_handoff(brain_dir)
    assert content is None and pending is None


# ── main — auto trigger ───────────────────────────────────────────────────────


def test_auto_trigger_with_handoff_returns_compact_instructions(tmp_path, monkeypatch):
    brain_dir = tmp_path / "brain"
    _make_handoff(brain_dir, "## Handoff\nContinue from here.")
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))

    result = pc.main({"trigger": "auto"})

    assert result is not None
    assert "COMPACT INSTRUCTIONS" in result["result"]
    assert "Continue from here" in result["result"]


def test_auto_trigger_consumes_pending_handoff(tmp_path, monkeypatch):
    brain_dir = tmp_path / "brain"
    _make_handoff(brain_dir)
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))

    pc.main({"trigger": "auto"})

    assert not (brain_dir / "state" / "pending_handoff.txt").exists()


def test_auto_trigger_no_handoff_falls_back_to_snapshot(tmp_path, monkeypatch):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))

    result = pc.main({"trigger": "auto"})

    assert result == {"result": "State saved before compaction"}


# ── main — manual trigger ─────────────────────────────────────────────────────


def test_manual_trigger_always_snapshots(tmp_path, monkeypatch):
    brain_dir = tmp_path / "brain"
    _make_handoff(brain_dir)
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))

    result = pc.main({"trigger": "manual"})

    assert result == {"result": "State saved before compaction"}
    # pending_handoff.txt should NOT be consumed on manual compact
    assert (brain_dir / "state" / "pending_handoff.txt").exists()


def test_no_brain_dir_returns_none(monkeypatch):
    monkeypatch.setattr("gradata.hooks.pre_compact.resolve_brain_dir", lambda: None)
    result = pc.main({"trigger": "auto"})
    assert result is None


def test_legacy_type_field_treated_as_trigger(tmp_path, monkeypatch):
    """Older Claude Code versions send 'type' instead of 'trigger'."""
    brain_dir = tmp_path / "brain"
    _make_handoff(brain_dir, "legacy handoff content")
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))

    result = pc.main({"type": "auto"})

    assert result is not None
    assert "legacy handoff content" in result["result"]
