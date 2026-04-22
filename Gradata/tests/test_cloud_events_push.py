"""Tests for gradata.cloud.push — events/push client.

Covers: happy path, watermark advancement, disabled/kill-switch/no-credential
short-circuits, 4xx fatal, 5xx retried-then-failed, resume from watermark,
chunked batching across multiple POSTs.
"""

from __future__ import annotations

import io
import json
import sqlite3
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from gradata.cloud import _credentials as _creds
from gradata.cloud import push as push_mod
from gradata.cloud.sync import CloudConfig, save_config


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Rebind keyfile + clean env for every test."""
    monkeypatch.setattr(_creds, "KEYFILE_DIR", tmp_path / ".gradata")
    monkeypatch.setattr(_creds, "KEYFILE_PATH", tmp_path / ".gradata" / "key")
    for v in (
        "GRADATA_API_KEY",
        "GRADATA_CLOUD_SYNC_DISABLE",
        "GRADATA_CLOUD_SYNC",
        "GRADATA_CLOUD_URL",
        "GRADATA_CLOUD_KEY",
    ):
        monkeypatch.delenv(v, raising=False)
    yield


def _make_brain(
    tmp_path: Path,
    *,
    enabled: bool = True,
    token: str = "gk_live_testkey_1234567890",
    api_base: str = "https://api.example.com",
    events: list[dict[str, Any]] | None = None,
    watermark: str | None = None,
    tenant_id: str = "11111111-2222-3333-4444-555555555555",
    device_id: str = "dev_" + "a" * 32,
) -> Path:
    """Materialize a brain dir with cloud-config, tenant/device, and events rows."""
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / ".tenant_id").write_text(tenant_id, encoding="utf-8")
    (brain / ".device_id").write_text(device_id, encoding="utf-8")
    save_config(
        brain,
        CloudConfig(sync_enabled=enabled, token=token, api_base=api_base),
    )

    conn = sqlite3.connect(brain / "system.db")
    conn.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            type TEXT,
            source TEXT,
            session INTEGER,
            ts TEXT,
            data_json TEXT,
            tags_json TEXT,
            device_id TEXT,
            content_hash TEXT,
            correction_chain_id TEXT,
            origin_agent TEXT,
            tenant_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sync_state (
            brain_id TEXT PRIMARY KEY,
            last_push_at TEXT,
            updated_at TEXT,
            device_id TEXT,
            last_push_event_id TEXT,
            last_pull_cursor TEXT,
            tenant_id TEXT
        )
        """
    )
    for ev in events or []:
        conn.execute(
            """
            INSERT INTO events (event_id, type, source, session, ts, data_json,
                                tags_json, device_id, content_hash, tenant_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev["event_id"],
                ev.get("type", "CORRECTION"),
                ev.get("source", "test"),
                ev.get("session", 1),
                ev.get("ts", "2026-04-21T00:00:00+00:00"),
                json.dumps(ev.get("data", {})),
                json.dumps(ev.get("tags", [])),
                device_id,
                ev.get("content_hash", "h" * 64),
                tenant_id,
            ),
        )
    if watermark:
        conn.execute(
            """
            INSERT INTO sync_state (brain_id, device_id, tenant_id,
                                    last_push_event_id, last_push_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                device_id,
                tenant_id,
                watermark,
                "2026-04-20T00:00:00+00:00",
                "2026-04-20T00:00:00+00:00",
            ),
        )
    conn.commit()
    conn.close()
    return brain


class _FakeResp:
    # Default to an empty JSON body so callers that don't assert partial-
    # acceptance semantics don't accidentally signal "accepted=0 of N". The
    # push client treats a missing ``accepted`` key as "server didn't report
    # counts; trust the 2xx", which matches pre-0.7.0 server behavior.
    def __init__(self, body: bytes = b"{}"):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_no_db_returns_error(tmp_path):
    summary = push_mod.push_pending_events(tmp_path)
    assert summary["status"] == "error"
    assert summary["reason"] == "no_db"


def test_kill_switch_short_circuits(tmp_path, monkeypatch):
    brain = _make_brain(tmp_path)
    monkeypatch.setenv("GRADATA_CLOUD_SYNC_DISABLE", "1")
    summary = push_mod.push_pending_events(brain)
    assert summary["status"] == "kill_switch"
    assert summary["events_pushed"] == 0


def test_disabled_by_config(tmp_path):
    brain = _make_brain(tmp_path, enabled=False)
    summary = push_mod.push_pending_events(brain)
    assert summary["status"] == "disabled"


def test_no_credential(tmp_path):
    brain = _make_brain(tmp_path, token="")
    summary = push_mod.push_pending_events(brain)
    assert summary["status"] == "no_credential"


def test_non_https_api_base_rejected(tmp_path):
    brain = _make_brain(tmp_path, api_base="http://api.example.com")
    summary = push_mod.push_pending_events(brain)
    assert summary["status"] == "error"
    assert summary["reason"] == "https_required"


