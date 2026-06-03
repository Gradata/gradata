"""Regression tests for RULE_GRADUATED -> brain/rules/*.json materialization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gradata._types import Lesson, LessonState
from gradata.enhancements.rule_pipeline import run_rule_pipeline
from gradata.enhancements.self_improvement import format_lessons, graduate
from tests.conftest import init_brain


def _rule_id(category: str, description: str) -> str:
    return hashlib.sha256(f"{category}:{description}".encode("utf-8")).hexdigest()[:16]


def _pattern_to_rule_lesson() -> Lesson:
    return Lesson(
        date="2026-06-02",
        state=LessonState.PATTERN,
        confidence=0.95,
        category="ACCURACY",
        description="Always verify citations before submitting",
        fire_count=8,
        correction_event_ids=["evt_correction_1", "evt_correction_2"],
    )


def test_direct_pattern_to_rule_graduation_writes_rule_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BETA_LB_GATE", "0")
    brain = init_brain(tmp_path)
    lesson = _pattern_to_rule_lesson()

    graduate([lesson], brain=brain)

    rid = _rule_id("ACCURACY", "Always verify citations before submitting")
    rule_path = Path(brain.dir) / "rules" / f"{rid}.json"
    assert rule_path.is_file()
    data = json.loads(rule_path.read_text(encoding="utf-8"))
    assert data["rule_id"] == rid
    assert data["pattern"] == "Always verify citations before submitting"
    assert data["category"] == "ACCURACY"
    assert data["source"] == "graduate"
    assert data["source_correction_id"] == "evt_correction_1"
    assert data["source_correction_ids"] == ["evt_correction_1", "evt_correction_2"]
    assert data["graduation"]["old_state"] == "PATTERN"
    assert data["graduation"]["new_state"] == "RULE"
    assert data["graduation"]["reason"] == "pattern_to_rule"


def test_pipeline_pattern_to_rule_graduation_writes_rule_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BETA_LB_GATE", "0")
    lesson = _pattern_to_rule_lesson()
    lessons_path = tmp_path / "lessons.md"
    db_path = tmp_path / "system.db"
    lessons_path.write_text(format_lessons([lesson]), encoding="utf-8")

    result = run_rule_pipeline(lessons_path, db_path, current_session=99999)

    assert result.graduated == ["ACCURACY:Always verify citations before"]
    rid = _rule_id("ACCURACY", "Always verify citations before submitting")
    rule_path = tmp_path / "rules" / f"{rid}.json"
    assert rule_path.is_file()
    data = json.loads(rule_path.read_text(encoding="utf-8"))
    assert data["rule_id"] == rid
    assert data["pattern"] == "Always verify citations before submitting"
    assert data["graduation"]["session"] == 99999


def test_instinct_to_pattern_does_not_write_rule_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BETA_LB_GATE", "0")
    brain = init_brain(tmp_path)
    lesson = Lesson(
        date="2026-06-02",
        state=LessonState.INSTINCT,
        confidence=0.75,
        category="TONE",
        description="Prefer short sentences in emails",
        fire_count=5,
    )

    graduate([lesson], brain=brain)

    rules_dir = Path(brain.dir) / "rules"
    assert not rules_dir.exists() or list(rules_dir.glob("*.json")) == []
