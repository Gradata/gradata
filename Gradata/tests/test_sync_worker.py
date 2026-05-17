"""Tests for :class:`gradata._sync_worker.SyncWorker` (#194 day 3).

The worker drains rows from the local ``sync_queue`` table by POSTing
each payload to the cloud ``/api/v1/ingest`` endpoint. These tests
spin up a tiny stub HTTP server (same pattern as ``test_daemon_sync``)
to assert on the exact requests and exercise the failure modes:

* 200 → mark_synced (queue empties)
* 200 + ``deduplicated=true`` body → still mark_synced
* 500 → mark_failed, row stays pending for next tick
* 429 → mark_failed and bail (don't process the rest of the batch)
* permanent 4xx (e.g. 422) → mark_synced (poison row, no infinite retry)
* network error → mark_failed, retry next tick
* stop(drain=True) flushes pending in one final synchronous tick
* at-least-once: mark_synced failure → row remains pending → next tick retries
"""

from __future__ import annotations

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from unittest.mock import patch

import pytest

from gradata import _sync_queue
from gradata._migrations import _BASE_TABLES, _MIGRATIONS
from gradata._sync_worker import SyncWorker


# ── shared helpers ────────────────────────────────────────────────────


def _seed_db(db_path) -> None:
    """Create a system.db with only the sync_queue schema applied."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        for sql in _BASE_TABLES:
            if "sync_queue" in sql:
                conn.execute(sql)
        for sql in _MIGRATIONS:
            if "sync_queue" in sql:
                conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _open(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── stub /ingest HTTP server ──────────────────────────────────────────


class _StubIngestServer:
    """Tiny in-process HTTP server that records POSTs to /api/v1/ingest."""

    def __init__(self, response_fn) -> None:
        self.response_fn = response_fn
        self.requests: list[dict[str, Any]] = []
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kwargs) -> None:  # silence
                return

            def do_POST(self) -> None:  # noqa: N802 — stdlib API
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b""
                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    payload = {"_raw": body.decode("utf-8", errors="replace")}
                outer.requests.append(
                    {
                        "path": self.path,
                        "auth": self.headers.get("Authorization", ""),
                        "payload": payload,
                    }
                )
                status, resp = outer.response_fn(payload, len(outer.requests))
                resp_body = json.dumps(resp).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{port}/api/v1/ingest"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


@pytest.fixture
def stub_ingest():
    """Yield a factory that starts a stub /ingest server with a custom responder."""
    started: list[_StubIngestServer] = []

    def _factory(response_fn):
        s = _StubIngestServer(response_fn)
        url = s.start()
        started.append(s)
        return s, url

    yield _factory

    for s in started:
        s.stop()


# ── happy path ────────────────────────────────────────────────────────


def test_worker_drains_queue_on_200(tmp_path, stub_ingest):
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        for i in range(3):
            _sync_queue.enqueue_correction(
                conn,
                brain_id="brain-x",
                correction={"session": 1, "description": f"row {i}"},
                event_id=f"e-{i}",
            )
    finally:
        conn.close()

    server, url = stub_ingest(lambda _p, _n: (200, {"ok": True}))

    worker = SyncWorker(tmp_path, api_key="test-key", ingest_url=url, tick_sec=999)
    worker._tick()

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    assert pending == []

    assert len(server.requests) == 3
    # All requests carry the bearer token and the IngestRequest shape.
    for req in server.requests:
        assert req["path"].endswith("/api/v1/ingest")
        assert req["auth"] == "Bearer test-key"
        assert req["payload"]["brain_id"] == "brain-x"
        assert "correction" in req["payload"]
        assert req["payload"]["event_id"] in {"e-0", "e-1", "e-2"}


def test_worker_marks_synced_on_deduplicated_response(tmp_path, stub_ingest):
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        _sync_queue.enqueue_correction(conn, brain_id="b", correction={"x": 1}, event_id="dup")
    finally:
        conn.close()

    _server, url = stub_ingest(lambda _p, _n: (200, {"status": "ok", "deduplicated": True}))

    worker = SyncWorker(tmp_path, api_key="k", ingest_url=url, tick_sec=999)
    worker._tick()

    conn = _open(db_path)
    try:
        assert _sync_queue.peek_pending(conn) == []
    finally:
        conn.close()


# ── failure modes ────────────────────────────────────────────────────


def test_worker_marks_failed_on_500_and_row_stays_pending(tmp_path, stub_ingest):
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        _sync_queue.enqueue_correction(conn, brain_id="b", correction={"x": 1}, event_id="e1")
    finally:
        conn.close()

    _server, url = stub_ingest(lambda _p, _n: (500, {"error": "db down"}))

    worker = SyncWorker(tmp_path, api_key="k", ingest_url=url, tick_sec=999)
    worker._tick()

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    assert len(pending) == 1
    assert pending[0]["attempts"] == 1
    # A second tick retries (still pending after failure).
    worker._tick()
    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    assert len(pending) == 1
    assert pending[0]["attempts"] == 2


def test_worker_429_stops_tick_and_marks_failed(tmp_path, stub_ingest):
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        for i in range(3):
            _sync_queue.enqueue_correction(
                conn, brain_id="b", correction={"i": i}, event_id=f"e{i}"
            )
    finally:
        conn.close()

    _server, url = stub_ingest(lambda _p, _n: (429, {"error": "rate limited"}))

    worker = SyncWorker(tmp_path, api_key="k", ingest_url=url, tick_sec=999)
    worker._tick()

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    # All three still pending — 429 bails on the first row.
    assert len(pending) == 3
    # First row recorded the 429 failure, the rest are untouched.
    attempts = sorted(r["attempts"] for r in pending)
    assert attempts == [0, 0, 1]


def test_worker_422_is_permanent_and_marks_synced(tmp_path, stub_ingest):
    """422 means the payload is rejected — don't retry forever."""
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        _sync_queue.enqueue_correction(conn, brain_id="b", correction={"bad": True}, event_id="e1")
    finally:
        conn.close()

    _server, url = stub_ingest(lambda _p, _n: (422, {"error": "validation"}))

    worker = SyncWorker(tmp_path, api_key="k", ingest_url=url, tick_sec=999)
    worker._tick()

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
        row = conn.execute("SELECT synced_at, last_error FROM sync_queue").fetchone()
    finally:
        conn.close()
    assert pending == []  # not pending — won't retry
    assert row["synced_at"] is not None
    assert "permanent" in (row["last_error"] or "")


