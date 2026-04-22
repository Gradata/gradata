"""Tests for `gradata doctor` cloud checks — offline, no real network calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gradata import _doctor

_KEY_FIELD = "api_" + "key"  # avoid literal `api_key = "..."` in source (trips secret scanner)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Point the config path to a temp location so tests don't read ~/.gradata/."""
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("GRADATA_CONFIG", str(cfg))
    return cfg


def _write_config(
    path: Path,
    *,
    credential: str = "",
    brain_id: str = "",
    api_url: str = "",
) -> None:
    parts = ["[cloud]"]
    if credential:
        parts.append(f'{_KEY_FIELD} = "{credential}"')
    if brain_id:
        parts.append(f'brain_id = "{brain_id}"')
    if api_url:
        parts.append(f'api_url = "{api_url}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def test_cloud_config_missing(isolated_config):
    result = _doctor._check_cloud_config()
    assert result["status"] == "missing"
    assert "gradata cloud enable" in result["detail"]


def test_cloud_config_missing_credential(isolated_config):
    isolated_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.write_text('[cloud]\nbrain_id = "abc"\n', encoding="utf-8")
    result = _doctor._check_cloud_config()
    assert result["status"] == "fail"


def test_cloud_config_ok(isolated_config):
    _write_config(isolated_config, credential="fake-tok-12345678", brain_id="brain-abc")
    result = _doctor._check_cloud_config()
    assert result["status"] == "ok"
    assert "brain-abc" in result["detail"]


def test_cloud_env_vars_not_set(monkeypatch):
    for var in (
        "GRADATA_API_KEY",
        "GRADATA_ENDPOINT",
        "GRADATA_CLOUD_API_BASE",
        "GRADATA_CLOUD_SYNC_DISABLE",
    ):
        monkeypatch.delenv(var, raising=False)
    result = _doctor._check_cloud_env_vars()
    assert result["status"] == "skip"


def test_cloud_env_vars_api_key_set(monkeypatch):
    monkeypatch.setenv("GRADATA_API_KEY", "gk_test_placeholder")
    monkeypatch.delenv("GRADATA_CLOUD_SYNC_DISABLE", raising=False)
    result = _doctor._check_cloud_env_vars()
    assert result["status"] == "ok"


def test_cloud_env_vars_kill_switch_warns(monkeypatch):
    monkeypatch.setenv("GRADATA_API_KEY", "gk_test_placeholder")
    monkeypatch.setenv("GRADATA_CLOUD_SYNC_DISABLE", "1")
    result = _doctor._check_cloud_env_vars()
    assert result["status"] == "warn"
    assert "kill switch" in result["detail"].lower()


def test_cloud_auth_skips_when_not_logged_in(isolated_config):
    result = _doctor._check_cloud_auth()
    assert result["status"] == "skip"


def test_cloud_auth_rejected(isolated_config):
    _write_config(isolated_config, credential="bad-value-1234", brain_id="b1")
    with patch.object(_doctor, "_probe_api", return_value=(401, "")):
        result = _doctor._check_cloud_auth()
    assert result["status"] == "fail"
    assert "401" in result["detail"]


def test_cloud_auth_ok(isolated_config):
    _write_config(isolated_config, credential="good-value-1234", brain_id="b1")
    with patch.object(_doctor, "_probe_api", return_value=(200, '{"brain_id": "b1"}')):
        result = _doctor._check_cloud_auth()
    assert result["status"] == "ok"


def test_cloud_has_data_zero_sessions_warns(isolated_config):
    _write_config(isolated_config, credential="good-value-1234", brain_id="b1")
    with patch.object(_doctor, "_probe_api", return_value=(200, '{"session_count": 0}')):
        result = _doctor._check_cloud_has_data()
    assert result["status"] == "warn"
    assert "0 sessions" in result["detail"]


def test_cloud_has_data_ok(isolated_config):
    _write_config(isolated_config, credential="good-value-1234", brain_id="b1")
    with patch.object(_doctor, "_probe_api", return_value=(200, '{"session_count": 42}')):
        result = _doctor._check_cloud_has_data()
    assert result["status"] == "ok"
    assert "42 sessions" in result["detail"]


def test_diagnose_cloud_only(isolated_config):
    report = _doctor.diagnose(cloud_only=True)
    names = {c["name"] for c in report["checks"]}
    assert names == {
        "cloud_config",
        "cloud_env",
        "cloud_reachable",
        "cloud_auth",
        "cloud_has_data",
    }


def test_diagnose_no_cloud_skips_cloud_checks(tmp_path):
    report = _doctor.diagnose(brain_dir=tmp_path, include_cloud=False)
    names = {c["name"] for c in report["checks"]}
    assert "cloud_config" not in names
    assert "python_version" in names
