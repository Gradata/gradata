"""Contract tests for ``gradata.cloud.pull.pull_events`` — Phase 1 stub.

The pull endpoint ships disabled server-side. These tests lock the client
contract so the interface can't drift before Phase 2 wires the merge path.

See ``docs/specs/events-pull-contract.md``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata import Brain
from gradata.cloud import _credentials as _creds
from gradata.cloud.pull import pull_events
from gradata.cloud.sync import CloudConfig, save_config


@pytest.fixture
def brain(tmp_path):
    b = Brain(tmp_path)
    b.emit("TEST", "src", {"x": 1}, [])
    return b


@pytest.fixture(autouse=True)
def _isolate_keyfile(tmp_path, monkeypatch):
    fake = tmp_path / ".gradata_test_key"
    monkeypatch.setattr(_creds, "KEYFILE_PATH", fake)
    monkeypatch.setattr(_creds, "KEYFILE_DIR", fake.parent)
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    monkeypatch.delenv("GRADATA_CLOUD_SYNC_DISABLE", raising=False)
    yield


def _save_cfg(
    brain_dir: Path,
    *,
    enabled: bool = True,
    tok: str = "gk_live_test",
    api_base: str = "https://api.example.com",
):
    cfg = CloudConfig(sync_enabled=enabled, api_base=api_base)
    cfg.token = tok
    save_config(brain_dir, cfg)


def test_no_db_returns_error(tmp_path):
    result = pull_events(tmp_path)
    assert result["status"] == "error"
    assert result["reason"] == "no_db"


def test_kill_switch_short_circuits(brain, monkeypatch):
    _save_cfg(brain.dir)
    monkeypatch.setenv("GRADATA_CLOUD_SYNC_DISABLE", "1")
    assert pull_events(brain.dir)["status"] == "kill_switch"


def test_disabled_by_config(brain):
    _save_cfg(brain.dir, enabled=False)
    assert pull_events(brain.dir)["status"] == "disabled"


def test_no_credential(brain):
    _save_cfg(brain.dir, tok="")
    assert pull_events(brain.dir)["status"] == "no_credential"


def test_non_https_rejected(brain):
    _save_cfg(brain.dir, api_base="http://not-https.example.com")
    result = pull_events(brain.dir)
    assert result["status"] == "error"
    assert result["reason"] == "https_required"


def test_server_501_returns_disabled_server_side(brain):
    """Phase 1 server returns 501; client surfaces it as a clean status."""
    import urllib.error

    _save_cfg(brain.dir)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 501, "Not Implemented", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = pull_events(brain.dir)

    assert result["status"] == "disabled_server_side"
    assert result["events_pulled"] == 0


def test_server_410_surfaces_rewind_error(brain):
    import urllib.error

    _save_cfg(brain.dir)

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 410, "Gone", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = pull_events(brain.dir, rebuild_from="01JN0000000000000000000000")

    assert result["status"] == "error"
    assert result["reason"] == "rewind_beyond_retention"


def test_server_200_raises_not_implemented(brain):
    """Phase 1 MUST NOT merge pulled events — raises loudly to prevent silent corruption."""
    _save_cfg(brain.dir)

    body = json.dumps(
        {
            "events": [{"event_id": "01JN...", "type": "TEST"}],
            "watermark": "01JN...",
            "end_of_stream": True,
        }
    ).encode()

    class FakeResp:
        def __init__(self, data):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp(body)):
        with pytest.raises(NotImplementedError, match="Phase 2"):
            pull_events(brain.dir)


def test_request_includes_brain_and_device_id(brain):
    """Contract: every pull request carries brain_id and device_id as query params."""
    import urllib.error

    _save_cfg(brain.dir)
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        raise urllib.error.HTTPError(req.full_url, 501, "Not Implemented", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        pull_events(brain.dir)

    assert "brain_id=" in captured["url"]
    assert "device_id=dev_" in captured["url"]
    assert captured["auth"] == "Bearer gk_live_test"


def test_limit_is_clamped(brain):
    """Contract: limit is clamped to [1, 1000]."""
    import urllib.error

    _save_cfg(brain.dir)
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        raise urllib.error.HTTPError(req.full_url, 501, "Not Implemented", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        pull_events(brain.dir, limit=99999)

    assert "limit=1000" in captured["url"]


def test_credential_resolves_from_keyfile_when_config_token_empty(brain):
    """Keyfile flows to Authorization header even when config.token is empty."""
    import urllib.error

    _save_cfg(brain.dir, tok="")
    _creds.write_to_keyfile("gk_live_from_keyfile")

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.headers.get("Authorization")
        raise urllib.error.HTTPError(req.full_url, 501, "Not Implemented", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = pull_events(brain.dir)

    assert result["status"] == "disabled_server_side"
    assert captured["auth"] == "Bearer gk_live_from_keyfile"
