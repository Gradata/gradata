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


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _graduation_body(watermark: str = "01JN000000001") -> bytes:
    """Realistic 200 payload: one PATTERN graduation for 'style / use active voice'."""
    return json.dumps(
        {
            "events": [
                {
                    "event_id": "01JN0000000001",
                    "ts": "2026-04-20T00:00:00Z",
                    "type": "RULE_GRADUATED",
                    "source": "graduate",
                    "data": {
                        "category": "style",
                        "description": "use active voice",
                        "new_state": "PATTERN",
                        "confidence": 0.62,
                        "fire_count": 3,
                        "device_id": "dev_remote",
                    },
                }
            ],
            "watermark": watermark,
            "end_of_stream": True,
        }
    ).encode()


def test_server_200_dry_run_materializes_without_writing(brain):
    """Default apply=False: summary shows counts; lessons.md untouched."""
    _save_cfg(brain.dir)
    lessons_md = brain.dir / "lessons.md"
    before = lessons_md.read_text(encoding="utf-8") if lessons_md.is_file() else None

    with patch("urllib.request.urlopen", return_value=_FakeResp(_graduation_body())):
        result = pull_events(brain.dir)

    assert result["status"] == "ok"
    assert result["events_pulled"] == 1
    assert result["rules_materialized"] == 1
    assert result["applied"] is False
    after = lessons_md.read_text(encoding="utf-8") if lessons_md.is_file() else None
    assert after == before  # no mutation


def test_server_200_apply_writes_lessons(brain):
    """apply=True merges materialized state into lessons.md."""
    _save_cfg(brain.dir)

    with patch("urllib.request.urlopen", return_value=_FakeResp(_graduation_body())):
        result = pull_events(brain.dir, apply=True)

    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["conflicts"] == 0
    assert result["conflict_events_emitted"] == 0

    lessons_md = brain.dir / "lessons.md"
    assert lessons_md.is_file()
    text = lessons_md.read_text(encoding="utf-8")
    assert "use active voice" in text


def test_apply_persists_pull_watermark(brain):
    """After a successful apply, sync_state.last_pull_cursor records the watermark."""
    from gradata._migrations.device_uuid import get_or_create_device_id
    from gradata._tenant import tenant_for
    from gradata.cloud._sync_state import get_pull_cursor

    _save_cfg(brain.dir)
    with patch(
        "urllib.request.urlopen",
        return_value=_FakeResp(_graduation_body(watermark="01JN_RESUME_ME")),
    ):
        result = pull_events(brain.dir, apply=True)

    assert result["applied"] is True
    persisted = get_pull_cursor(
        brain.dir / "system.db",
        tenant_id=tenant_for(brain.dir),
        device_id=get_or_create_device_id(brain.dir),
    )
    assert persisted == "01JN_RESUME_ME"


def test_server_200_malformed_json_returns_error(brain):
    _save_cfg(brain.dir)

    with patch("urllib.request.urlopen", return_value=_FakeResp(b"not json")):
        result = pull_events(brain.dir)

    assert result["status"] == "error"
    assert result["reason"] == "malformed_response"


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


def test_pull_uses_persisted_watermark_when_rebuild_from_absent(brain):
    """Second call without rebuild_from picks up the watermark left by the first."""
    import urllib.error

    from gradata._migrations.device_uuid import get_or_create_device_id
    from gradata._tenant import tenant_for
    from gradata.cloud._sync_state import update_pull_cursor

    _save_cfg(brain.dir)
    # Seed a persisted watermark as though a prior apply had succeeded.
    update_pull_cursor(
        brain.dir / "system.db",
        tenant_id=tenant_for(brain.dir),
        device_id=get_or_create_device_id(brain.dir),
        cursor="01JN_PRIOR_WATERMARK",
    )

    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        raise urllib.error.HTTPError(req.full_url, 501, "Not Implemented", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        pull_events(brain.dir)

    assert "cursor=01JN_PRIOR_WATERMARK" in captured["url"]
    # rebuild_from must NOT be sent — only cursor.
    assert "rebuild_from=" not in captured["url"]


def test_explicit_rebuild_from_overrides_persisted_watermark(brain):
    """An explicit rebuild_from takes precedence over any persisted cursor."""
    import urllib.error

    from gradata._migrations.device_uuid import get_or_create_device_id
    from gradata._tenant import tenant_for
    from gradata.cloud._sync_state import update_pull_cursor

    _save_cfg(brain.dir)
    update_pull_cursor(
        brain.dir / "system.db",
        tenant_id=tenant_for(brain.dir),
        device_id=get_or_create_device_id(brain.dir),
        cursor="01JN_PRIOR_WATERMARK",
    )

    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        raise urllib.error.HTTPError(req.full_url, 501, "Not Implemented", {}, None)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        pull_events(brain.dir, rebuild_from="01JN_EXPLICIT")

    assert "rebuild_from=01JN_EXPLICIT" in captured["url"]
    # Persisted watermark must not smuggle in as cursor when rebuilding.
    assert "cursor=01JN_PRIOR_WATERMARK" not in captured["url"]


def test_pagination_drains_until_end_of_stream(brain):
    """Server returns end_of_stream=False then True — client keeps asking."""
    _save_cfg(brain.dir)

    page_one = json.dumps(
        {
            "events": [
                {
                    "event_id": "01JN_P1_E1",
                    "ts": "2026-04-20T00:00:00Z",
                    "type": "RULE_GRADUATED",
                    "source": "graduate",
                    "data": {
                        "category": "style",
                        "description": "use active voice",
                        "new_state": "PATTERN",
                        "confidence": 0.62,
                        "fire_count": 3,
                        "device_id": "dev_a",
                    },
                }
            ],
            "watermark": "01JN_PAGE1",
            "end_of_stream": False,
        }
    ).encode()
    page_two = json.dumps(
        {
            "events": [
                {
                    "event_id": "01JN_P2_E1",
                    "ts": "2026-04-20T00:01:00Z",
                    "type": "RULE_GRADUATED",
                    "source": "graduate",
                    "data": {
                        "category": "structure",
                        "description": "headings before prose",
                        "new_state": "PATTERN",
                        "confidence": 0.70,
                        "fire_count": 4,
                        "device_id": "dev_a",
                    },
                }
            ],
            "watermark": "01JN_PAGE2",
            "end_of_stream": True,
        }
    ).encode()

    responses = [_FakeResp(page_one), _FakeResp(page_two)]
    urls_seen: list[str] = []

    def fake_urlopen(req, timeout=None):
        urls_seen.append(req.full_url)
        return responses.pop(0)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = pull_events(brain.dir, apply=True)

    assert result["status"] == "ok"
    assert result["events_pulled"] == 2
    assert result["pages_fetched"] == 2
    assert result["end_of_stream"] is True
    assert result["watermark"] == "01JN_PAGE2"
    # Second request carries the page-one watermark as cursor.
    assert "cursor=01JN_PAGE1" in urls_seen[1]
    # First request has no cursor yet.
    assert "cursor=" not in urls_seen[0]


def test_pagination_stops_if_server_omits_watermark(brain):
    """Defensive: end_of_stream=False without a watermark must not spin."""
    _save_cfg(brain.dir)

    bad_page = json.dumps({"events": [], "watermark": None, "end_of_stream": False}).encode()

    call_count = {"n": 0}

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        return _FakeResp(bad_page)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = pull_events(brain.dir)

    assert call_count["n"] == 1  # stopped after the first page
    assert result["status"] == "ok"
    assert result["pages_fetched"] == 1


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
