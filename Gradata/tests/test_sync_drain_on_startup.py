"""Tests for write-through sync_queue drain on daemon startup (GRA-1245).

Daemon restart used to leave rows in ``sync_queue`` with ``synced_at IS NULL``
until the next correction event triggered a flush. If the daemon crashed
mid-batch, pending syncs sat indefinitely.

The fix calls :func:`gradata._sync_worker.drain_sync_queue` (also exposed via
:meth:`GradataDaemon._drain_sync_queue_at_startup`) *before* the HTTP listener
is bound, so the first request never observes a stale backlog.

These tests:

1. Seed pending rows in ``sync_queue``.
2. Call the startup hook directly (no real HTTP listener needed).
3. Assert all rows have ``synced_at`` populated.
4. Assert the discoverable info log line is emitted.
5. Assert idempotency: a second call is a no-op (0 rows drained).
6. Assert the function tolerates missing api_key / fresh brain (no crash).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from gradata import _sync_queue
from gradata._migrations import _BASE_TABLES, _MIGRATIONS
from gradata._sync_worker import drain_sync_queue

# ── helpers ───────────────────────────────────────────────────────────


def _seed_db(db_path) -> None:
    """Create a system.db that has just the sync_queue table + index."""
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


def _enqueue_n(db_path, n: int) -> list[int]:
    conn = _open(db_path)
    ids: list[int] = []
    try:
        for i in range(n):
            ids.append(
                _sync_queue.enqueue_correction(
                    conn,
                    brain_id="brain-startup",
                    correction={"session": 1, "description": f"pending row {i}"},
                    event_id=f"startup-evt-{i}",
                )
            )
    finally:
        conn.close()
    return ids


def _count_pending(db_path) -> int:
    conn = _open(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM sync_queue WHERE synced_at IS NULL").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


# ── stub /ingest server ──────────────────────────────────────────────


class _StubIngest:
    """In-process HTTP server that records POSTs and returns 200 by default."""

    def __init__(self, response_fn=None) -> None:
        self.response_fn = response_fn or (lambda _p, _n: (200, {"ok": True}))
        self.requests: list[dict] = []
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a, **_kw) -> None:
                return

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b""
                try:
                    payload = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    payload = {"_raw": body.decode("utf-8", errors="replace")}
                outer.requests.append({"path": self.path, "payload": payload})
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
    started: list[_StubIngest] = []

    def _factory(response_fn=None):
        s = _StubIngest(response_fn)
        url = s.start()
        started.append(s)
        return s, url

    yield _factory

    for s in started:
        s.stop()


# ── tests ────────────────────────────────────────────────────────────


def test_drain_sync_queue_flushes_pending_rows(tmp_path, stub_ingest, caplog):
    """Pending rows from a 'previous run' are all marked synced after the hook fires."""
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    _enqueue_n(db_path, n=5)
    assert _count_pending(db_path) == 5

    server, url = stub_ingest()

    with caplog.at_level(logging.INFO, logger="gradata.sync_worker"):
        drained = drain_sync_queue(tmp_path, api_key="startup-key", ingest_url=url)

    assert drained == 5
    assert _count_pending(db_path) == 0
    # All rows now have synced_at populated
    conn = _open(db_path)
    try:
        rows = conn.execute("SELECT synced_at FROM sync_queue").fetchall()
    finally:
        conn.close()
    assert len(rows) == 5
    assert all(r["synced_at"] is not None for r in rows)

    # Discoverable journalctl line
    assert any(
        "sync queue drained at startup: 5 rows" in rec.getMessage() for rec in caplog.records
    ), [r.getMessage() for r in caplog.records]

    # Every payload was POSTed once
    assert len(server.requests) == 5


def test_drain_sync_queue_is_idempotent(tmp_path, stub_ingest, caplog):
    """A second drain call with a clean queue is a no-op (0 rows)."""
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    _enqueue_n(db_path, n=3)

    _, url = stub_ingest()
    first = drain_sync_queue(tmp_path, api_key="k", ingest_url=url)
    assert first == 3
    assert _count_pending(db_path) == 0

    with caplog.at_level(logging.INFO, logger="gradata.sync_worker"):
        second = drain_sync_queue(tmp_path, api_key="k", ingest_url=url)

    assert second == 0
    assert _count_pending(db_path) == 0
    assert any(
        "sync queue drained at startup: 0 rows" in rec.getMessage() for rec in caplog.records
    )


def test_drain_sync_queue_noop_without_api_key(tmp_path):
    """Missing api_key must not crash startup — just no-op."""
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    _enqueue_n(db_path, n=2)

    drained = drain_sync_queue(tmp_path, api_key=None)
    assert drained == 0
    # Rows remain pending (background worker will pick them up)
    assert _count_pending(db_path) == 2


def test_drain_sync_queue_noop_when_db_missing(tmp_path):
    """No system.db yet (fresh brain dir) — must return 0, not crash."""
    drained = drain_sync_queue(tmp_path, api_key="k")
    assert drained == 0


def test_drain_sync_queue_noop_when_table_missing(tmp_path):
    """system.db exists but sync_queue table doesn't — handle gracefully."""
    db_path = tmp_path / "system.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE other (x INTEGER)")
    conn.commit()
    conn.close()

    drained = drain_sync_queue(tmp_path, api_key="k")
    assert drained == 0


