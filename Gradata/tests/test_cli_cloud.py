"""Tests for the ``gradata cloud`` CLI family.

Keyfile writes/reads are rerouted to a tmp dir so no real user state is
touched. Each test shells argparse via ``cli.main`` with a synthetic argv.
"""

from __future__ import annotations

import sys

import pytest

from gradata import cli
from gradata.cloud import _credentials as _creds


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch, capsys):
    """Route keyfile + brain discovery to tmp paths."""
    fake_key = tmp_path / ".gradata" / "key"
    monkeypatch.setattr(_creds, "KEYFILE_DIR", fake_key.parent)
    monkeypatch.setattr(_creds, "KEYFILE_PATH", fake_key)
    brain = tmp_path / "brain"
    brain.mkdir()
    monkeypatch.setenv("GRADATA_BRAIN", str(brain))
    yield brain


def _run(monkeypatch, *argv: str) -> str:
    monkeypatch.setattr(sys, "argv", ["gradata", *argv])
    try:
        cli.main()
    except SystemExit as e:
        if e.code not in (0, None):
            raise
    return ""


def test_cloud_enable_writes_keyfile(_isolate, monkeypatch, capsys):
    _run(
        monkeypatch,
        "cloud",
        "enable",
        "--key",
        "gk_live_testkey_abcdef123456",
        "--scope",
        "team:acme",
    )
    out = capsys.readouterr().out
    assert "enabled" in out.lower()
    assert _creds.load_from_keyfile() == "gk_live_testkey_abcdef123456"

    from gradata.cloud.sync import load_config

    cfg = load_config(_isolate)
    assert cfg.sync_enabled is True
    assert cfg.key_scope == "team:acme"


def test_cloud_enable_warns_on_missing_prefix(_isolate, monkeypatch, capsys):
    _run(monkeypatch, "cloud", "enable", "--key", "weirdformat12345")
    out = capsys.readouterr().out
    assert "warning" in out.lower()
    assert _creds.load_from_keyfile() == "weirdformat12345"


def test_cloud_status_reports_no_key(_isolate, monkeypatch, capsys):
    _run(monkeypatch, "cloud", "status")
    out = capsys.readouterr().out
    assert "credential:" in out
    assert "(none)" in out


def test_cloud_status_masks_credential(_isolate, monkeypatch, capsys):
    _creds.write_to_keyfile("gk_live_verylongsecretvalue1234567890")
    _run(monkeypatch, "cloud", "status")
    out = capsys.readouterr().out
    assert "gk_liv" in out
    assert "7890" in out
    assert "verylongsecretvalue" not in out  # not printed in full


def test_cloud_rotate_key(_isolate, monkeypatch, capsys):
    _creds.write_to_keyfile("gk_live_oldkey_11111111111111")
    _run(monkeypatch, "cloud", "rotate-key", "--key", "gk_live_newkey_22222222222222")
    out = capsys.readouterr().out
    assert "Rotating" in out
    assert _creds.load_from_keyfile() == "gk_live_newkey_22222222222222"


def test_cloud_disconnect_removes_keyfile(_isolate, monkeypatch, capsys):
    _creds.write_to_keyfile("gk_live_tokill_33333333333333")
    _run(monkeypatch, "cloud", "disconnect")
    out = capsys.readouterr().out
    assert _creds.load_from_keyfile() == ""
    assert "removed" in out.lower()

    from gradata.cloud.sync import load_config

    cfg = load_config(_isolate)
    assert cfg.sync_enabled is False


def test_cloud_disconnect_idempotent(_isolate, monkeypatch, capsys):
    _run(monkeypatch, "cloud", "disconnect")
    out = capsys.readouterr().out
    assert "no keyfile" in out.lower()


def test_login_prints_deprecation_notice(_isolate, monkeypatch, capsys):
    """`gradata login` must emit a deprecation note pointing at cloud enable."""
    # Short-circuit the device flow by making urlopen fail immediately.
    import urllib.error
    import urllib.request

    def _boom(*_a, **_kw):
        raise urllib.error.URLError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    with pytest.raises(SystemExit):
        _run(monkeypatch, "login")
    out = capsys.readouterr().out
    assert "deprecated" in out.lower()
    assert "cloud enable" in out
