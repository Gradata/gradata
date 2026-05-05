"""Tests for `gradata seed` — Day-0 brain bootstrapping."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import pytest

from gradata import Brain
from gradata.cli import _SEVEN_STARTER_RULES, cmd_seed


def _bootstrap_brain(brain_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import gradata._paths as _p

    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))
    importlib.reload(_p)
    Brain.init(brain_dir)


def _args(brain_dir: Path, *, seven_lines: bool = True) -> argparse.Namespace:
    return argparse.Namespace(brain_dir=str(brain_dir), seven_lines=seven_lines)


def test_seven_starter_rules_shape():
    assert len(_SEVEN_STARTER_RULES) == 7
    for cat, text in _SEVEN_STARTER_RULES:
        assert cat in {"PATTERN", "CODE", "PROCESS", "TRUTH", "SECURITY"}
        assert len(text) > 10


def test_cmd_seed_adds_7_rules_first_run(tmp_path, capsys, monkeypatch):
    brain_dir = tmp_path / "brain"
    _bootstrap_brain(brain_dir, monkeypatch)
    cmd_seed(_args(brain_dir))
    out = capsys.readouterr().out
    assert "7 added, 0 already present" in out


def test_cmd_seed_is_idempotent(tmp_path, capsys, monkeypatch):
    brain_dir = tmp_path / "brain"
    _bootstrap_brain(brain_dir, monkeypatch)
    cmd_seed(_args(brain_dir))
    capsys.readouterr()  # drop first output
    cmd_seed(_args(brain_dir))
    out = capsys.readouterr().out
    assert "0 added, 7 already present" in out


def test_cmd_seed_errors_without_flag(tmp_path, capsys, monkeypatch):
    brain_dir = tmp_path / "brain"
    _bootstrap_brain(brain_dir, monkeypatch)
    with pytest.raises(SystemExit) as exc:
        cmd_seed(_args(brain_dir, seven_lines=False))
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "pick a seed set" in err


def test_cmd_seed_creates_missing_brain_dir(tmp_path, capsys):
    brain_dir = tmp_path / "does-not-exist-yet" / "brain"
    cmd_seed(_args(brain_dir))
    assert brain_dir.exists()
    out = capsys.readouterr().out
    assert "7 added" in out
