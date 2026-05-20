"""Tests for the ``gradata projects`` subcommand (GRA-1238).

Covers:
  * missing registry → friendly message, exit 0
  * empty registry → friendly message, exit 0
  * single project (brain_dir missing on disk → sync_status='missing')
  * multi-project registry
  * malformed TOML → SystemExit(1) with error message
  * --json output shape
  * missing brain_dir → sync_status='missing' (explicit case)
  * brain_dir present + no system.db → sync_status='ok', rules=0
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata.cli import cmd_projects


class _Args:
    """Minimal stand-in for argparse.Namespace."""

    def __init__(self, *, json: bool = False) -> None:
        self.json = json


def _patch_home(tmp_path: Path):
    """Return a patcher pinning ``Path.home()`` to tmp_path for cmd_projects."""
    return patch("pathlib.Path.home", return_value=tmp_path)


def _write_registry(home: Path, contents: str) -> None:
    cfg_dir = home / ".gradata"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "projects.toml").write_text(contents, encoding="utf-8")


def test_missing_registry_prints_hint_and_exits_zero(tmp_path, capsys):
    # No projects.toml at all → friendly message, no crash, exit 0 (function returns).
    with _patch_home(tmp_path):
        cmd_projects(_Args())
    out = capsys.readouterr().out
    assert "No projects registered" in out
    assert "gradata init" in out


def test_missing_registry_json_returns_empty_array(tmp_path, capsys):
    with _patch_home(tmp_path):
        cmd_projects(_Args(json=True))
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == []


def test_empty_registry_prints_hint(tmp_path, capsys):
    _write_registry(tmp_path, "")  # valid TOML, no [[projects]]
    with _patch_home(tmp_path):
        cmd_projects(_Args())
    out = capsys.readouterr().out
    assert "No projects registered" in out


def test_single_project_missing_brain_dir(tmp_path, capsys):
    _write_registry(
        tmp_path,
        '[[projects]]\nname = "alpha"\nbrain_dir = "/nonexistent/path/brain"\n',
    )
    with _patch_home(tmp_path):
        cmd_projects(_Args())
    out = capsys.readouterr().out
    # Header + one row.
    assert "NAME" in out
    assert "alpha" in out
    assert "missing" in out
    assert "(never)" in out


def test_single_project_brain_dir_exists_no_db(tmp_path, capsys):
    brain_dir = tmp_path / "my-brain"
    brain_dir.mkdir()
    _write_registry(
        tmp_path,
        f'[[projects]]\nname = "alpha"\nbrain_dir = "{brain_dir}"\n',
    )
    with _patch_home(tmp_path):
        cmd_projects(_Args(json=True))
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    row = payload[0]
    assert row["name"] == "alpha"
    assert row["brain_dir"] == str(brain_dir)
    assert row["rules"] == 0
    assert row["last_correction"] is None
    assert row["sync_status"] == "ok"


def test_multi_project_registry(tmp_path, capsys):
    other_dir = tmp_path / "other-brain"
    other_dir.mkdir()
    _write_registry(
        tmp_path,
        f"""
[[projects]]
name = "alpha"
brain_dir = "/nope/alpha"

[[projects]]
name = "beta"
brain_dir = "{other_dir}"
""",
    )
    with _patch_home(tmp_path):
        cmd_projects(_Args(json=True))
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 2
    names = {row["name"] for row in payload}
    assert names == {"alpha", "beta"}
    by_name = {row["name"]: row for row in payload}
    assert by_name["alpha"]["sync_status"] == "missing"
    assert by_name["beta"]["sync_status"] == "ok"


def test_malformed_toml_exits_one(tmp_path, capsys):
    _write_registry(tmp_path, "this = is = broken =\n[[[\n")
    with _patch_home(tmp_path), pytest.raises(SystemExit) as excinfo:
        cmd_projects(_Args())
    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "malformed" in out.lower() or "error" in out.lower()


def test_json_output_shape(tmp_path, capsys):
    _write_registry(
        tmp_path,
        '[[projects]]\nname = "alpha"\nbrain_dir = "/nope/alpha"\n',
    )
    with _patch_home(tmp_path):
        cmd_projects(_Args(json=True))
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0].keys() == {
        "name",
        "brain_dir",
        "rules",
        "last_correction",
        "sync_status",
    }


def test_real_db_with_rule_graduated_event(tmp_path, capsys):
    """Real sqlite db with an events table → rules count is read."""
    import sqlite3

    brain_dir = tmp_path / "brain-x"
    brain_dir.mkdir()
    db = brain_dir / "system.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE events (type TEXT, ts TEXT)")
    con.execute("INSERT INTO events (type, ts) VALUES ('RULE_GRADUATED', '2025-01-01')")
    con.execute("INSERT INTO events (type, ts) VALUES ('RULE_GRADUATED', '2025-01-02')")
    con.execute("INSERT INTO events (type, ts) VALUES ('CORRECTION', '2025-05-10T12:00:00Z')")
    con.commit()
    con.close()

    _write_registry(
        tmp_path,
        f'[[projects]]\nname = "x"\nbrain_dir = "{brain_dir}"\n',
    )
    with _patch_home(tmp_path):
        cmd_projects(_Args(json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["rules"] == 2
    assert payload[0]["last_correction"] == "2025-05-10T12:00:00Z"
    assert payload[0]["sync_status"] == "ok"
