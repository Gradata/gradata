"""Tests for the ctx_watchdog Stop hook.

Covers: JSONL discovery, context ratio calculation, handoff write on
threshold breach, and no-op paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from gradata.hooks import ctx_watchdog as wdg


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _usage_entry(input_tokens: int, cache_read: int = 0, cache_create: int = 0) -> dict:
    return {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": 100,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
            }
        },
    }


# ── _read_context_usage ───────────────────────────────────────────────────────


def test_read_context_usage_basic(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [_usage_entry(100_000)])
    ratio = wdg._read_context_usage(jsonl, 200_000)
    assert ratio == pytest.approx(0.5)


def test_read_context_usage_includes_cache(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [_usage_entry(50_000, cache_read=50_000, cache_create=30_000)])
    ratio = wdg._read_context_usage(jsonl, 200_000)
    assert ratio == pytest.approx(0.65)


def test_read_context_usage_uses_last_entry(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [_usage_entry(10_000), _usage_entry(140_000)])
    ratio = wdg._read_context_usage(jsonl, 200_000)
    assert ratio == pytest.approx(0.7)


def test_read_context_usage_no_usage_entries_returns_none(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    _write_jsonl(jsonl, [{"type": "user", "message": "hello"}])
    assert wdg._read_context_usage(jsonl, 200_000) is None


def test_read_context_usage_missing_file_returns_none(tmp_path):
    assert wdg._read_context_usage(tmp_path / "nonexistent.jsonl", 200_000) is None


def test_read_context_usage_malformed_lines_skipped(tmp_path):
    jsonl = tmp_path / "session.jsonl"
    jsonl.write_text("not json\n" + json.dumps(_usage_entry(120_000)) + "\nbad\n")
    ratio = wdg._read_context_usage(jsonl, 200_000)
    assert ratio == pytest.approx(0.6)


# ── _find_session_jsonl ───────────────────────────────────────────────────────


def test_find_session_jsonl_by_id(tmp_path, monkeypatch):
    projects = tmp_path / ".claude" / "projects"
    proj_dir = projects / "proj1"
    proj_dir.mkdir(parents=True)
    target = proj_dir / "abc123.jsonl"
    target.write_text("{}\n")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = wdg._find_session_jsonl("abc123")
    assert result == target


def test_find_session_jsonl_fallback_most_recent(tmp_path, monkeypatch):
    projects = tmp_path / ".claude" / "projects"
    proj_dir = projects / "proj1"
    proj_dir.mkdir(parents=True)
    old = proj_dir / "old.jsonl"
    new = proj_dir / "new.jsonl"
    old.write_text("{}\n")
    import time

    time.sleep(0.01)
    new.write_text("{}\n")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = wdg._find_session_jsonl(None)
    assert result == new


def test_find_session_jsonl_no_projects_dir_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert wdg._find_session_jsonl("xyz") is None


# ── main ─────────────────────────────────────────────────────────────────────


def test_main_below_threshold_no_handoff(tmp_path, monkeypatch):
    """Context at 50% with 65% threshold → no handoff written."""
    projects = tmp_path / ".claude" / "projects" / "p"
    projects.mkdir(parents=True)
    jsonl = projects / "sess1.jsonl"
    _write_jsonl(jsonl, [_usage_entry(100_000)])

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("GRADATA_CTX_THRESHOLD", "0.65")
    monkeypatch.setenv("GRADATA_CTX_WINDOW", "200000")

    result = wdg.main({"session_id": "sess1"})
    assert result is None
    assert not (brain_dir / "state" / "pending_handoff.txt").exists()


def test_main_above_threshold_writes_handoff(tmp_path, monkeypatch):
    """Context at 70% with 65% threshold → handoff + pending_handoff.txt written."""
    projects = tmp_path / ".claude" / "projects" / "p"
    projects.mkdir(parents=True)
    jsonl = projects / "sess2.jsonl"
    _write_jsonl(jsonl, [_usage_entry(140_000)])

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("GRADATA_CTX_THRESHOLD", "0.65")
    monkeypatch.setenv("GRADATA_CTX_WINDOW", "200000")

    result = wdg.main({"session_id": "sess2", "session_number": 42})
    assert result is None

    pending = brain_dir / "state" / "pending_handoff.txt"
    assert pending.is_file()
    handoff_path = Path(pending.read_text(encoding="utf-8").strip())
    assert handoff_path.is_file()
    content = handoff_path.read_text(encoding="utf-8")
    assert "70%" in content
    assert "Session: 42" in content


def test_main_no_jsonl_returns_none(tmp_path, monkeypatch):
    """No JSONL file discoverable → silently returns None."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))

    result = wdg.main({"session_id": "ghost"})
    assert result is None


def test_main_custom_threshold(tmp_path, monkeypatch):
    """Custom threshold of 80% — 70% usage should NOT trigger."""
    projects = tmp_path / ".claude" / "projects" / "p"
    projects.mkdir(parents=True)
    jsonl = projects / "sess3.jsonl"
    _write_jsonl(jsonl, [_usage_entry(140_000)])

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain_dir))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("GRADATA_CTX_THRESHOLD", "0.80")
    monkeypatch.setenv("GRADATA_CTX_WINDOW", "200000")

    wdg.main({"session_id": "sess3"})
    assert not (brain_dir / "state" / "pending_handoff.txt").exists()
