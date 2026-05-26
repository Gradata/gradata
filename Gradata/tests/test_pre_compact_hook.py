from __future__ import annotations

import json
from pathlib import Path

from gradata.hooks import pre_compact
from gradata.hooks._base import run_hook


def test_pre_compact_writes_snapshot(tmp_path: Path, monkeypatch) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "brain_prompt.md").write_text("remember this rule", encoding="utf-8")
    monkeypatch.setenv("BRAIN_DIR", str(brain))

    result = pre_compact.main(
        {
            "hook_event_name": "PreCompact",
            "session_id": "abc123",
            "trigger": "manual",
            "cwd": "/repo",
            "transcript_path": "/tmp/transcript.jsonl",
            "custom_instructions": "be concise",
        }
    )

    assert result is None
    snapshot_path = brain / ".precompact-snapshots" / "abc123.json"
    assert snapshot_path.exists()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["event"] == "PreCompact"
    assert snapshot["session_id"] == "abc123"
    assert snapshot["trigger"] == "manual"
    assert snapshot["cwd"] == "/repo"
    assert snapshot["transcript_path"] == "/tmp/transcript.jsonl"
    assert snapshot["custom_instructions"] == "be concise"
    assert snapshot["relevant_context"]["brain_prompt_md"] == "remember this rule"
    assert snapshot["limits"]["transcript_content_captured"] is False


def test_pre_compact_sanitizes_session_id(tmp_path: Path, monkeypatch) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain))

    pre_compact.main({"session_id": "../../escape/session"})

    snapshots = list((brain / ".precompact-snapshots").glob("*.json"))
    assert len(snapshots) == 1
    assert snapshots[0].parent == brain / ".precompact-snapshots"
    assert ".." not in snapshots[0].name
    assert "/" not in snapshots[0].name


def test_pre_compact_missing_brain_noops(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "missing"))

    assert pre_compact.main({"session_id": "abc123"}) is None


def test_pre_compact_callable_via_run_hook(tmp_path: Path, monkeypatch) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    monkeypatch.setenv("BRAIN_DIR", str(brain))

    run_hook(
        pre_compact.main,
        pre_compact.HOOK_META,
        raw_input=json.dumps({"session_id": "via-run-hook", "hook_event_name": "PreCompact"}),
    )

    assert (brain / ".precompact-snapshots" / "via-run-hook.json").exists()
