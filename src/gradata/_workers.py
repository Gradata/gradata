"""
Background Worker Queue — off-the-hot-path job runner.
======================================================

Provides a minimal, durable (SQLite-backed) job queue plus a worker
thread pool that drains it. Heavy operations (meta-rule synthesis,
decay application, event consolidation, DP export) enqueue jobs here
instead of running inline during ``brain.correct()`` or session-end.

Design
------
* Storage:     ``worker_jobs`` table in the brain's ``system.db``.
* Dedup:       ``(type, payload_hash)`` — same job enqueued twice while
               the first is still pending runs only once.
* Semantics:   at-least-once. Handlers should be idempotent.
* Dispatch:    one or more worker threads poll for ``pending`` rows,
               claim with an ``UPDATE ... status='running'``, run the
               handler, then mark ``done`` or ``failed``.
* Shutdown:    :meth:`WorkerPool.stop` drains up to a deadline, then
               exits even if jobs remain queued.

Job types (stubs for now — real handlers land in follow-up PRs):

* ``SYNTHESIZE_META_RULES``  — LLM meta-rule synthesis from graduated rules.
* ``APPLY_DECAY``            — Periodic confidence decay.
* ``CONSOLIDATE_EVENTS``     — Event-log consolidation / compression.
* ``DP_EXPORT``              — Differentially-private brain export.

The handlers registered here are intentionally no-op-with-logging stubs.
Implementation wiring happens in the PRs that own the touched files.
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


# ── Job types ───────────────────────────────────────────────────────────

SYNTHESIZE_META_RULES = "SYNTHESIZE_META_RULES"
APPLY_DECAY = "APPLY_DECAY"
CONSOLIDATE_EVENTS = "CONSOLIDATE_EVENTS"
DP_EXPORT = "DP_EXPORT"

KNOWN_JOB_TYPES: frozenset[str] = frozenset({
    SYNTHESIZE_META_RULES,
    APPLY_DECAY,
    CONSOLIDATE_EVENTS,
    DP_EXPORT,
})


# ── Schema ──────────────────────────────────────────────────────────────

_WORKER_JOBS_SQL = """
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
"""

_WORKER_JOBS_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_worker_jobs_status ON worker_jobs(status)",
    (
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_jobs_dedup "
        "ON worker_jobs(type, payload_hash) "
        "WHERE status IN ('pending', 'running')"
    ),
]


def ensure_schema(db_path: str | Path) -> None:
    """Create ``worker_jobs`` table and indexes if missing.

    Safe to call repeatedly; uses ``CREATE IF NOT EXISTS``. Callers should
    invoke this once at daemon startup, before any enqueue.
    """
    conn = get_connection(db_path)
    try:
        conn.execute(_WORKER_JOBS_SQL)
        for sql in _WORKER_JOBS_INDEXES:
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


# ── Dataclass ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Job:
    """A single row from ``worker_jobs`` delivered to a handler."""

    id: int
    type: str
    payload: dict[str, Any]
    created_at: float


Handler = Callable[[Job], None]


# ── Default handlers (no-op with logging) ───────────────────────────────


def _handler_synthesize_meta_rules(job: Job) -> None:
    logger.info("worker: would synthesize meta-rules (job=%d)", job.id)


def _handler_apply_decay(job: Job) -> None:
    logger.info("worker: would apply decay (job=%d)", job.id)


def _handler_consolidate_events(job: Job) -> None:
    logger.info("worker: would consolidate events (job=%d)", job.id)


def _handler_dp_export(job: Job) -> None:
    logger.info("worker: would run DP export (job=%d)", job.id)


def default_handlers() -> dict[str, Handler]:
    """Return the default handler map (stubs).

    Follow-up PRs that own the synthesis / decay / export code will
    replace these by calling :meth:`WorkerPool.register` with real
    implementations.
    """
    return {
        SYNTHESIZE_META_RULES: _handler_synthesize_meta_rules,
        APPLY_DECAY: _handler_apply_decay,
        CONSOLIDATE_EVENTS: _handler_consolidate_events,
        DP_EXPORT: _handler_dp_export,
    }


# ── Utility ─────────────────────────────────────────────────────────────


def _payload_hash(payload: dict[str, Any]) -> str:
    """Stable hash of a payload for dedup. Sorted keys, JSON-serialised."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Clock abstraction (for tests) ───────────────────────────────────────


