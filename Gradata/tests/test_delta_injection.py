from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons

if TYPE_CHECKING:
    import pytest


def _lesson(i: int, prefix: str = "rule") -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=LessonState.RULE,
        confidence=0.95,
        category=f"CAT{i}",
        description=f"{prefix} {i} should be applied precisely",
    )


def _write_brain_config(brain_dir: Path, enabled: bool) -> None:
    (brain_dir / "brain-config.json").write_text(
        json.dumps({"delta_injection": enabled, "ranker": "flat"}),
        encoding="utf-8",
    )


def _write_lessons(brain_dir: Path, lessons: list[Lesson]) -> None:
    (brain_dir / "lessons.md").write_text(format_lessons(lessons), encoding="utf-8")


def _call_injection(
    monkeypatch: pytest.MonkeyPatch,
    brain_dir: Path,
    *,
    agent_type: str = "claude-code",
    session_id: str = "s1",
) -> str:
    from gradata.hooks import inject_brain_rules as inj

    monkeypatch.setattr(inj, "resolve_brain_dir", lambda: str(brain_dir))
    monkeypatch.setattr(inj, "load_meta_rules", lambda _db_path: [])
    monkeypatch.setattr(inj, "format_meta_rules_for_prompt", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(inj, "_wiki_categories", lambda _context: set())
    monkeypatch.setattr(inj, "rank_rules", lambda rules, **_kwargs: rules)
    monkeypatch.setattr(inj, "MAX_RULES", 25)

    result = inj.main(
        {
            "agent_type": agent_type,
            "session_id": session_id,
            "session_type": "coding",
            "session_number": 1,
        }
    )
    assert result is not None
    return result["result"]


def _log_rows(brain_dir: Path) -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(brain_dir / "system.db")
    try:
        return conn.execute(
            "SELECT agent_type, session_id, rule_ids FROM injection_log ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_delta_injection_false_keeps_full_injection(fresh_brain, monkeypatch) -> None:
    _write_brain_config(fresh_brain.dir, False)
    _write_lessons(fresh_brain.dir, [_lesson(i) for i in range(3)])

    first = _call_injection(monkeypatch, fresh_brain.dir, session_id="s1")
    second = _call_injection(monkeypatch, fresh_brain.dir, session_id="s2")

    assert "currently learned:" not in first
    assert "currently learned:" not in second
    assert "rule 0 should be applied precisely" in second
    assert _log_rows(fresh_brain.dir) == []


def test_delta_injection_first_session_injects_full_set(fresh_brain, monkeypatch) -> None:
    _write_brain_config(fresh_brain.dir, True)
    _write_lessons(fresh_brain.dir, [_lesson(i) for i in range(3)])

    result = _call_injection(monkeypatch, fresh_brain.dir, session_id="s1")

    assert "currently learned: 3 rules, 3 new since last session" in result
    assert "rule 0 should be applied precisely" in result
    assert "rule 2 should be applied precisely" in result


def test_delta_injection_second_session_no_changes_header_only(fresh_brain, monkeypatch) -> None:
    _write_brain_config(fresh_brain.dir, True)
    _write_lessons(fresh_brain.dir, [_lesson(i) for i in range(3)])

    _call_injection(monkeypatch, fresh_brain.dir, session_id="s1")
    result = _call_injection(monkeypatch, fresh_brain.dir, session_id="s2")

    assert "currently learned: 3 rules, 0 new since last session" in result
    assert "you already know everything; 3 rules active" in result
    assert "<brain-rules>" not in result
    assert "rule 0 should be applied precisely" not in result


def test_delta_injection_second_session_only_three_new_rules(fresh_brain, monkeypatch) -> None:
    _write_brain_config(fresh_brain.dir, True)
    old_lessons = [_lesson(i) for i in range(10)]
    _write_lessons(fresh_brain.dir, old_lessons)
    _call_injection(monkeypatch, fresh_brain.dir, session_id="s1")

    new_lessons = old_lessons + [_lesson(i, "new rule") for i in range(10, 13)]
    _write_lessons(fresh_brain.dir, new_lessons)
    result = _call_injection(monkeypatch, fresh_brain.dir, session_id="s2")

    assert "currently learned: 13 rules, 3 new since last session" in result
    assert "new rule 10 should be applied precisely" in result
    assert "new rule 12 should be applied precisely" in result
    assert "rule 0 should be applied precisely" not in result


def test_delta_injection_reanchors_when_more_than_30_percent_changed(
    fresh_brain,
    monkeypatch,
) -> None:
    _write_brain_config(fresh_brain.dir, True)
    _write_lessons(fresh_brain.dir, [_lesson(i) for i in range(6)])
    _call_injection(monkeypatch, fresh_brain.dir, session_id="s1")

    _write_lessons(
        fresh_brain.dir, [_lesson(i) for i in range(3)] + [_lesson(i, "new") for i in range(3, 6)]
    )
    result = _call_injection(monkeypatch, fresh_brain.dir, session_id="s2")

    assert "currently learned: 6 rules, 6 new since last session" in result
    assert "rule 0 should be applied precisely" in result


def test_delta_injection_is_tracked_per_agent(fresh_brain, monkeypatch) -> None:
    _write_brain_config(fresh_brain.dir, True)
    _write_lessons(fresh_brain.dir, [_lesson(i) for i in range(3)])

    _call_injection(monkeypatch, fresh_brain.dir, agent_type="claude-code", session_id="c1")
    claude_second = _call_injection(
        monkeypatch,
        fresh_brain.dir,
        agent_type="claude-code",
        session_id="c2",
    )
    codex_first = _call_injection(monkeypatch, fresh_brain.dir, agent_type="codex", session_id="x1")

    assert "0 new since last session" in claude_second
    assert "3 new since last session" in codex_first
    assert "rule 0 should be applied precisely" in codex_first


def test_delta_injection_log_records_each_call(fresh_brain, monkeypatch) -> None:
    _write_brain_config(fresh_brain.dir, True)
    _write_lessons(fresh_brain.dir, [_lesson(i) for i in range(3)])

    _call_injection(monkeypatch, fresh_brain.dir, session_id="s1")
    _call_injection(monkeypatch, fresh_brain.dir, session_id="s2")

    rows = _log_rows(fresh_brain.dir)
    assert [(r[0], r[1]) for r in rows] == [("claude-code", "s1"), ("claude-code", "s2")]
    assert len(json.loads(rows[0][2])) == 3