def test_happy_path_pushes_events_and_advances_watermark(tmp_path, monkeypatch):
    events = [
        {"event_id": "01HN000000000000000000000A"},
        {"event_id": "01HN000000000000000000000B"},
        {"event_id": "01HN000000000000000000000C"},
    ]
    brain = _make_brain(tmp_path, events=events)

    captured: list[dict] = []

    def fake_urlopen(req, timeout):  # noqa: ARG001
        body = json.loads(req.data.decode("utf-8"))
        captured.append(body)
        return _FakeResp(b'{"accepted": 3, "rejected": []}')

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    summary = push_mod.push_pending_events(brain)

    assert summary["status"] == "ok"
    assert summary["events_pushed"] == 3
    assert summary["batches"] == 1
    assert summary["last_event_id"] == "01HN000000000000000000000C"
    assert len(captured) == 1
    assert captured[0]["device_id"].startswith("dev_")
    assert len(captured[0]["events"]) == 3

    conn = sqlite3.connect(brain / "system.db")
    wm = conn.execute("SELECT last_push_event_id FROM sync_state").fetchone()
    conn.close()
    assert wm[0] == "01HN000000000000000000000C"


def test_resume_from_watermark_skips_already_pushed(tmp_path, monkeypatch):
    events = [
        {"event_id": "01HN000000000000000000000A"},
        {"event_id": "01HN000000000000000000000B"},
        {"event_id": "01HN000000000000000000000C"},
    ]
    brain = _make_brain(tmp_path, events=events, watermark="01HN000000000000000000000A")

    captured: list[dict] = []

    def fake_urlopen(req, timeout):  # noqa: ARG001
        captured.append(json.loads(req.data.decode("utf-8")))
        return _FakeResp()

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    summary = push_mod.push_pending_events(brain)

    assert summary["events_pushed"] == 2
    assert captured[0]["events"][0]["event_id"] == "01HN000000000000000000000B"


def test_chunked_batching_multiple_posts(tmp_path, monkeypatch):
    events = [{"event_id": f"01HN00000000000000000000{i:02X}"} for i in range(5)]
    brain = _make_brain(tmp_path, events=events)

    posts: list[int] = []

    def fake_urlopen(req, timeout):  # noqa: ARG001
        body = json.loads(req.data.decode("utf-8"))
        posts.append(len(body["events"]))
        return _FakeResp()

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    summary = push_mod.push_pending_events(brain, chunk_size=2)

    assert summary["status"] == "ok"
    assert summary["events_pushed"] == 5
    assert summary["batches"] == 3
    assert posts == [2, 2, 1]


def test_4xx_is_fatal_no_retry(tmp_path, monkeypatch):
    events = [{"event_id": "01HN000000000000000000000A"}]
    brain = _make_brain(tmp_path, events=events)

    calls = {"n": 0}

    def fake_urlopen(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 400, "Bad Request", hdrs=None, fp=io.BytesIO(b"")
        )

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    # Neutralize sleep so test is fast even if a retry slipped through.
    monkeypatch.setattr(push_mod.time, "sleep", lambda *_a, **_k: None)
    summary = push_mod.push_pending_events(brain, max_retries=3)

    assert summary["status"] == "error"
    assert summary["reason"] == "batch_failed_after_retries"
    assert calls["n"] == 1  # 4xx must not retry


def test_5xx_retried_then_fails(tmp_path, monkeypatch):
    events = [{"event_id": "01HN000000000000000000000A"}]
    brain = _make_brain(tmp_path, events=events)

    calls = {"n": 0}

    def fake_urlopen(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        raise urllib.error.HTTPError(
            req.full_url, 503, "Service Unavailable", hdrs=None, fp=io.BytesIO(b"")
        )

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(push_mod.time, "sleep", lambda *_a, **_k: None)
    summary = push_mod.push_pending_events(brain, max_retries=2)

    assert summary["status"] == "error"
    assert summary["reason"] == "batch_failed_after_retries"
    assert calls["n"] == 3  # 1 initial + 2 retries


def test_5xx_then_success_within_retries(tmp_path, monkeypatch):
    events = [{"event_id": "01HN000000000000000000000A"}]
    brain = _make_brain(tmp_path, events=events)

    calls = {"n": 0}

    def fake_urlopen(req, timeout):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] < 2:
            raise urllib.error.HTTPError(
                req.full_url, 502, "Bad Gateway", hdrs=None, fp=io.BytesIO(b"")
            )
        return _FakeResp()

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(push_mod.time, "sleep", lambda *_a, **_k: None)
    summary = push_mod.push_pending_events(brain, max_retries=3)

    assert summary["status"] == "ok"
    assert summary["events_pushed"] == 1


def test_credential_resolves_from_keyfile_when_config_token_empty(tmp_path, monkeypatch):
    events = [{"event_id": "01HN000000000000000000000A"}]
    brain = _make_brain(tmp_path, token="", events=events)
    _creds.write_to_keyfile("gk_live_fromkeyfile_000000")

    captured: list[dict[str, Any]] = []

    def fake_urlopen(req, timeout):  # noqa: ARG001
        captured.append({"auth": req.headers.get("Authorization")})
        return _FakeResp()

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    summary = push_mod.push_pending_events(brain)

    assert summary["status"] == "ok"
    assert captured[0]["auth"] == "Bearer gk_live_fromkeyfile_000000"


def test_empty_events_table_returns_ok_noop(tmp_path, monkeypatch):
    brain = _make_brain(tmp_path, events=[])

    def fake_urlopen(req, timeout):  # noqa: ARG001
        raise AssertionError("should not POST when no events")

    monkeypatch.setattr(push_mod.urllib.request, "urlopen", fake_urlopen)
    summary = push_mod.push_pending_events(brain)
    assert summary["status"] == "ok"
    assert summary["events_pushed"] == 0
    assert summary["batches"] == 0
