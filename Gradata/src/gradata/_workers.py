"""
Background Worker Queue — off-the-hot-path job runner.

SQLite-backed job queue + worker-thread pool that drains it. Heavy ops
(meta-rule synthesis, decay, consolidation, DP export) enqueue here
instead of running inline in ``brain.correct()`` or session-end.

* Storage:   ``worker_jobs`` table in the brain's ``system.db``.
* Dedup:     unique partial index on ``(type, payload_hash)`` for rows
             with ``status IN ('pending','running')``. Bursts of
             identical enqueues collapse to one handler call.
* Semantics: at-least-once. Handlers MUST be idempotent.
* Shutdown:  :meth:`WorkerPool.stop` drains up to a deadline then exits.

Four job-type constants (SYNTHESIZE_META_RULES, APPLY_DECAY,
CONSOLIDATE_EVENTS, DP_EXPORT) come pre-registered as log-only stubs.
Follow-up PRs swap real implementations via :meth:`WorkerPool.register`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gradata._db import get_connection

logger = logging.getLogger("gradata.workers")

SYNTHESIZE_META_RULES = "SYNTHESIZE_META_RULES"
APPLY_DECAY = "APPLY_DECAY"
CONSOLIDATE_EVENTS = "CONSOLIDATE_EVENTS"
DP_EXPORT = "DP_EXPORT"

KNOWN_JOB_TYPES: frozenset[str] = frozenset(
    {
        SYNTHESIZE_META_RULES,
        APPLY_DECAY,
        CONSOLIDATE_EVENTS,
        DP_EXPORT,
    }
)

_SCHEMA_SQL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS worker_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        payload_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at REAL NOT NULL,
        started_at REAL,
        finished_at REAL,
        error TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_worker_jobs_status ON worker_jobs(status)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_jobs_dedup "
    "ON worker_jobs(type, payload_hash) "
    "WHERE status IN ('pending', 'running')",
)


def ensure_schema(db_path: str | Path) -> None:
    """Create ``worker_jobs`` table + indexes if missing. Idempotent."""
    conn = get_connection(db_path)
    try:
        for sql in _SCHEMA_SQL:
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


@dataclass(frozen=True)
class Job:
    """A single row from ``worker_jobs`` delivered to a handler."""

    id: int
    type: str
    payload: dict[str, Any]
    created_at: float


Handler = Callable[[Job], None]


def _stub_handler(label: str) -> Handler:
    """Log-and-succeed stub. Follow-up PRs swap via ``WorkerPool.register``."""

    def _run(job: Job) -> None:
        logger.info("worker: would %s (job=%d)", label, job.id)

    return _run


def default_handlers() -> dict[str, Handler]:
    return {
        SYNTHESIZE_META_RULES: _stub_handler("synthesize meta-rules"),
        APPLY_DECAY: _stub_handler("apply decay"),
        CONSOLIDATE_EVENTS: _stub_handler("consolidate events"),
        DP_EXPORT: _stub_handler("run DP export"),
    }


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload: dict[str, Any]) -> str:
    """Stable short hash of a payload for dedup."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]


class _Clock:
    """Clock indirection so tests can inject a fake (see ``FakeClock``)."""

    def now(self) -> float:
        return time.time()

    def mono(self) -> float:
        return time.monotonic()


