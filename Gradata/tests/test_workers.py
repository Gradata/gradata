"""Tests for the background worker queue (src/gradata/_workers.py).

All time-dependent logic uses a fake clock; nothing sleeps for real
seconds. Thread-based tests use :meth:`WorkerPool.drain_once` so runs
are deterministic and fast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gradata._workers import (
    APPLY_DECAY,
    CONSOLIDATE_EVENTS,
    DP_EXPORT,
    SYNTHESIZE_META_RULES,
    Job,
    WorkerPool,
    _Clock,
    _payload_hash,
    enqueue_job,
    ensure_schema,
)

if TYPE_CHECKING:
    from pathlib import Path


# ── Fakes ───────────────────────────────────────────────────────────────


class FakeClock(_Clock):
    """Deterministic clock for tests."""

    def __init__(self, start_now: float = 1_000_000.0, start_mono: float = 0.0) -> None:
        self._now = start_now
        self._mono = start_mono

    def now(self) -> float:
        return self._now

    def mono(self) -> float:
        return self._mono

    def advance(self, seconds: float) -> None:
        self._now += seconds
        self._mono += seconds


def _db(tmp_path: Path) -> Path:
    """Create a fresh brain-like directory with an empty system.db."""
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    db = brain_dir / "system.db"
    db.touch()
    ensure_schema(db)
    return db


# ── Schema & enqueue basics ─────────────────────────────────────────────


def test_ensure_schema_idempotent(tmp_path: Path) -> None:
    db = _db(tmp_path)
    # Calling twice must not raise.
    ensure_schema(db)
    ensure_schema(db)


def test_payload_hash_is_stable() -> None:
    a = _payload_hash({"x": 1, "y": 2})
    b = _payload_hash({"y": 2, "x": 1})  # key order differs
    c = _payload_hash({"x": 1, "y": 3})
    assert a == b
    assert a != c


def test_known_job_types_are_registered_by_default(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pool = WorkerPool(db)
    # All four stubs come pre-registered.
    assert SYNTHESIZE_META_RULES in pool._handlers
    assert APPLY_DECAY in pool._handlers
    assert CONSOLIDATE_EVENTS in pool._handlers
    assert DP_EXPORT in pool._handlers


# ── Enqueue + drain ─────────────────────────────────────────────────────


def test_enqueue_and_drain_runs_handler(tmp_path: Path) -> None:
    db = _db(tmp_path)
    clock = FakeClock()
    seen: list[Job] = []

    def handler(job: Job) -> None:
        seen.append(job)

    pool = WorkerPool(db, clock=clock, handlers={APPLY_DECAY: handler})
    job_id = pool.enqueue(APPLY_DECAY, {"reason": "nightly"})
    assert job_id is not None and job_id > 0

    assert pool.drain_once() is True
    assert pool.drain_once() is False  # queue now empty

    assert len(seen) == 1
    assert seen[0].type == APPLY_DECAY
    assert seen[0].payload == {"reason": "nightly"}


def test_module_level_enqueue_job_helper(tmp_path: Path) -> None:
    db = _db(tmp_path)
    job_id = enqueue_job(db, CONSOLIDATE_EVENTS, {"window": "24h"})
    assert job_id is not None

    calls: list[Job] = []
    pool = WorkerPool(db, handlers={CONSOLIDATE_EVENTS: lambda j: calls.append(j)})
    assert pool.drain_once() is True
    assert len(calls) == 1
    assert calls[0].payload == {"window": "24h"}


# ── Dedup ───────────────────────────────────────────────────────────────


def test_dedup_same_type_and_payload_collapses_to_one_handler_call(tmp_path: Path) -> None:
    db = _db(tmp_path)
    calls: list[Job] = []

    def handler(job: Job) -> None:
        calls.append(job)

    pool = WorkerPool(db, handlers={SYNTHESIZE_META_RULES: handler})

    first = pool.enqueue(SYNTHESIZE_META_RULES, {"window": "session_end"})
    second = pool.enqueue(SYNTHESIZE_META_RULES, {"window": "session_end"})
    third = pool.enqueue(SYNTHESIZE_META_RULES, {"window": "session_end"})

    assert first is not None
    # Duplicates while the first is still pending return None (deduped).
    assert second is None
    assert third is None

    # Drain everything. Should run exactly once.
    assert pool.drain_once() is True
    assert pool.drain_once() is False
    assert len(calls) == 1


def test_dedup_distinct_payloads_both_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    calls: list[Job] = []
    pool = WorkerPool(db, handlers={APPLY_DECAY: lambda j: calls.append(j)})

    a = pool.enqueue(APPLY_DECAY, {"half_life_days": 7})
    b = pool.enqueue(APPLY_DECAY, {"half_life_days": 30})
    assert a is not None and b is not None and a != b

    assert pool.drain_once() is True
    assert pool.drain_once() is True
    assert pool.drain_once() is False
    assert len(calls) == 2


def test_dedup_releases_after_completion(tmp_path: Path) -> None:
    """Once a job is done, an identical payload can be enqueued again."""
    db = _db(tmp_path)
    calls: list[Job] = []
    pool = WorkerPool(db, handlers={DP_EXPORT: lambda j: calls.append(j)})

    first = pool.enqueue(DP_EXPORT, {"epsilon": 1.0})
    assert first is not None
    assert pool.drain_once() is True  # marks done, frees the dedup slot

    second = pool.enqueue(DP_EXPORT, {"epsilon": 1.0})
    assert second is not None and second != first
    assert pool.drain_once() is True

    assert len(calls) == 2


# ── Unknown type + handler error ────────────────────────────────────────


def test_unknown_job_type_marked_failed(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pool = WorkerPool(db, handlers={})  # explicitly empty
    pool.enqueue("MYSTERY_JOB", {})
    assert pool.drain_once() is True  # it processed (and failed) the row
    assert pool.drain_once() is False


def test_handler_exception_marks_failed_but_does_not_crash_pool(tmp_path: Path) -> None:
    db = _db(tmp_path)

    def bad(_job: Job) -> None:
        raise RuntimeError("boom")

    def good(job: Job) -> None:
        calls.append(job)

    calls: list[Job] = []
    pool = WorkerPool(db, handlers={APPLY_DECAY: bad, DP_EXPORT: good})
    pool.enqueue(APPLY_DECAY, {})
    pool.enqueue(DP_EXPORT, {})

    assert pool.drain_once() is True  # bad one fails silently
    assert pool.drain_once() is True  # good one still runs
    assert len(calls) == 1


# ── Shutdown / drain deadline ───────────────────────────────────────────


def test_should_exit_respects_drain_deadline(tmp_path: Path) -> None:
    """With stop requested and the deadline passed, the pool exits even if
    the queue still has work. This is the graceful-shutdown contract.
    """
    db = _db(tmp_path)
    clock = FakeClock()
    pool = WorkerPool(db, clock=clock)

    # Enqueue a job but don't drain it — queue has pending work.
    pool.enqueue(APPLY_DECAY, {"still": "pending"})

    # Not stopping yet: _should_exit is False regardless of work.
    assert pool._should_exit() is False

    # Stop requested, deadline in the future, work still pending -> keep going.
    pool._stop_event.set()
    pool._drain_deadline = clock.mono() + 10.0
    assert pool._should_exit() is False

    # Deadline reached -> exit even though a job is still pending.
    clock.advance(11.0)
    assert pool._should_exit() is True


def test_should_exit_returns_true_when_queue_empty_and_stop_requested(tmp_path: Path) -> None:
    db = _db(tmp_path)
    clock = FakeClock()
    pool = WorkerPool(db, clock=clock)

    pool._stop_event.set()
    pool._drain_deadline = clock.mono() + 10.0
    # No work, stop set, deadline not hit -> still exit (nothing to drain).
    assert pool._should_exit() is True


def test_stop_without_start_is_noop(tmp_path: Path) -> None:
    db = _db(tmp_path)
    pool = WorkerPool(db)
    pool.stop()  # must not raise
