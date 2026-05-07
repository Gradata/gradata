from __future__ import annotations

import json


def test_lesson_change_created_carries_parent_cloud_event_id(fresh_brain) -> None:
    result = fresh_brain.correct(
        "We maybe can discuss price later.",
        "State pricing clearly before the call to action.",
        category="PRICING",
        session=1,
    )

    assert result["type"] == "CORRECTION"
    correction_event_id = result["event_id"]

    events = [
        json.loads(line)
        for line in (fresh_brain.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    created = [
        ev
        for ev in events
        if ev["type"] == "LESSON_CHANGE" and ev["data"].get("action") == "created"
    ]

    assert created
    assert created[-1]["data"]["cloud_correction_event_id"] == correction_event_id
    assert isinstance(created[-1]["data"].get("source_correction_id"), int)