def test_worker_network_error_marks_failed(tmp_path):
    """Unreachable URL → mark_failed (transient, retry next tick)."""
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        _sync_queue.enqueue_correction(conn, brain_id="b", correction={"x": 1}, event_id="e1")
    finally:
        conn.close()

    # Port 1 is reserved → connection refused.
    bogus = "http://127.0.0.1:1/api/v1/ingest"
    worker = SyncWorker(tmp_path, api_key="k", ingest_url=bogus, tick_sec=999)
    worker._tick()

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    assert len(pending) == 1
    assert pending[0]["attempts"] == 1


# ── lifecycle ────────────────────────────────────────────────────────


def test_stop_with_drain_flushes_pending(tmp_path, stub_ingest):
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        _sync_queue.enqueue_correction(conn, brain_id="b", correction={"x": 1}, event_id="e1")
    finally:
        conn.close()

    _server, url = stub_ingest(lambda _p, _n: (200, {"ok": True}))

    # Long tick — the worker would not naturally drain in time.
    worker = SyncWorker(tmp_path, api_key="k", ingest_url=url, tick_sec=999)
    worker.start()
    try:
        worker.stop(drain=True)
    finally:
        # idempotent — calling again must not throw
        worker.stop(drain=False)

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    assert pending == []


def test_worker_noop_when_db_missing(tmp_path):
    """If system.db doesn't exist (no Brain there), _tick is a no-op."""
    worker = SyncWorker(tmp_path / "nope", api_key="k", ingest_url="http://x")
    # Should not raise.
    worker._tick()


# ── at-least-once ────────────────────────────────────────────────────


def test_at_least_once_when_mark_synced_fails(tmp_path, stub_ingest):
    """If /ingest returns 200 but mark_synced raises, the row stays pending."""
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    conn = _open(db_path)
    try:
        _sync_queue.enqueue_correction(conn, brain_id="b", correction={"x": 1}, event_id="e1")
    finally:
        conn.close()

    _server, url = stub_ingest(lambda _p, _n: (200, {"ok": True}))

    worker = SyncWorker(tmp_path, api_key="k", ingest_url=url, tick_sec=999)

    real_mark_synced = _sync_queue.mark_synced
    call_count = {"n": 0}

    def flaky_mark_synced(conn, ids):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise sqlite3.OperationalError("simulated db lock")
        return real_mark_synced(conn, ids)

    with patch("gradata._sync_worker._sync_queue.mark_synced", side_effect=flaky_mark_synced):
        with pytest.raises(sqlite3.OperationalError):
            worker._tick()

        # Still pending — at-least-once guarantee preserved.
        conn = _open(db_path)
        try:
            pending = _sync_queue.peek_pending(conn)
        finally:
            conn.close()
        assert len(pending) == 1

        # Next tick: cloud returns 200 again, mark_synced succeeds → drained.
        worker._tick()

    conn = _open(db_path)
    try:
        pending = _sync_queue.peek_pending(conn)
    finally:
        conn.close()
    assert pending == []
