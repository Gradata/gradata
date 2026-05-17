"""Tests for the POST /sync endpoint on the local Gradata daemon.

The dashboard's Sync Now button POSTs to http://127.0.0.1:8765/sync — this
file pins the contract: it must read events past the watermark, push them
to the cloud, advance the watermark, and return {status, pushed, last_sync_at}.
"""

from __future__ import annotations

import io
import json
import sqlite3
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from gradata.daemon import (
    SYNC_WATERMARK_FILENAME,
    GradataDaemon,
    _build_sync_payload,
    _resolve_api_key,
)

if TYPE_CHECKING:
    from pathlib import Path


# ── Fixture: spin up a daemon with a brain that has events ────────────


@pytest.fixture
def daemon_with_events(brain_dir: Path):
    """Start a GradataDaemon with a brain DB pre-seeded with a few events."""
    from gradata._events import _ensure_table

    db_path = brain_dir / "system.db"
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_table(conn)
        conn.execute(
            "INSERT INTO events (ts, session, type, source, data_json, tags_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01T00:00:00Z",
                1,
                "CORRECTION",
                "pytest",
                json.dumps(
                    {
                        "description": "use commas not em dashes",
                        "category": "TONE",
                        "severity": "minor",
                    }
                ),
                "[]",
            ),
        )
        conn.execute(
            "INSERT INTO events (ts, session, type, source, data_json, tags_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01T00:01:00Z",
                1,
                "OUTPUT",
                "pytest",
                json.dumps({"output_type": "email"}),
                "[]",
            ),
        )
        conn.execute(
            "INSERT INTO events (ts, session, type, source, data_json, tags_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01T00:02:00Z",
                1,
                "correction",  # lowercase variant
                "pytest",
                json.dumps(
                    {
                        "description": "use commas not em dashes",  # dup desc
                        "category": "TONE",
                    }
                ),
                "[]",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    d = GradataDaemon(brain_dir, port=0, api_key="test-key-abc")
    d._try_bind(0)
    assert d._server is not None
    d._server._daemon = d  # type: ignore[attr-defined]
    actual_port = d._server.server_address[1]
    d._port = actual_port
    d._reset_idle_timer()

    t = threading.Thread(target=d._server.serve_forever, daemon=True)
    t.start()

    base = f"http://127.0.0.1:{actual_port}"
    yield base, d, brain_dir

    d._server.shutdown()


def _post(base_url: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """POST JSON to daemon, return (status, parsed_response)."""
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ── /sync happy path ──────────────────────────────────────────────────


def test_sync_pushes_events_and_advances_watermark(daemon_with_events) -> None:
    """POST /sync should push events, advance watermark, return ok shape."""
    base, _daemon, brain_dir = daemon_with_events

    captured: dict = {}

    def fake_cloud_post(url: str, body: bytes, api_key: str, timeout: float = 30.0) -> bytes:
        captured["url"] = url
        captured["body"] = body
        captured["api_key"] = api_key
        return json.dumps({"events_synced": 3, "corrections_synced": 1}).encode("utf-8")

    with patch("gradata.daemon._cloud_post", side_effect=fake_cloud_post):
        status, body = _post(base, "/sync")

    assert status == 200
    assert body["status"] == "ok"
    assert body["pushed"] == 4  # events_synced + corrections_synced
    assert body.get("last_sync_at")

    # Watermark advanced to last event id
    watermark_file = brain_dir / SYNC_WATERMARK_FILENAME
    assert watermark_file.exists()
    assert int(watermark_file.read_text(encoding="utf-8").strip()) == 3

    # Cloud was called once with the right shape
    assert captured["api_key"] == "test-key-abc"
    assert "api.gradata.ai" in captured["url"]
    sent_body = json.loads(captured["body"])
    assert "events" in sent_body
    assert "corrections" in sent_body
    assert "lessons" in sent_body
    assert "meta_rules" in sent_body
    assert len(sent_body["events"]) == 3
    # Dedup-by-(session, description): only one correction even though we
    # inserted two correction-type events with the same description.
    assert len(sent_body["corrections"]) == 1
    assert sent_body["corrections"][0]["severity"] == "minor"


def test_sync_with_no_events_returns_zero(brain_dir: Path) -> None:
    """POST /sync with empty brain returns pushed=0 and sends a heartbeat.

    PR #198 changed the empty-payload behavior: the daemon now POSTs an
    empty heartbeat to the cloud so brains.last_sync_at advances even
    when there's nothing new to push. Cloud failures during the
    heartbeat are non-fatal (logged at info, not surfaced to caller).
    """
    from gradata._events import _ensure_table

    db_path = brain_dir / "system.db"
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_table(conn)
        conn.commit()
    finally:
        conn.close()

    d = GradataDaemon(brain_dir, port=0, api_key="test-key")
    d._try_bind(0)
    assert d._server is not None
    d._server._daemon = d  # type: ignore[attr-defined]
    actual_port = d._server.server_address[1]
    d._reset_idle_timer()

    t = threading.Thread(target=d._server.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{actual_port}"

    try:
        with patch("gradata.daemon._cloud_post") as mock_post:
            mock_post.return_value = b'{"events_synced":0,"corrections_synced":0}'
            status, body = _post(base, "/sync")
        assert status == 200
        assert body["status"] == "ok"
        assert body["pushed"] == 0
        assert "last_sync_at" in body
        # PR #198 heartbeat: empty payload still POSTs to cloud so
        # brains.last_sync_at advances. Exactly one call expected.
        assert mock_post.call_count == 1, (
            f"empty-sync should POST one heartbeat, got {mock_post.call_count}"
        )
    finally:
        d._server.shutdown()


# ── /sync error cases ─────────────────────────────────────────────────


def test_sync_returns_502_on_cloud_http_error(daemon_with_events) -> None:
    """When the cloud rejects with HTTP 500, daemon returns 502 status=error."""
    base, _daemon, brain_dir = daemon_with_events

    err = urllib.error.HTTPError(
        url="https://api.gradata.ai/api/v1/sync",
        code=500,
        msg="Internal Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error":"db down"}'),
    )

    with patch("gradata.daemon._cloud_post", side_effect=err):
        status, body = _post(base, "/sync")

    assert status == 502
    assert body["status"] == "error"
    assert "cloud HTTP 500" in body["error"]

    # Watermark should NOT have advanced
    watermark_file = brain_dir / SYNC_WATERMARK_FILENAME
    assert not watermark_file.exists()


def test_sync_returns_502_on_network_error(daemon_with_events) -> None:
    """When DNS/connection fails, daemon returns 502."""
    base, _daemon, brain_dir = daemon_with_events

    with patch(
        "gradata.daemon._cloud_post",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        status, body = _post(base, "/sync")

    assert status == 502
    assert body["status"] == "error"
    assert "network error" in body["error"]
    assert not (brain_dir / SYNC_WATERMARK_FILENAME).exists()


def test_sync_returns_502_when_no_api_key(brain_dir: Path, monkeypatch) -> None:
    """No api_key, no env, no key file → 502 with helpful error."""
    from gradata._events import _ensure_table

    db_path = brain_dir / "system.db"
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_table(conn)
        conn.execute(
            "INSERT INTO events (ts, session, type, source, data_json, tags_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("2024-01-01T00:00:00Z", 1, "OUTPUT", "pytest", "{}", "[]"),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.delenv("GRADATA_API_KEY", raising=False)

    # Point ~/.gradata/key into a non-existent dir so it's not picked up
    fake_home = brain_dir / "fakehome"
    fake_home.mkdir()

    d = GradataDaemon(brain_dir, port=0, api_key=None)
    d._try_bind(0)
    assert d._server is not None
    d._server._daemon = d  # type: ignore[attr-defined]
    actual_port = d._server.server_address[1]
    d._reset_idle_timer()

    t = threading.Thread(target=d._server.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{actual_port}"

    try:
        with patch("gradata.daemon.Path.home", return_value=fake_home):
            status, body = _post(base, "/sync")
        assert status == 502
        assert body["status"] == "error"
        assert "API key" in body["error"]
    finally:
        d._server.shutdown()


# ── CORS ───────────────────────────────────────────────────────────────


def test_sync_options_preflight(daemon_with_events) -> None:
    """OPTIONS /sync must respond 204 with CORS headers (browser preflight)."""
    base, _d, _bd = daemon_with_events
    req = urllib.request.Request(f"{base}/sync", method="OPTIONS")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        allow_methods = resp.headers.get("Access-Control-Allow-Methods", "")
        assert "POST" in allow_methods
        assert "OPTIONS" in allow_methods


def test_sync_post_has_cors_headers(daemon_with_events) -> None:
    """POST /sync response must include Access-Control-Allow-Origin."""
    base, _d, _bd = daemon_with_events

    with patch("gradata.daemon._cloud_post", return_value=b"{}"):
        req = urllib.request.Request(
            f"{base}/sync",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ── _build_sync_payload / _resolve_api_key direct unit tests ──────────


def test_build_sync_payload_normalizes_severity_and_dedupes() -> None:
    """Bad severity → minor, dup (session, description) → dropped."""

    # Fake rows as dicts (sqlite3.Row is dict-like enough via dict(row))
    class _Row(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)

    rows = [
        _Row(
            id=1,
            type="CORRECTION",
            source="x",
            data_json=json.dumps(
                {
                    "description": "be concise",
                    "category": "TONE",
                    "severity": "WHATEVER",
                }
            ),
            tags_json="[]",
            session=1,
            event_id=None,
        ),
        _Row(
            id=2,
            type="correction",
            source="x",
            data_json=json.dumps({"description": "be concise", "category": "TONE"}),
            tags_json="[]",
            session=1,
            event_id=None,
        ),
        _Row(
            id=3,
            type="correction",
            source="x",
            data_json=json.dumps(
                {
                    "description": "be concise",
                    "category": "TONE",
                    "severity": "major",
                }
            ),
            tags_json="[]",
            session=2,  # different session → not a dup
            event_id=None,
        ),
    ]

    events, corrections = _build_sync_payload(rows)
    assert len(events) == 3
    # session=1 dup is dropped; session=2 kept
    assert len(corrections) == 2
    assert corrections[0]["severity"] == "minor"  # WHATEVER normalised
    assert corrections[1]["severity"] == "major"


def test_resolve_api_key_priority(monkeypatch, tmp_path: Path) -> None:
    """Explicit arg > env > ~/.gradata/key."""
    monkeypatch.setenv("GRADATA_API_KEY", "from-env")
    fake_home = tmp_path / "home"
    (fake_home / ".gradata").mkdir(parents=True)
    (fake_home / ".gradata" / "key").write_text("from-file", encoding="utf-8")

    with patch("gradata.daemon.Path.home", return_value=fake_home):
        # explicit beats everything
        assert _resolve_api_key("explicit") == "explicit"
        # env beats file
        assert _resolve_api_key(None) == "from-env"

    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    with patch("gradata.daemon.Path.home", return_value=fake_home):
        assert _resolve_api_key(None) == "from-file"

    # Missing everywhere
    empty_home = tmp_path / "empty"
    empty_home.mkdir()
    with patch("gradata.daemon.Path.home", return_value=empty_home):
        assert _resolve_api_key(None) is None
