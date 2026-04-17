"""Tests for atomic file operations — persistence and data integrity."""
import json
import multiprocessing
import tempfile
from pathlib import Path

from tests.conftest import init_brain


# ---------------------------------------------------------------------------
# Worker used by the concurrency property test (must be module-level so that
# multiprocessing can pickle it on Windows).
# ---------------------------------------------------------------------------

def _emit_worker(brain_dir_str: str, n: int, worker_id: int) -> None:
    """Emit *n* events from a subprocess, each carrying the worker id."""
    from gradata._events import emit
    from gradata._paths import BrainContext

    ctx = BrainContext.from_brain_dir(brain_dir_str)
    for i in range(n):
        emit("CONCURRENT_TEST", f"worker-{worker_id}", data={"seq": i}, ctx=ctx)


class TestAtomicWrites:
    def test_rapid_sequential_corrections_no_corruption(self, tmp_path):
        brain = init_brain(tmp_path)
        for t in range(3):
            for i in range(5):
                brain.correct(draft=f"t{t}-draft-{i}", final=f"t{t}-final-{i}", category="TEST")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 15

    def test_single_correction_persisted(self, tmp_path):
        brain = init_brain(tmp_path)
        brain.correct(draft="good", final="better", category="TEST")
        events = brain.query_events(event_type="CORRECTION")
        assert len(events) >= 1

    def test_lessons_file_not_truncated(self, tmp_path):
        brain = init_brain(tmp_path)
        for i in range(10):
            brain.correct(draft=f"draft {i}", final=f"final {i}", category="TONE")
        lessons_path = tmp_path / "brain" / "lessons.md"
        assert lessons_path.exists(), "lessons.md should be created after 10 corrections"
        assert len(lessons_path.read_text()) > 0

    # -----------------------------------------------------------------------
    # Property test: 4 concurrent processes × 100 events = exactly 400 valid
    # JSONL lines (Tier2 #14 — Windows-safe atomic append via msvcrt.locking).
    # -----------------------------------------------------------------------

    def test_concurrent_multiprocess_append_no_corruption(self, tmp_path):
        """Spawn 4 processes, each emitting 100 events to the same events.jsonl.

        Asserts:
        - Exactly 401 lines in the file (1 INIT + 4 × 100).
        - Every line is valid JSON (no interleaved/partial lines).
        """
        from gradata._events import emit
        from gradata._paths import BrainContext

        brain_dir = tmp_path / "brain"
        brain_dir.mkdir(parents=True, exist_ok=True)

        # Initialise the DB schema once from the main process so sub-processes
        # do not race on table creation.
        ctx = BrainContext.from_brain_dir(brain_dir)
        emit("INIT", "main", ctx=ctx)  # seed schema + file

        num_workers = 4
        events_per_worker = 100

        processes = [
            multiprocessing.Process(
                target=_emit_worker,
                args=(str(brain_dir), events_per_worker, wid),
                daemon=True,
            )
            for wid in range(num_workers)
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=60)

        events_jsonl = ctx.events_jsonl
        raw = events_jsonl.read_text(encoding="utf-8")
        lines = [ln for ln in raw.splitlines() if ln.strip()]

        expected_total = 1 + num_workers * events_per_worker  # 1 INIT + 400

        # Every line must be parseable JSON — no corruption.
        parse_errors = []
        for idx, line in enumerate(lines):
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                parse_errors.append((idx, str(exc), line[:80]))

        assert parse_errors == [], (
            f"{len(parse_errors)} corrupted line(s) detected:\n"
            + "\n".join(f"  line {i}: {e} | preview: {pr}" for i, e, pr in parse_errors)
        )
        assert len(lines) == expected_total, (
            f"Expected {expected_total} lines, got {len(lines)}. "
            "Possible dropped or duplicated events."
        )
