from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from gradata._audit import run_audit


def _event(event_type: str, session: int, data: dict | None = None) -> str:
    return json.dumps(
        {
            "ts": datetime.now(UTC).isoformat(),
            "type": event_type,
            "session": session,
            "data": data or {},
        }
    )


def test_audit_calculates_recall_coverage(tmp_path: Path) -> None:
    (tmp_path / "events.jsonl").write_text(
        "\n".join(
            [
                _event("tool.call", 1),
                _event("rules.injected", 1, {"rules": ["a"]}),
                _event("tool.call", 2),
                _event("tool.call", 3),
                _event("recall.hit", 3, {"recall_hits": 2}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path)

    assert report["tool_call_sessions"] == 3
    assert report["recall_hit_sessions"] == 2
    assert report["recall_coverage_pct"] == 66.67