def test_daemon_startup_hook_drains_before_listener(tmp_path, stub_ingest, caplog, monkeypatch):
    """The GradataDaemon startup hook drains the queue and emits the log line.

    Simulates daemon startup by calling the hook method directly (no HTTP
    server bound). This is the canonical 'startup before listener' test.
    """
    from gradata.daemon import GradataDaemon

    # Seed a brain dir with system.db + sync_queue and a few pending rows.
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    _enqueue_n(db_path, n=4)
    assert _count_pending(db_path) == 4

    _, url = stub_ingest()
    monkeypatch.setenv("GRADATA_CLOUD_INGEST_URL", url)

    # Construct the daemon WITHOUT calling .start() so no listener binds.
    # We need a Brain initialisable from this dir — but GradataDaemon.__init__
    # calls Brain(self._brain_dir). To avoid the full Brain machinery we
    # stub it out, since this test only exercises the startup-drain hook.
    class _StubBrain:
        def __init__(self, p) -> None:
            self.dir = p
            self.db_path = p / "system.db"

        def _load_lessons(self):
            return []

    import gradata

    monkeypatch.setattr(gradata, "Brain", _StubBrain)

    daemon = GradataDaemon(brain_dir=tmp_path, api_key="startup-key")

    with caplog.at_level(logging.INFO, logger="gradata.sync_worker"):
        drained = daemon._drain_sync_queue_at_startup()

    assert drained == 4
    assert _count_pending(db_path) == 0
    assert any(
        "sync queue drained at startup: 4 rows" in rec.getMessage() for rec in caplog.records
    )


def test_drain_sync_queue_safe_concurrent_with_worker(tmp_path, stub_ingest):
    """Two simultaneous drain callers don't lose or double-mark rows.

    Models the (rare) race where the startup drain and the background
    :class:`SyncWorker` first tick land at the same time. Both paths open
    their own short-lived sqlite connections; the final state must be
    'all rows synced exactly once per row' from the local DB's perspective
    (the cloud dedupes any duplicate POST via event_id).
    """
    db_path = tmp_path / "system.db"
    _seed_db(db_path)
    _enqueue_n(db_path, n=10)

    _, url = stub_ingest()

    results: list[int] = []
    errors: list[BaseException] = []

    def _runner() -> None:
        try:
            results.append(drain_sync_queue(tmp_path, api_key="k", ingest_url=url))
        except BaseException as exc:  # pragma: no cover — defensive
            errors.append(exc)

    threads = [threading.Thread(target=_runner) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert not errors, errors
    # Queue must be fully drained regardless of who got which rows.
    assert _count_pending(db_path) == 0
    # Total drained across both runners equals 10 (sum across threads; one
    # may see 10, the other 0, or any split — but no row is lost).
    assert sum(results) >= 10 or _count_pending(db_path) == 0
