"""Tests for the lesson_applications audit trail.

Verifies the compound-quality loop:
  1. inject_brain_rules writes a PENDING row per injected rule.
  2. session_close resolves PENDING to CONFIRMED when the session has no
     matching correction.
  3. session_close resolves PENDING to REJECTED when a CORRECTION in the
     same session shares the lesson's category.
  4. Injection does not fail when system.db is absent.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

from gradata.hooks.inject_brain_rules import main as inject_main
from gradata.hooks.session_close import _resolve_pending_applications
from gradata.onboard import _create_db


def _setup_brain(tmp_path: Path, lessons_text: str) -> Path:
    (tmp_path / "lessons.md").write_text(lessons_text, encoding="utf-8")
    _create_db(tmp_path / "system.db")
    return tmp_path


def _lesson_applications(brain_dir: Path) -> list[tuple]:
    conn = sqlite3.connect(brain_dir / "system.db")
    rows = conn.execute(
        "SELECT lesson_id, session, outcome, success FROM lesson_applications ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def test_injection_writes_pending_rows(tmp_path):
    brain = _setup_brain(
        tmp_path,
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n"
        "[2026-04-01] [PATTERN:0.65] TONE: Use casual tone in emails\n",
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(brain)}):
        result = inject_main({"session_number": 7})
    assert result is not None
    rows = _lesson_applications(brain)
    assert len(rows) >= 2
    outcomes = {r[2] for r in rows}
    assert outcomes == {"PENDING"}
    sessions = {r[1] for r in rows}
    assert sessions == {7}


def test_session_close_confirms_without_correction(tmp_path):
    brain = _setup_brain(
        tmp_path,
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(brain)}):
        inject_main({"session_number": 11})
    _resolve_pending_applications(str(brain), {"session_number": 11})
    rows = _lesson_applications(brain)
    assert rows, "expected at least one lesson_applications row"
    for _, _, outcome, success in rows:
        assert outcome == "CONFIRMED"
        assert success == 1


def test_session_close_rejects_on_category_correction(tmp_path):
    brain = _setup_brain(
        tmp_path,
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n"
        "[2026-04-01] [PATTERN:0.65] TONE: Use casual tone in emails\n",
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(brain)}):
        inject_main({"session_number": 22})

    conn = sqlite3.connect(brain / "system.db")
    conn.execute(
        "INSERT INTO events (ts, session, type, source, data_json) "
        "VALUES (?, ?, 'CORRECTION', 'test', ?)",
        (
            "2026-04-20T12:00:00+00:00",
            22,
            json.dumps({"category": "PROCESS", "snippet": "no, plan first"}),
        ),
    )
    conn.commit()
    conn.close()

    _resolve_pending_applications(str(brain), {"session_number": 22})

    conn = sqlite3.connect(brain / "system.db")
    by_category: dict[str, str] = {}
    for ctx_raw, outcome in conn.execute(
        "SELECT context, outcome FROM lesson_applications"
    ).fetchall():
        ctx = json.loads(ctx_raw) if ctx_raw else {}
        by_category[ctx.get("category", "")] = outcome
    conn.close()
    assert by_category.get("PROCESS") == "REJECTED"
    assert by_category.get("TONE") == "CONFIRMED"


def test_session_close_rejects_on_implicit_feedback(tmp_path):
    """IMPLICIT_FEEDBACK events (text-speak corrections) must also flip PENDING→REJECTED."""
    brain = _setup_brain(
        tmp_path,
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(brain)}):
        inject_main({"session_number": 33})

    conn = sqlite3.connect(brain / "system.db")
    conn.execute(
        "INSERT INTO events (ts, session, type, source, data_json) "
        "VALUES (?, ?, 'IMPLICIT_FEEDBACK', 'user_prompt', ?)",
        (
            "2026-04-20T12:00:00+00:00",
            33,
            json.dumps({"category": "PROCESS", "signal_type": "challenge"}),
        ),
    )
    conn.commit()
    conn.close()

    _resolve_pending_applications(str(brain), {"session_number": 33})
    rows = _lesson_applications(brain)
    assert rows, "expected at least one lesson_applications row"
    # The sole PROCESS rule must be rejected on the IMPLICIT_FEEDBACK signal.
    outcomes = {r[2] for r in rows}
    assert outcomes == {"REJECTED"}


def test_injection_no_db_is_silent(tmp_path):
    (tmp_path / "lessons.md").write_text(
        "[2026-04-01] [RULE:0.92] PROCESS: Always plan before implementing\n",
        encoding="utf-8",
    )
    # No system.db — inject_main must still return a result, just no writes.
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = inject_main({"session_number": 1})
    assert result is not None
    assert "brain-rules" in result.get("result", "")
