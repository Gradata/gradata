"""Tests for _transcript.py and _transcript_providers.py (P3 transcript store)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from gradata._transcript import cleanup_ttl, load_turns, log_turn
from gradata._transcript_providers import (
    GradataTranscriptSource,
    ProviderTranscriptSource,
    get_transcript_source,
)


# ── log_turn ─────────────────────────────────────────────────────────────────


def test_log_turn_disabled_by_default(tmp_path, monkeypatch):
    """GRADATA_TRANSCRIPT not set → no file written."""
    monkeypatch.delenv("GRADATA_TRANSCRIPT", raising=False)
    log_turn(str(tmp_path), "sess1", "user", "hello")
    assert not (tmp_path / "sessions" / "sess1" / "transcript.jsonl").exists()


def test_log_turn_writes_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "sess1", "user", "hello world")
    path = tmp_path / "sessions" / "sess1" / "transcript.jsonl"
    assert path.is_file()
    entry = json.loads(path.read_text())
    assert entry["role"] == "user"
    assert entry["content"] == "hello world"
    assert "ts" in entry


def test_log_turn_truncates_long_content(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    monkeypatch.setenv("GRADATA_TRANSCRIPT_TRUNCATE", "10")
    log_turn(str(tmp_path), "sess1", "assistant", "a" * 100)
    path = tmp_path / "sessions" / "sess1" / "transcript.jsonl"
    entry = json.loads(path.read_text())
    assert entry["content"] == "a" * 10


def test_log_turn_has_non_text(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "sess1", "user", None, has_non_text=True)
    path = tmp_path / "sessions" / "sess1" / "transcript.jsonl"
    entry = json.loads(path.read_text())
    assert entry["has_non_text"] is True
    assert entry["content"] is None


def test_log_turn_appends_multiple(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "sess1", "user", "turn 1")
    log_turn(str(tmp_path), "sess1", "assistant", "response 1")
    path = tmp_path / "sessions" / "sess1" / "transcript.jsonl"
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["role"] == "user"
    assert json.loads(lines[1])["role"] == "assistant"


def test_log_turn_noop_on_empty_brain_dir(monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn("", "sess1", "user", "test")  # Should not raise.


# ── load_turns ────────────────────────────────────────────────────────────────


def test_load_turns_returns_empty_when_no_file(tmp_path):
    assert load_turns(str(tmp_path), "nonexistent") == []


def test_load_turns_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "sess2", "user", "hello")
    log_turn(str(tmp_path), "sess2", "assistant", "world")
    turns = load_turns(str(tmp_path), "sess2")
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[1]["role"] == "assistant"


def test_load_turns_skips_malformed_lines(tmp_path):
    path = tmp_path / "sessions" / "s" / "transcript.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('bad json\n{"role":"user","content":"ok","ts":""}\n')
    turns = load_turns(str(tmp_path), "s")
    assert len(turns) == 1
    assert turns[0]["role"] == "user"


# ── cleanup_ttl ───────────────────────────────────────────────────────────────


def test_cleanup_ttl_removes_old_transcripts(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "old_sess", "user", "old")
    transcript = tmp_path / "sessions" / "old_sess" / "transcript.jsonl"
    # Backdate mtime by 40 days.
    old_time = time.time() - 40 * 86400
    import os

    os.utime(transcript, (old_time, old_time))
    deleted = cleanup_ttl(str(tmp_path), ttl_days=30)
    assert deleted == 1
    assert not transcript.exists()


def test_cleanup_ttl_preserves_recent(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "new_sess", "user", "recent")
    deleted = cleanup_ttl(str(tmp_path), ttl_days=30)
    assert deleted == 0


def test_cleanup_ttl_no_sessions_dir(tmp_path):
    assert cleanup_ttl(str(tmp_path), ttl_days=1) == 0


# ── ProviderTranscriptSource ──────────────────────────────────────────────────


def _write_provider_jsonl(path: Path, turns: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for t in turns:
            fh.write(json.dumps(t) + "\n")


def test_provider_source_finds_by_session_id(tmp_path, monkeypatch):
    proj = tmp_path / ".claude" / "projects" / "p1"
    proj.mkdir(parents=True)
    jsonl = proj / "myses.jsonl"
    _write_provider_jsonl(
        jsonl,
        [
            {"type": "user", "message": {"content": "hello"}, "timestamp": "t1"},
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "hi"}]},
                "timestamp": "t2",
            },
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    src = ProviderTranscriptSource("myses")
    assert src.available()
    turns = src.turns()
    assert len(turns) == 2
    assert turns[0]["role"] == "user"
    assert turns[0]["content"] == "hello"
    assert turns[1]["role"] == "assistant"
    assert turns[1]["content"] == "hi"


def test_provider_source_handles_non_text_blocks(tmp_path, monkeypatch):
    proj = tmp_path / ".claude" / "projects" / "p1"
    proj.mkdir(parents=True)
    jsonl = proj / "sess.jsonl"
    _write_provider_jsonl(
        jsonl,
        [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "done"},
                        {"type": "tool_use", "name": "Edit"},
                    ]
                },
                "timestamp": "t",
            }
        ],
    )
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    src = ProviderTranscriptSource("sess")
    turns = src.turns()
    assert turns[0]["has_non_text"] is True
    assert turns[0]["content"] == "done"


def test_provider_source_unavailable_when_no_projects(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    src = ProviderTranscriptSource("nope")
    assert not src.available()
    assert src.turns() == []


# ── GradataTranscriptSource ───────────────────────────────────────────────────


def test_gradata_source_reads_log_turn_output(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "gs1", "user", "what is x")
    log_turn(str(tmp_path), "gs1", "assistant", "x is y")
    src = GradataTranscriptSource(str(tmp_path), "gs1")
    assert src.available()
    turns = src.turns()
    assert len(turns) == 2


def test_gradata_source_unavailable_without_file(tmp_path):
    src = GradataTranscriptSource(str(tmp_path), "ghost")
    assert not src.available()
    assert src.turns() == []


def test_gradata_source_unavailable_without_session_id(tmp_path):
    src = GradataTranscriptSource(str(tmp_path), None)
    assert not src.available()


# ── get_transcript_source ─────────────────────────────────────────────────────


def test_get_transcript_source_prefers_provider(tmp_path, monkeypatch):
    proj = tmp_path / ".claude" / "projects" / "p"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text(
        json.dumps({"type": "user", "message": {"content": "hi"}, "timestamp": "t"}) + "\n"
    )
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    log_turn(str(tmp_path), "s", "user", "hi")
    src = get_transcript_source(str(tmp_path), "s")
    assert isinstance(src, ProviderTranscriptSource)


def test_get_transcript_source_falls_back_to_gradata(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("GRADATA_TRANSCRIPT", "1")
    log_turn(str(tmp_path), "s2", "user", "hello")
    src = get_transcript_source(str(tmp_path), "s2")
    assert isinstance(src, GradataTranscriptSource)


def test_get_transcript_source_returns_none_when_neither(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert get_transcript_source(str(tmp_path), "ghost") is None
