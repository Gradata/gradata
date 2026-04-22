"""emit() redacts PII before writing and keeps a raw side-log.

Contract:
1. ``events.jsonl`` + SQLite see only redacted values.
2. ``events.raw.jsonl`` keeps the un-redacted copy (best-effort, gitignored).
3. If the redactor raises, emit() fails closed — no redacted or raw row reaches
   cloud-syncable storage.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from gradata import _events as _ev
from gradata.exceptions import EventPersistenceError
from tests.conftest import init_brain


SECRET_EMAIL = "leaker@example.com"


def _events_jsonl_lines(brain) -> list[dict]:
    path = brain.dir / "events.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _raw_jsonl_lines(brain) -> list[dict]:
    path = brain.dir / "events.raw.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_emitted_event_is_redacted_in_canonical_log(tmp_path):
    brain = init_brain(tmp_path)
    brain.emit("T", "test", {"note": f"email me at {SECRET_EMAIL}"}, [])

    canon = _events_jsonl_lines(brain)
    ours = [e for e in canon if e["type"] == "T"]
    assert ours, "expected our event in events.jsonl"
    assert SECRET_EMAIL not in ours[-1]["data"]["note"]
    assert "[REDACTED_EMAIL]" in ours[-1]["data"]["note"]


def test_emitted_event_is_redacted_in_sqlite(tmp_path):
    brain = init_brain(tmp_path)
    brain.emit("T2", "test", {"note": f"ping {SECRET_EMAIL}"}, [])

    with sqlite3.connect(str(brain.dir / "system.db")) as conn:
        row = conn.execute("SELECT data_json FROM events WHERE type = 'T2'").fetchone()
    assert row is not None
    assert SECRET_EMAIL not in row[0]
    assert "[REDACTED_EMAIL]" in row[0]


def test_raw_side_log_keeps_original(tmp_path):
    brain = init_brain(tmp_path)
    brain.emit("T3", "test", {"note": f"reach me: {SECRET_EMAIL}"}, [])

    raw = _raw_jsonl_lines(brain)
    ours = [e for e in raw if e["type"] == "T3"]
    assert ours, "expected event in events.raw.jsonl"
    assert SECRET_EMAIL in ours[-1]["data"]["note"]


def test_nested_structures_are_redacted(tmp_path):
    brain = init_brain(tmp_path)
    brain.emit(
        "NESTED",
        "test",
        {
            "outer": {"inner": f"user {SECRET_EMAIL}"},
            "list": [{"email": SECRET_EMAIL}],
        },
        [],
    )
    canon = _events_jsonl_lines(brain)
    ours = [e for e in canon if e["type"] == "NESTED"]
    assert ours
    d = ours[-1]["data"]
    assert SECRET_EMAIL not in d["outer"]["inner"]
    assert SECRET_EMAIL not in d["list"][0]["email"]


def test_redactor_failure_aborts_write(tmp_path, monkeypatch):
    """If _redact_payload raises, emit() must not persist to JSONL or SQLite."""
    brain = init_brain(tmp_path)

    def _boom(_obj):
        raise RuntimeError("redactor exploded")

    monkeypatch.setattr(_ev, "_redact_payload", _boom)

    with pytest.raises(Exception):  # EventPersistenceError or the raw RuntimeError
        brain.emit("SHOULD_NOT_LAND", "test", {"note": SECRET_EMAIL}, [])

    # Canonical log must not contain the event.
    canon = _events_jsonl_lines(brain)
    assert all(e["type"] != "SHOULD_NOT_LAND" for e in canon)
    with sqlite3.connect(str(brain.dir / "system.db")) as conn:
        row = conn.execute("SELECT 1 FROM events WHERE type = 'SHOULD_NOT_LAND'").fetchone()
    assert row is None


def test_raw_side_log_failure_does_not_block_canonical_write(tmp_path, monkeypatch):
    """events.raw.jsonl write is best-effort; a failure must not break emit()."""
    brain = init_brain(tmp_path)

    original_locked_append = _ev._locked_append

    def _maybe_fail(path, line):
        if path.name == "events.raw.jsonl":
            raise OSError("simulated raw-log disk full")
        return original_locked_append(path, line)

    monkeypatch.setattr(_ev, "_locked_append", _maybe_fail)

    # Must not raise.
    brain.emit("STILL_LANDS", "test", {"note": "hi"}, [])
    canon = _events_jsonl_lines(brain)
    assert any(e["type"] == "STILL_LANDS" for e in canon)


# Keep unused-import check honest: silence the ``EventPersistenceError`` noise.
_ = EventPersistenceError
