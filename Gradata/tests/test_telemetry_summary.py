"""Tests for telemetry recording in run_hook + the summary CLI."""

from __future__ import annotations

import json

from gradata.hooks import _base, telemetry_summary
from gradata.hooks._profiles import Profile


def test_run_hook_records_telemetry(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    monkeypatch.setenv("GRADATA_TELEMETRY", "on")

    def main_fn(_data):
        return {"result": "hello world"}

    main_fn.__module__ = "gradata.hooks.fake_hook"
    meta = {"event": "PreToolUse", "profile": Profile.STANDARD}
    _base.run_hook(main_fn, meta, raw_input='{"x":1}')

    log = tmp_path / "telemetry.jsonl"
    assert log.is_file()
    rows = [json.loads(line) for line in log.read_text().strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["event"] == "PreToolUse"
    assert rows[0]["hook"] == "fake_hook"
    assert rows[0]["bytes"] > 0


def test_run_hook_records_zero_bytes_when_none(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    monkeypatch.setenv("GRADATA_TELEMETRY", "on")

    def main_fn(_data):
        return None

    main_fn.__module__ = "gradata.hooks.fake_hook"
    _base.run_hook(main_fn, {"event": "PreToolUse", "profile": Profile.STANDARD}, raw_input="{}")

    log = tmp_path / "telemetry.jsonl"
    rows = [json.loads(line) for line in log.read_text().strip().splitlines()]
    assert rows[0]["bytes"] == 0


def test_telemetry_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    monkeypatch.setenv("GRADATA_TELEMETRY", "off")

    def main_fn(_data):
        return {"result": "x"}

    main_fn.__module__ = "gradata.hooks.fake_hook"
    _base.run_hook(main_fn, {"event": "PreToolUse", "profile": Profile.STANDARD}, raw_input="{}")

    assert not (tmp_path / "telemetry.jsonl").exists()


def test_summarize_empty():
    out = telemetry_summary.summarize([])
    assert "no telemetry recorded" in out


def test_summarize_aggregates():
    rows = [
        {"event": "PreToolUse", "hook": "rule_enforcement", "bytes": 100},
        {"event": "PreToolUse", "hook": "rule_enforcement", "bytes": 0},
        {"event": "PreToolUse", "hook": "rule_enforcement", "bytes": 200},
        {"event": "SessionStart", "hook": "inject_brain_rules", "bytes": 1900},
    ]
    out = telemetry_summary.summarize(rows)
    assert "rule_enforcement" in out
    assert "inject_brain_rules" in out
    assert "Suppressed 1/4" in out


def test_cli_reset(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    log = tmp_path / "telemetry.jsonl"
    log.write_text('{"hook":"x","bytes":1}\n')
    rc = telemetry_summary.main(["--reset"])
    assert rc == 0
    assert not log.exists()


def test_cli_summary_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    (tmp_path / "telemetry.jsonl").write_text(
        '{"event":"PreToolUse","hook":"a","bytes":50}\n'
        '{"event":"PreToolUse","hook":"a","bytes":0}\n'
    )
    rc = telemetry_summary.main([])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "gradata telemetry" in captured
    assert "Suppressed 1/2" in captured
