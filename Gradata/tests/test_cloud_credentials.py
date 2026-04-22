"""Tests for gradata.cloud._credentials — keyfile + env + fallback chain.

Keyfile path is rebound to a per-test tmp path so the user's real
``~/.gradata/key`` is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gradata.cloud import _credentials as _creds


@pytest.fixture(autouse=True)
def _isolate_keyfile(tmp_path, monkeypatch):
    """Rebind KEYFILE_DIR/KEYFILE_PATH to tmp_path for every test in this file."""
    fake_dir = tmp_path / ".gradata"
    fake_path = fake_dir / "key"
    monkeypatch.setattr(_creds, "KEYFILE_DIR", fake_dir)
    monkeypatch.setattr(_creds, "KEYFILE_PATH", fake_path)
    yield


def test_write_then_load_keyfile():
    p = _creds.write_to_keyfile("my-cred-abc123")
    assert isinstance(p, Path)
    assert _creds.load_from_keyfile() == "my-cred-abc123"


def test_load_keyfile_missing_returns_empty():
    assert _creds.load_from_keyfile() == ""


def test_delete_keyfile_roundtrip():
    _creds.write_to_keyfile("x")
    assert _creds.delete_keyfile() is True
    assert _creds.load_from_keyfile() == ""
    # Deleting a non-existent keyfile is a noop.
    assert _creds.delete_keyfile() is False


def test_resolve_credential_explicit_wins(monkeypatch):
    _creds.write_to_keyfile("from-keyfile")
    monkeypatch.setenv("GRADATA_API_KEY", "from-env")
    assert _creds.resolve_credential("explicit-val") == "explicit-val"


def test_resolve_credential_keyfile_beats_env(monkeypatch):
    _creds.write_to_keyfile("from-keyfile")
    monkeypatch.setenv("GRADATA_API_KEY", "from-env")
    assert _creds.resolve_credential() == "from-keyfile"


def test_resolve_credential_env_fallback(monkeypatch):
    monkeypatch.setenv("GRADATA_API_KEY", "from-env")
    assert _creds.resolve_credential() == "from-env"


def test_resolve_credential_returns_empty_when_nothing_set(monkeypatch):
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    assert _creds.resolve_credential() == ""


def test_resolve_endpoint_kwarg_wins(monkeypatch):
    monkeypatch.setenv("GRADATA_ENDPOINT", "https://env.example.com")
    assert _creds.resolve_endpoint("https://explicit.example.com") == "https://explicit.example.com"


def test_resolve_endpoint_env_fallback(monkeypatch):
    monkeypatch.setenv("GRADATA_ENDPOINT", "https://env.example.com/")
    assert _creds.resolve_endpoint() == "https://env.example.com"


def test_resolve_endpoint_fallback_default(monkeypatch):
    monkeypatch.delenv("GRADATA_ENDPOINT", raising=False)
    monkeypatch.delenv("GRADATA_CLOUD_API_BASE", raising=False)
    assert _creds.resolve_endpoint(fallback="https://default.example.com/") == (
        "https://default.example.com"
    )


def test_kill_switch_default_off(monkeypatch):
    monkeypatch.delenv("GRADATA_CLOUD_SYNC_DISABLE", raising=False)
    assert _creds.kill_switch_set() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "TRUE", "Yes"])
def test_kill_switch_recognises_truthy_values(val, monkeypatch):
    monkeypatch.setenv("GRADATA_CLOUD_SYNC_DISABLE", val)
    assert _creds.kill_switch_set() is True


def test_kill_switch_ignores_random_values(monkeypatch):
    monkeypatch.setenv("GRADATA_CLOUD_SYNC_DISABLE", "maybe")
    assert _creds.kill_switch_set() is False


def test_key_prefix_matches_live_scheme():
    # Sanity: the split-string trick keeps the value correct.
    assert _creds.KEY_PREFIX == "gk_live_"


def test_kill_switch_disables_row_push(monkeypatch):
    """The kill switch flips gradata._cloud_sync.enabled() to False even when
    GRADATA_CLOUD_SYNC=1 and URL/key are set."""
    import gradata._cloud_sync as row_push

    monkeypatch.setenv("GRADATA_CLOUD_SYNC", "1")
    monkeypatch.setenv("GRADATA_CLOUD_URL", "https://cloud.example.com")
    monkeypatch.setenv("GRADATA_CLOUD_KEY", "k")
    assert row_push.enabled() is True

    monkeypatch.setenv("GRADATA_CLOUD_SYNC_DISABLE", "1")
    assert row_push.enabled() is False


def test_cloudclient_consults_keyfile_when_config_token_empty(tmp_path):
    """sync.CloudClient should resolve a credential from the keyfile when
    cloud-config.json has no token stored — proves the unified auth chain."""
    from gradata.cloud.sync import CloudClient, CloudConfig

    _creds.write_to_keyfile("from-keyfile-xyz")
    cfg = CloudConfig(sync_enabled=True, token="", api_base="https://api.example.com")
    client = CloudClient(tmp_path, config=cfg)
    assert client.enabled is True
    assert client._resolved_credential() == "from-keyfile-xyz"


def test_cloudclient_not_enabled_without_any_credential(tmp_path, monkeypatch):
    from gradata.cloud.sync import CloudClient, CloudConfig

    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    cfg = CloudConfig(sync_enabled=True, token="", api_base="https://api.example.com")
    client = CloudClient(tmp_path, config=cfg)
    assert client.enabled is False
