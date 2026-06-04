"""Regression tests for GRA-2094 / GRA-2060 pending approval drain visibility."""

from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path


def test_session_close_drain_emits_review_event_for_public_correction_path(
    tmp_path: Path, monkeypatch
):
    """GRA-2060: pending_approvals must not remain a silent dead-end forever.

    The fixture captures a pending approval through the public Brain.correct()
    path, runs the same session_close sweep used by hooks, then asserts the
    processor creates an explicit terminal/visible state event for the pending
    row. This prevents regressions where rows sit in pending_approvals with no
    consumer reading them.
    """
    monkeypatch.delenv("BRAIN_DIR", raising=False)
    monkeypatch.delenv("GRADATA_BRAIN", raising=False)
    monkeypatch.delenv("GRADATA_BRAIN_DIR", raising=False)
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)

    brain_dir = tmp_path / "gra-2094-brain"
    monkeypatch.setenv("BRAIN_DIR", str(brain_dir))

    import gradata._paths as paths
    from gradata.brain import Brain
    from gradata.hooks import session_close

    importlib.reload(paths)

    brain = Brain.init(brain_dir, name="GRA-2094", domain="Testing", interactive=False)
    event = brain.correct(
        "Use em dashes in every outbound email.",
        "Do not use em dashes in outbound email.",
        category="DRAFTING",
        context={"source": "public-hook-fixture", "issue": "GRA-2060"},
        session=2060,
        approval_required=True,
    )
    assert event.get("approval_required") is True

    with sqlite3.connect(brain_dir / "system.db") as conn:
        pending_before = conn.execute(
            "SELECT id, resolution FROM pending_approvals WHERE resolution IS NULL"
        ).fetchall()
    assert len(pending_before) == 1

    session_close.main({"session_number": 2060})

    with sqlite3.connect(brain_dir / "system.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT type, data_json FROM events WHERE type = 'PENDING_APPROVAL'"
        ).fetchall()

    assert rows, "session_close must drain/mark pending_approvals rows explicitly"
    payloads = [json.loads(row["data_json"]) for row in rows]
    assert any(
        payload.get("source_issue") == "GRA-2060"
        and payload.get("status") == "awaiting_human_review"
        and payload.get("approval_id") == pending_before[0][0]
        for payload in payloads
    )

    with sqlite3.connect(brain_dir / "system.db") as conn:
        still_pending = conn.execute(
            "SELECT id FROM pending_approvals WHERE id = ? AND resolution IS NULL",
            (pending_before[0][0],),
        ).fetchone()
    assert still_pending is not None, "reviewable approvals stay open for human approval"
