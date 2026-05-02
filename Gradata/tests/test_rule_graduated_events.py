"""RULE_GRADUATED event emission — graduate() state transitions log to events.jsonl.

Unblocks Decision 4 (materializer): graduation state must be derivable from
events, not only from the SQLite lesson_transitions side-table. Each
INSTINCT/PATTERN/RULE/UNTESTABLE/KILLED transition emits a RULE_GRADUATED
event with {category, description, old_state, new_state, confidence,
fire_count, reason}.
"""

from __future__ import annotations

import json
from pathlib import Path

from gradata._types import Lesson, LessonState
from gradata.brain import Brain
from gradata.enhancements.self_improvement import graduate
from tests.conftest import init_brain


def _rule_graduated_events(brain: Brain) -> list[dict]:
    """Return decoded RULE_GRADUATED events from events.jsonl (preserves order)."""
    path = Path(brain.dir) / "events.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "RULE_GRADUATED":
            events.append(ev)
    return events


def test_instinct_to_pattern_emits_rule_graduated(tmp_path):
    brain = init_brain(tmp_path)
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.INSTINCT,
        confidence=0.75,  # > PATTERN_THRESHOLD (0.60)
        category="TONE",
        description="Prefer short sentences in emails",
        fire_count=5,  # >= MIN_APPLICATIONS_FOR_PATTERN (3)
    )
    graduate([lesson], brain=brain)

    events = _rule_graduated_events(brain)
    assert len(events) == 1, f"expected 1 RULE_GRADUATED event, got {len(events)}"
    data = events[0]["data"]
    assert data["old_state"] == "INSTINCT"
    assert data["new_state"] == "PATTERN"
    assert data["reason"] == "instinct_to_pattern"
    assert data["category"] == "TONE"
    assert data["confidence"] == 0.75
    assert data["fire_count"] == 5


def test_pattern_to_rule_emits_rule_graduated(tmp_path, monkeypatch):
    monkeypatch.setenv("GRADATA_BETA_LB_GATE", "0")
    brain = init_brain(tmp_path)
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.PATTERN,
        confidence=0.95,  # >= RULE_THRESHOLD (0.90)
        category="ACCURACY",
        description="Always verify citations before submitting",
        fire_count=8,  # >= MIN_APPLICATIONS_FOR_RULE (5)
    )
    graduate([lesson], brain=brain)

    events = _rule_graduated_events(brain)
    pattern_to_rule = [e for e in events if e["data"]["reason"] == "pattern_to_rule"]
    assert len(pattern_to_rule) == 1
    data = pattern_to_rule[0]["data"]
    assert data["old_state"] == "PATTERN"
    assert data["new_state"] == "RULE"


def test_demote_pattern_to_instinct_emits_rule_graduated(tmp_path):
    brain = init_brain(tmp_path)
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.PATTERN,
        confidence=0.40,  # < PATTERN_THRESHOLD (0.60)
        category="STYLE",
        description="Use an em dash between clauses",
        fire_count=3,
    )
    graduate([lesson], brain=brain)

    events = _rule_graduated_events(brain)
    assert len(events) == 1
    data = events[0]["data"]
    assert data["old_state"] == "PATTERN"
    assert data["new_state"] == "INSTINCT"
    assert data["reason"] == "demoted_below_threshold"


def test_zero_confidence_kill_emits_rule_graduated(tmp_path):
    brain = init_brain(tmp_path)
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.INSTINCT,
        confidence=0.0,  # triggers kill
        category="DRAFTING",
        description="Never start emails with 'I hope this finds you well'",
        fire_count=2,
    )
    graduate([lesson], brain=brain)

    events = _rule_graduated_events(brain)
    assert len(events) == 1
    data = events[0]["data"]
    assert data["new_state"] == "KILLED"
    assert data["reason"] == "zero_confidence"


def test_moved_to_untestable_emits_rule_graduated(tmp_path):
    brain = init_brain(tmp_path)
    # INFANT kill_limit is the baseline; sessions_since_fire must meet it.
    from gradata.enhancements.self_improvement._confidence import KILL_LIMITS

    kill_limit = KILL_LIMITS["INFANT"]
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.PATTERN,
        confidence=0.70,
        category="PROCESS",
        description="Run lint before committing",
        fire_count=4,
        sessions_since_fire=kill_limit,  # trips untestable path
    )
    graduate([lesson], brain=brain)

    events = _rule_graduated_events(brain)
    assert len(events) == 1
    data = events[0]["data"]
    assert data["old_state"] == "PATTERN"
    assert data["new_state"] == "UNTESTABLE"
    assert data["reason"] == "moved_to_untestable"


def test_no_transition_no_event(tmp_path):
    """A lesson below promotion threshold must NOT emit RULE_GRADUATED."""
    brain = init_brain(tmp_path)
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.INSTINCT,
        confidence=0.45,  # below PATTERN_THRESHOLD
        category="TONE",
        description="Prefer active voice",
        fire_count=2,  # below MIN_APPLICATIONS_FOR_PATTERN
    )
    graduate([lesson], brain=brain)

    events = _rule_graduated_events(brain)
    assert events == [], f"expected no events, got {events}"


def test_graduate_without_brain_still_emits(tmp_path):
    """graduate(brain=None) must still emit via module-level fallback path."""
    brain = init_brain(tmp_path)
    # Drop brain= kwarg — helper should fall back to globals (rewired by init_brain).
    lesson = Lesson(
        date="2026-04-21",
        state=LessonState.INSTINCT,
        confidence=0.75,
        category="TONE",
        description="Keep subject lines under 50 chars",
        fire_count=5,
    )
    graduate([lesson])  # no brain= kwarg

    events = _rule_graduated_events(brain)
    assert len(events) == 1
    assert events[0]["data"]["reason"] == "instinct_to_pattern"
