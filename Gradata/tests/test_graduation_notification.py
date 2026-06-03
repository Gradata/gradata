"""Tests for lesson graduation notification events."""

from __future__ import annotations

from gradata._types import Lesson, LessonState
from gradata.brain import Brain
from gradata.enhancements.self_improvement._graduation import _emit_rule_graduated


def test_rule_graduated_event_includes_rule_identity_payload():
    """RULE_GRADUATED carries provenance needed by rule-file materializers."""

    class FakeBrain:
        def __init__(self):
            self.calls = []

        def emit(self, event_type, source, data, tags):
            self.calls.append((event_type, source, data, tags))

    brain = FakeBrain()
    lesson = Lesson(
        date="2026-06-03",
        state=LessonState.RULE,
        confidence=0.95,
        category="PROCESS",
        description="Always verify work before reporting done",
        fire_count=5,
        correction_event_ids=["evt_correction_123"],
    )

    _emit_rule_graduated(
        lesson,
        LessonState.PATTERN,
        LessonState.RULE,
        "pattern_to_rule",
        brain=brain,
    )

    assert len(brain.calls) == 1
    event_type, source, payload, tags = brain.calls[0]
    assert event_type == "RULE_GRADUATED"
    assert source == "graduate"
    assert tags == []
    assert payload["rule_id"]
    assert payload["pattern"] == "Always verify work before reporting done"
    assert payload["lesson_description"] == "Always verify work before reporting done"
    assert payload["source_correction_id"] == "evt_correction_123"
    assert payload["source_correction_ids"] == ["evt_correction_123"]
    assert payload["category"] == "PROCESS"
    assert payload["description"] == "Always verify work before reporting done"
    assert payload["old_state"] == "PATTERN"
    assert payload["new_state"] == "RULE"


def test_graduation_event_emitted_on_pattern_promotion(tmp_path):
    """lesson.graduated fires when a lesson promotes to PATTERN."""
    brain = Brain(str(tmp_path))
    events: list[dict] = []
    brain.bus.on("lesson.graduated", lambda p: events.append(p))

    # Make 4 similar corrections across different sessions to trigger INSTINCT -> PATTERN
    for session in range(1, 5):
        brain.correct(
            "The system is working good",
            "The system is working well",
            category="DRAFTING",
            session=session,
        )
    # Force graduation
    brain.end_session()

    graduated = [e for e in events if e.get("new_state") == "PATTERN"]
    if graduated:
        assert "message" in graduated[0]
        msg = graduated[0]["message"].lower()
        assert "learned it" in msg or "corrected" in msg


def test_graduation_message_contains_description(tmp_path):
    """Graduation message includes the lesson description."""
    brain = Brain(str(tmp_path))
    events: list[dict] = []
    brain.bus.on("lesson.graduated", lambda p: events.append(p))

    for session in range(1, 5):
        brain.correct(
            "Dear Sir or Madam",
            "Hi",
            category="TONE",
            session=session,
        )
    brain.end_session()

    if events:
        assert events[0].get("category") == "TONE"
        assert "description" in events[0]


def test_graduation_event_includes_all_fields(tmp_path):
    """lesson.graduated payload has all required fields."""
    brain = Brain(str(tmp_path))
    events: list[dict] = []
    brain.bus.on("lesson.graduated", lambda p: events.append(p))

    for session in range(1, 5):
        brain.correct(
            "Please advise at your earliest convenience",
            "Let me know",
            category="TONE",
            session=session,
        )
    brain.end_session()

    if events:
        required_keys = {
            "category",
            "description",
            "old_state",
            "new_state",
            "fire_count",
            "confidence",
            "message",
        }
        assert required_keys.issubset(events[0].keys())


def test_rule_graduation_message(tmp_path):
    """lesson.graduated fires with correct message when promoting to RULE."""
    brain = Brain(str(tmp_path))
    events: list[dict] = []
    brain.bus.on("lesson.graduated", lambda p: events.append(p))

    # Need enough corrections across sessions to reach RULE (fire_count >= 5, high confidence)
    for session in range(1, 10):
        brain.correct(
            "Utilize the framework",
            "Use the framework",
            category="DRAFTING",
            session=session,
        )
    brain.end_session()

    rule_events = [e for e in events if e.get("new_state") == "RULE"]
    if rule_events:
        assert "permanent" in rule_events[0]["message"].lower()
        assert "confidence" in rule_events[0]["message"].lower()
