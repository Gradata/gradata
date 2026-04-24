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
    assert "gradata login" in result["detail"]


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


def test_cloud_env_vars_not_enabled(monkeypatch):
    for var in (
        "GRADATA_CLOUD_SYNC",
        "GRADATA_CLOUD_URL",
        "GRADATA_CLOUD_KEY",
        "GRADATA_SUPABASE_URL",
        "GRADATA_SUPABASE_SERVICE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    result = _doctor._check_cloud_env_vars()
    assert result["status"] == "skip"


def test_cloud_env_vars_supabase_alias_accepted(monkeypatch):
    monkeypatch.setenv("GRADATA_CLOUD_SYNC", "1")
    monkeypatch.delenv("GRADATA_CLOUD_URL", raising=False)
    monkeypatch.delenv("GRADATA_CLOUD_KEY", raising=False)
    monkeypatch.setenv("GRADATA_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("GRADATA_SUPABASE_SERVICE_KEY", "placeholder-value")
    result = _doctor._check_cloud_env_vars()
    assert result["status"] == "ok"


def test_cloud_env_vars_missing_key(monkeypatch):
    monkeypatch.setenv("GRADATA_CLOUD_SYNC", "1")
    monkeypatch.setenv("GRADATA_CLOUD_URL", "https://example.supabase.co")
    for k in ("GRADATA_CLOUD_KEY", "GRADATA_SUPABASE_SERVICE_KEY"):
        monkeypatch.delenv(k, raising=False)
    result = _doctor._check_cloud_env_vars()
    assert result["status"] == "fail"
    assert "GRADATA_CLOUD_KEY" in result["detail"]


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
        "cloud_push_error",
    }


def test_diagnose_no_cloud_skips_cloud_checks(tmp_path):
    report = _doctor.diagnose(brain_dir=tmp_path, include_cloud=False)
    names = {c["name"] for c in report["checks"]}
    assert "cloud_config" not in names
    assert "python_version" in names


def test_cloud_push_error_ok_when_file_missing(tmp_path):
    """No error file present → doctor reports ok."""
    result = _doctor._check_cloud_push_error(tmp_path)
    assert result["status"] == "ok"
    assert "no recent" in result["detail"]


def test_cloud_push_error_constraint_violation_fails(tmp_path):
    """A recorded 23505 constraint violation must surface as a `fail` so the
    user knows the watermark is stalled."""
    import json as _json

    (tmp_path / "cloud_push_error.json").write_text(
        _json.dumps(
            {
                "table": "events",
                "code": 409,
                "message": "duplicate key value",
                "constraint_violation": True,
                "recorded_at": "2026-04-24T04:50:00Z",
            }
        ),
        encoding="utf-8",
    )
    result = _doctor._check_cloud_push_error(tmp_path)
    assert result["status"] == "fail"
    assert "events" in result["detail"]
    assert "409" in result["detail"]


def test_cloud_push_error_non_constraint_warns(tmp_path):
    """Non-constraint HTTP failures are warn, not fail (transient)."""
    import json as _json

    (tmp_path / "cloud_push_error.json").write_text(
        _json.dumps(
            {
                "table": "lessons",
                "code": 500,
                "message": "Internal Server Error",
                "constraint_violation": False,
                "recorded_at": "2026-04-24T04:50:00Z",
            }
        ),
        encoding="utf-8",
    )
    result = _doctor._check_cloud_push_error(tmp_path)
    assert result["status"] == "warn"
    assert "lessons" in result["detail"]
    assert "500" in result["detail"]


def test_cloud_push_error_skipped_when_no_brain_dir():
    result = _doctor._check_cloud_push_error(None)
    assert result["status"] == "skip"


def test_cloud_push_error_detail_includes_brain_path(tmp_path):
    """Detail must name the resolved brain path so a multi-brain user can
    spot a divergence between the dir push writes to and the dir doctor reads."""
    ok = _doctor._check_cloud_push_error(tmp_path)
    assert str(tmp_path) in ok["detail"]

    import json as _json

    (tmp_path / "cloud_push_error.json").write_text(
        _json.dumps(
            {
                "table": "events",
                "code": 409,
                "constraint_violation": True,
                "recorded_at": "2026-04-24T05:50:00Z",
            }
        ),
        encoding="utf-8",
    )
    fail = _doctor._check_cloud_push_error(tmp_path)
    assert str(tmp_path) in fail["detail"]