class _Clock:
    """Indirection over ``time.time`` / ``time.monotonic`` so tests can
    inject a fake. The pool uses ``mono()`` for deadlines (shutdown) and
    ``now()`` for timestamp columns.
    """

    def now(self) -> float:
        return time.time()

    def mono(self) -> float:
        return time.monotonic()


# ── The pool ────────────────────────────────────────────────────────────


class WorkerPool:
    """Thread pool that drains ``worker_jobs`` from SQLite.

    The pool is designed to run embedded inside the daemon, but it is
    self-contained and can also be driven from a standalone script (see
    ``brain/scripts/daemon_runner.py``).

    Parameters
    ----------
    db_path:
        Path to the brain's ``system.db`` (same file the rest of the
        SDK uses).
    workers:
        Number of worker threads. Default 1 — these jobs are rare and
        heavyweight; we mostly want them off the hot path, not parallel.
    poll_interval:
        Seconds between polls when the queue is empty. Low enough to
        feel responsive, high enough not to burn CPU.
    handlers:
        Optional handler map. Defaults to :func:`default_handlers`.
    clock:
        Optional :class:`_Clock` for tests. Defaults to the real clock.
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

    # ── Registration ────────────────────────────────────────────────────

    def register(self, job_type: str, handler: Handler) -> None:
        """Register (or override) a handler for ``job_type``.

        Follow-up PRs call this to swap a stub for a real implementation.
        """
        with self._lock:
            self._handlers[job_type] = handler

    # ── Enqueue ─────────────────────────────────────────────────────────

    def enqueue(self, job_type: str, payload: dict[str, Any] | None = None) -> int | None:
        """Enqueue a job. Returns the new job id, or ``None`` if a job
        with the same ``(type, payload_hash)`` is already pending/running
        (dedup).

        At-least-once semantics: handlers MUST be idempotent. The dedup
        index guarantees that a burst of identical enqueues collapses to
        a single handler invocation, but a job that failed mid-flight
        may be retried by a future enqueue once the prior attempt is
        marked ``failed``.
        """
        payload = payload or {}
        phash = _payload_hash(payload)
        created_at = self._clock.now()

        conn = get_connection(self._db_path)
        try:
            try:
                cur = conn.execute(
                    "INSERT INTO worker_jobs "
                    "(type, payload_json, payload_hash, status, created_at) "
                    "VALUES (?, ?, ?, 'pending', ?)",
                    (job_type, json.dumps(payload, sort_keys=True), phash, created_at),
                )
                conn.commit()
                return int(cur.lastrowid) if cur.lastrowid is not None else None
            except sqlite3.IntegrityError:
                # Unique index collision => a duplicate is already live.
                logger.debug(
                    "enqueue dedup: type=%s hash=%s already pending/running",
                    job_type, phash,
                )
                return None
        finally:
            conn.close()

    # ── Static helper for callers that don't hold the pool ──────────────

    @staticmethod
    def enqueue_to(
        db_path: str | Path,
        job_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int | None:
        """Convenience: enqueue without instantiating a full pool.

        Used by hot-path callers (e.g. ``brain.correct``) that only need
        to drop a job; the daemon's pool picks it up.
        """
        ensure_schema(db_path)
        pool = WorkerPool(db_path)
        return pool.enqueue(job_type, payload)

    # ── Claim + run a single job ────────────────────────────────────────

    def _claim_one(self, conn: sqlite3.Connection) -> Job | None:
        """Atomically claim one pending job. Returns None if the queue is empty."""
        now = self._clock.now()
        # BEGIN IMMEDIATE takes a write lock so two workers can't claim the same row.
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

    def _mark_done(self, conn: sqlite3.Connection, job_id: int) -> None:
        conn.execute(
            "UPDATE worker_jobs SET status='done', finished_at=? WHERE id=?",
            (self._clock.now(), job_id),
        )
        conn.commit()

    def _mark_failed(self, conn: sqlite3.Connection, job_id: int, err: str) -> None:
        conn.execute(
            "UPDATE worker_jobs SET status='failed', finished_at=?, error=? WHERE id=?",
            (self._clock.now(), err[:500], job_id),
        )
        conn.commit()

    def drain_once(self) -> bool:
        """Claim and run a single pending job. Returns True if a job
        was processed, False if the queue was empty.

        Used both by the worker loop and by tests that want deterministic
        single-step execution without spawning threads.
        """
        conn = get_connection(self._db_path)
        try:
            job = self._claim_one(conn)
            if job is None:
                return False
            with self._lock:
                handler = self._handlers.get(job.type)
            if handler is None:
                self._mark_failed(conn, job.id, f"no handler for type={job.type}")
                logger.warning("worker: no handler for job type=%s id=%d", job.type, job.id)
                return True
            try:
                handler(job)
                self._mark_done(conn, job.id)
            except Exception as exc:
                logger.exception("worker: handler for %s raised", job.type)
                self._mark_failed(conn, job.id, f"{type(exc).__name__}: {exc}")
            return True
        finally:
            conn.close()

    # ── Worker loop ─────────────────────────────────────────────────────

    def _should_exit(self) -> bool:
        """True if we've been asked to stop AND either the queue is drained
        or the drain deadline has passed.
        """
        if not self._stop_event.is_set():
            return False
        if self._drain_deadline is not None and self._clock.mono() >= self._drain_deadline:
            return True
        # Stop set but deadline not hit: keep draining while there's work.
        return not self._has_pending()

    def _has_pending(self) -> bool:
        conn = get_connection(self._db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM worker_jobs WHERE status='pending' LIMIT 1"
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def _worker_loop(self) -> None:
        while not self._should_exit():
            try:
                processed = self.drain_once()
            except Exception:
                logger.exception("worker loop: drain_once failed")
                processed = False
            if not processed:
                # Idle: short sleep, but wake early on stop so we notice
                # the deadline.
                self._stop_event.wait(self._poll_interval)

    # ── Lifecycle ───────────────────────────────────────────────────────

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
        """Signal workers to exit. Blocks up to ``drain_timeout`` seconds
        while the queue drains, then returns even if jobs remain.
        """
        if not self._started:
            return
        self._drain_deadline = self._clock.mono() + max(0.0, drain_timeout)
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=drain_timeout + 1.0)
        self._threads.clear()
        self._started = False
        logger.info("WorkerPool stopped")


# ── Module-level convenience ────────────────────────────────────────────


def enqueue_job(
    db_path: str | Path,
    job_type: str,
    payload: dict[str, Any] | None = None,
) -> int | None:
    """Top-level helper mirroring :meth:`WorkerPool.enqueue_to`.

    Call from anywhere in the SDK::

        from gradata._workers import enqueue_job, APPLY_DECAY
        enqueue_job(brain.db_path, APPLY_DECAY, {"reason": "nightly"})

    Returns the new job id, or ``None`` on dedup.
    """
    return WorkerPool.enqueue_to(db_path, job_type, payload)


# ── Standalone runner ───────────────────────────────────────────────────


def run_standalone(
    brain_dir: str | Path,
    workers: int = 1,
    drain_timeout: float = 5.0,
) -> None:
    """Run a worker pool without the HTTP daemon.

    Useful for cron jobs, CI, or a dedicated systemd unit that only
    drains the queue. Blocks until SIGTERM / SIGINT, then drains up
    to ``drain_timeout`` seconds before exiting.
    """
    import contextlib
    import signal

    brain_dir = Path(brain_dir).resolve()
    db_path = brain_dir / "system.db"
    ensure_schema(db_path)

    pool = WorkerPool(db_path, workers=workers)
    pool.start()
    logger.info("workers: standalone pool started (workers=%d, db=%s)", workers, db_path)

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("workers: signal %d received, shutting down", signum)
        stop_event.set()

    if hasattr(signal, "SIGTERM"):
        with contextlib.suppress(ValueError):
            signal.signal(signal.SIGTERM, _handle_signal)
    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGINT, _handle_signal)

    try:
        stop_event.wait()
    finally:
        pool.stop(drain_timeout=drain_timeout)
        logger.info("workers: standalone pool exited")


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Gradata standalone worker-pool runner (no HTTP server).",
    )
    parser.add_argument("--brain-dir", required=True, help="Path to the brain directory")
    parser.add_argument("--workers", type=int, default=1, help="Worker threads (default 1)")
    parser.add_argument(
        "--drain-timeout", type=float, default=5.0,
        help="Seconds to let the queue drain on shutdown (default 5)",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_standalone(args.brain_dir, args.workers, args.drain_timeout)


if __name__ == "__main__":
    _main()
