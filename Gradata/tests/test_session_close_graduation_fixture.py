"""CI fixture for Stop/session-close graduation into AGENTS.md.

Regression coverage for GRA-1102: the Stop hook should take a deterministic
synthetic brain with INSTINCT entries, run the gated session-close sweep without
manual intervention, and leave a promoted RULE visible in the agent rules
payload.
"""

from __future__ import annotations

from pathlib import Path

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons, parse_lessons
from gradata.enhancements.rule_export import export_rules
from gradata.hooks import session_close
from tests.conftest import init_brain


def test_stop_session_close_sweep_graduates_rule_into_agents_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BETA_LB_GATE", "0")
    monkeypatch.setenv("GRADATA_TELEMETRY", "off")
    brain = init_brain(tmp_path)
    monkeypatch.setenv("BRAIN_DIR", str(brain.dir))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(brain.dir))

    lessons = [
        Lesson(
            date="2026-06-04",
            state=LessonState.INSTINCT,
            confidence=0.41,
            category="FIXTURE",
            description="Synthetic low-confidence instinct one stays tentative",
            fire_count=1,
        ),
        Lesson(
            date="2026-06-04",
            state=LessonState.INSTINCT,
            confidence=0.45,
            category="FIXTURE",
            description="Synthetic low-confidence instinct two stays tentative",
            fire_count=1,
        ),
        Lesson(
            date="2026-06-04",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="FIXTURE",
            description="Synthetic low-confidence instinct three stays tentative",
            fire_count=1,
        ),
        Lesson(
            date="2026-06-04",
            state=LessonState.PATTERN,
            confidence=0.95,
            category="FIXTURE",
            description="Stop hook session-close sweep exports promoted rules",
            fire_count=3,
        ),
    ]
    lessons_path = Path(brain.dir) / "lessons.md"
    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

    before = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    assert sum(lesson.state == LessonState.INSTINCT for lesson in before) == 3
    assert not (Path(brain.dir) / "AGENTS.md").exists()

    # The Stop hook's heavy waterfall is gated on a new trigger event.
    brain.emit(
        "CORRECTION",
        "test.gra_1102_fixture",
        {"category": "FIXTURE", "description": "deterministic session-close trigger"},
        ["source_issue:GRA-1102"],
        session=4242,
    )

    result = session_close.main({"session_number": 4242})

    assert result is None
    assert (Path(brain.dir) / ".last_close_ts").is_file()
    after = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    promoted = [
        lesson
        for lesson in after
        if lesson.description == "Stop hook session-close sweep exports promoted rules"
    ]
    assert promoted and promoted[0].state == LessonState.RULE

    agents_path = Path(brain.dir) / "AGENTS.md"
    assert agents_path.is_file()
    agents_payload = agents_path.read_text(encoding="utf-8")
    assert "# AGENTS.md" in agents_payload
    assert "- Stop hook session-close sweep exports promoted rules" in agents_payload

    exported_payload = export_rules(Path(brain.dir), target="agents", lessons_path=lessons_path)
    assert "- Stop hook session-close sweep exports promoted rules" in exported_payload