class WorkerPool:
    """Thread pool that drains ``worker_jobs`` from SQLite.

    Runs embedded inside the daemon but is self-contained enough to drive
    from a standalone script (see :func:`run_standalone`).
    """

    def __init__(
        self,
        db_path: str | Path,
        workers: int = 1,
        poll_interval: float = 0.5,
        handlers: dict[str, Handler] | None = None,
        clock: _Clock | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._n_workers = max(1, workers)
        self._poll_interval = poll_interval
        self._handlers: dict[str, Handler] = dict(handlers or default_handlers())
        self._clock = clock or _Clock()
        self._stop_event = threading.Event()
        self._drain_deadline: float | None = None
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._started = False

    def register(self, job_type: str, handler: Handler) -> None:
        """Register (or override) a handler for ``job_type``."""
        with self._lock:
            self._handlers[job_type] = handler

    def enqueue(self, job_type: str, payload: dict[str, Any] | None = None) -> int | None:
        """Insert a pending job. Returns new id, or ``None`` if deduped.

        At-least-once: handlers MUST be idempotent. A failed job's dedup
        slot is released, so a later enqueue can retry it.
        """
        payload_json = _canonical_json(payload or {})
        phash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()[:16]

        conn = get_connection(self._db_path)
        try:
            try:
                cur = conn.execute(
                    "INSERT INTO worker_jobs "
                    "(type, payload_json, payload_hash, status, created_at) "
                    "VALUES (?, ?, ?, 'pending', ?)",
                    (job_type, payload_json, phash, self._clock.now()),
                )
                conn.commit()
                return int(cur.lastrowid) if cur.lastrowid is not None else None
            except sqlite3.IntegrityError:
                logger.debug("enqueue dedup: type=%s hash=%s live", job_type, phash)
                return None
        finally:
            conn.close()

    def _claim_one(self, conn: sqlite3.Connection) -> Job | None:
        """Atomically claim one pending job. BEGIN IMMEDIATE prevents races."""
        now = self._clock.now()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT id, type, payload_json, created_at "
                "FROM worker_jobs WHERE status = 'pending' "
                "ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                "UPDATE worker_jobs SET status='running', started_at=? WHERE id=?",
                (now, row["id"]),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        try:
            payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        except json.JSONDecodeError:
            payload = {}
        return Job(
            id=int(row["id"]),
            type=str(row["type"]),
            payload=payload,
            created_at=float(row["created_at"]),
        )

    def _finalize(
        self,
        conn: sqlite3.Connection,
        job_id: int,
        *,
        error: str | None = None,
    ) -> None:
        conn.execute(
            "UPDATE worker_jobs SET status=?, finished_at=?, error=? WHERE id=?",
            (
                "failed" if error else "done",
                self._clock.now(),
                (error[:500] if error else None),
                job_id,
            ),
        )
        conn.commit()

    def drain_once(self) -> bool:
        """Claim + run one pending job. Returns True if one was processed."""
        conn = get_connection(self._db_path)
        try:
            job = self._claim_one(conn)
            if job is None:
                return False
            with self._lock:
                handler = self._handlers.get(job.type)
            if handler is None:
                self._finalize(conn, job.id, error=f"no handler for type={job.type}")
                logger.warning("worker: no handler for job type=%s id=%d", job.type, job.id)
                return True
            try:
                handler(job)
                self._finalize(conn, job.id)
            except Exception as exc:
                logger.exception("worker: handler for %s raised", job.type)
                self._finalize(conn, job.id, error=f"{type(exc).__name__}: {exc}")
            return True
        finally:
            conn.close()

    def _has_pending(self) -> bool:
        conn = get_connection(self._db_path)
        try:
            return (
                conn.execute("SELECT 1 FROM worker_jobs WHERE status='pending' LIMIT 1").fetchone()
                is not None
            )
        finally:
            conn.close()

    def _should_exit(self) -> bool:
        """Stop requested AND (deadline passed OR queue empty)."""
        if not self._stop_event.is_set():
            return False
        if self._drain_deadline is not None and self._clock.mono() >= self._drain_deadline:
            return True
        return not self._has_pending()

    def _worker_loop(self) -> None:
        while not self._should_exit():
            try:
                processed = self.drain_once()
            except Exception:
                logger.exception("worker loop: drain_once failed")
                processed = False
            if not processed:
                self._stop_event.wait(self._poll_interval)

    def start(self) -> None:
        """Start worker threads. Idempotent."""
        if self._started:
            return
        ensure_schema(self._db_path)
        self._stop_event.clear()
        self._drain_deadline = None
        for i in range(self._n_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"gradata-worker-{i}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)
        self._started = True
        logger.info("WorkerPool started with %d worker(s)", self._n_workers)

    def stop(self, drain_timeout: float = 5.0) -> None:
        """Signal exit; block up to ``drain_timeout`` s while queue drains."""
        if not self._started:
            return
        self._drain_deadline = self._clock.mono() + max(0.0, drain_timeout)
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=drain_timeout + 1.0)
        self._threads.clear()
        self._started = False
        logger.info("WorkerPool stopped")


def enqueue_job(
    db_path: str | Path,
    job_type: str,
    payload: dict[str, Any] | None = None,
) -> int | None:
    """Enqueue without instantiating a long-lived pool.

    For hot-path callers (e.g. ``brain.correct``) that drop a job and let
    the daemon's pool pick it up. Returns id or ``None`` on dedup.
    """
    ensure_schema(db_path)
    return WorkerPool(db_path).enqueue(job_type, payload)


def run_standalone(
    brain_dir: str | Path,
    workers: int = 1,
    drain_timeout: float = 5.0,
) -> None:
    """Run a worker pool without the HTTP daemon. Blocks until SIGTERM/SIGINT."""
    import contextlib
    import signal

    db_path = Path(brain_dir).resolve() / "system.db"
    ensure_schema(db_path)
    pool = WorkerPool(db_path, workers=workers)
    pool.start()
    logger.info("workers: standalone pool started (workers=%d, db=%s)", workers, db_path)

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("workers: signal %d received, shutting down", signum)
        stop_event.set()

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            with contextlib.suppress(ValueError):
                signal.signal(sig, _handle_signal)

    try:
        stop_event.wait()
    finally:
        pool.stop(drain_timeout=drain_timeout)
        logger.info("workers: standalone pool exited")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Gradata standalone worker-pool runner (no HTTP server).",
    )
    parser.add_argument("--brain-dir", required=True, help="Path to the brain directory")
    parser.add_argument("--workers", type=int, default=1, help="Worker threads (default 1)")
    parser.add_argument(
        "--drain-timeout",
        type=float,
        default=5.0,
        help="Seconds to let the queue drain on shutdown (default 5)",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_standalone(args.brain_dir, args.workers, args.drain_timeout)
