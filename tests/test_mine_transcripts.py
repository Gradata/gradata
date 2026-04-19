"""Tests for gradata._mine_transcripts — transcript backfill + noise filters.

Covers the filters added after a shadow run against the live brain revealed
40% false positives from claude-mem observer echoes and system wrappers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradata._mine_transcripts import (
    _detect_signals,
    _extract_user_text,
    _mine_session,
    run_mine,
)


# ── Signal detection ──


@pytest.mark.parametrize(
    "text,expected",
    [
        ("are you sure about that approach", ["PUSHBACK"]),
        ("why didn't you run the tests first", ["PUSHBACK"]),
        ("make sure the db connection closes", ["REMINDER"]),
        ("don't forget the edge case", ["REMINDER"]),
        ("what about the null input path", ["GAP"]),
        ("you forgot the ORDER BY clause", ["GAP"]),
        ("are we missing something here", ["CHALLENGE"]),
        ("i feel like this could break", ["CHALLENGE"]),
        ("just ship it", []),
        ("", []),
        ("short", []),  # < 10 chars
    ],
)
def test_detect_signals(text, expected):
    assert _detect_signals(text) == expected


def test_detect_signals_multiple_groups():
    text = "make sure you didn't forget — what about error paths"
    hits = _detect_signals(text)
    assert "REMINDER" in hits
    assert "GAP" in hits


# ── Text extraction ──


def test_extract_user_text_string_content():
    msg = {"type": "user", "message": {"role": "user", "content": "hello"}}
    assert _extract_user_text(msg) == "hello"


def test_extract_user_text_list_content():
    msg = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "text", "text": "first"},
                {"type": "text", "text": "second"},
            ],
        },
    }
    assert _extract_user_text(msg) == "first\nsecond"


def test_extract_user_text_assistant_skipped():
    msg = {"type": "assistant", "message": {"role": "assistant", "content": "hi"}}
    assert _extract_user_text(msg) == ""


# ── Noise filtering (the key regression guards) ──


def _write_session(tmp_path: Path, project: str, msgs: list[dict]) -> Path:
    proj = tmp_path / project
    proj.mkdir(parents=True, exist_ok=True)
    path = proj / "session.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for m in msgs:
            fh.write(json.dumps(m) + "\n")
    return path


def _user_msg(text: str) -> dict:
    return {
        "type": "user",
        "uuid": "u1",
        "sessionId": "s1",
        "timestamp": "2026-04-18T00:00:00Z",
        "message": {"role": "user", "content": text},
    }


def test_mine_session_skips_observer_project(tmp_path):
    path = _write_session(
        tmp_path,
        "C--Users-olive--claude-mem-observer-sessions",
        [_user_msg("are you sure this is right, make sure it works")],
    )
    assert _mine_session(path) == []


def test_mine_session_skips_system_wrappers(tmp_path):
    msgs = [
        _user_msg("<system-reminder> are you sure about it </system-reminder>"),
        _user_msg("<observed_from_primary_session> make sure you don't forget"),
        _user_msg("<command-message> what about the failing test </command-message>"),
        _user_msg("<local-command-stdout> you forgot to commit </local-command-stdout>"),
    ]
    path = _write_session(tmp_path, "C--real-project", msgs)
    assert _mine_session(path) == []


def test_mine_session_keeps_real_corrections(tmp_path):
    msgs = [
        _user_msg("are you sure about that approach"),
        _user_msg("make sure to handle the null case"),
    ]
    path = _write_session(tmp_path, "C--real-project", msgs)
    events = _mine_session(path)
    assert len(events) == 2
    assert all(e["event"] == "IMPLICIT_FEEDBACK" for e in events)
    assert all(e["source"] == "gradata.mine" for e in events)


def test_mine_session_skips_scheduled_task(tmp_path):
    path = _write_session(
        tmp_path,
        "C--real-project",
        [_user_msg("<scheduled-task> are you sure this fires </scheduled-task>")],
    )
    assert _mine_session(path) == []


# ── run_mine end-to-end ──


def test_run_mine_dry_run_writes_nothing(tmp_path):
    brain = tmp_path / "brain"
    projects = tmp_path / "projects"
    _write_session(
        projects,
        "C--p1",
        [_user_msg("are you sure about that"), _user_msg("make sure to test")],
    )
    run_mine(
        brain_root=brain,
        projects_root=projects,
        project=None,
        commit=False,
        dry_run=True,
    )
    assert not (brain / "events.backfill.jsonl").exists()
    assert not (brain / "events.jsonl").exists()


def test_run_mine_shadow_writes_backfill_only(tmp_path):
    brain = tmp_path / "brain"
    projects = tmp_path / "projects"
    _write_session(
        projects,
        "C--p1",
        [_user_msg("are you sure about that")],
    )
    run_mine(
        brain_root=brain,
        projects_root=projects,
        project=None,
        commit=False,
        dry_run=False,
    )
    shadow = brain / "events.backfill.jsonl"
    assert shadow.exists()
    lines = shadow.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert ev["event"] == "IMPLICIT_FEEDBACK"
    assert not (brain / "events.jsonl").exists()


def test_run_mine_project_filter(tmp_path):
    brain = tmp_path / "brain"
    projects = tmp_path / "projects"
    _write_session(projects, "C--keep", [_user_msg("are you sure about it")])
    _write_session(projects, "C--skip", [_user_msg("make sure to test")])
    run_mine(
        brain_root=brain,
        projects_root=projects,
        project="C--keep",
        commit=False,
        dry_run=False,
    )
    lines = (brain / "events.backfill.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    ev = json.loads(lines[0])
    assert json.loads(ev["data"])["project"] == "C--keep"


def test_run_mine_missing_projects_root_returns_1(tmp_path, capsys):
    rc = run_mine(
        brain_root=tmp_path / "brain",
        projects_root=tmp_path / "does-not-exist",
        project=None,
        commit=False,
        dry_run=True,
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "transcript root not found" in err


def test_run_mine_missing_project_dir_warns(tmp_path, capsys):
    projects = tmp_path / "projects"
    projects.mkdir()
    run_mine(
        brain_root=tmp_path / "brain",
        projects_root=projects,
        project="C--does-not-exist",
        commit=False,
        dry_run=True,
    )
    err = capsys.readouterr().err
    assert "skip missing" in err


def test_run_mine_commit_appends_live(tmp_path):
    brain = tmp_path / "brain"
    brain.mkdir()
    live = brain / "events.jsonl"
    live.write_text('{"event": "PRE_EXISTING"}\n', encoding="utf-8")

    projects = tmp_path / "projects"
    _write_session(
        projects,
        "C--p1",
        [_user_msg("are you sure about that")],
    )
    run_mine(
        brain_root=brain,
        projects_root=projects,
        project=None,
        commit=True,
        dry_run=False,
    )
    lines = live.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "PRE_EXISTING"
    assert json.loads(lines[1])["event"] == "IMPLICIT_FEEDBACK"
