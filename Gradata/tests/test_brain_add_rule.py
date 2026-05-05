"""Unit tests for ``Brain.add_rule``.

Covers:
    * happy path (writes via canonical parse/format round-trip)
    * duplicate detection (category + normalized description)
    * missing category / empty description rejection
    * confidence clamping ([0.0, 1.0])
    * unknown state rejection
    * default state=RULE, confidence=0.90
    * extra ``data`` dict applies only to known Lesson fields
    * schema evolution guarantee: round-trip via parse_lessons / format_lessons
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gradata import Brain
from gradata._types import LessonState
from gradata.enhancements.self_improvement import parse_lessons


@pytest.fixture
def brain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Brain:
    # Scope BRAIN_DIR via monkeypatch so it's auto-reverted after each test
    # and can't leak into unrelated tests (the raw os.environ.__setitem__
    # approach persisted beyond the test that set it).
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "brain"))
    b = Brain.init(
        tmp_path / "brain",
        name="AddRuleTest",
        domain="Testing",
        embedding="local",
        interactive=False,
    )
    return b


class TestAddRuleHappyPath:
    def test_creates_lesson_with_defaults(self, brain: Brain) -> None:
        result = brain.add_rule("Use colons not em-dashes", "DRAFTING")
        assert result["added"] is True
        assert result["state"] == "RULE"
        assert result["confidence"] == 0.90

        # Round-trips through parse_lessons — confirming canonical schema path
        text = (brain.dir / "lessons.md").read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        assert len(lessons) == 1
        l = lessons[0]
        assert l.description == "Use colons not em-dashes"
        assert l.category == "DRAFTING"
        assert l.state == LessonState.RULE
        assert l.confidence == 0.90

    def test_accepts_custom_state_and_confidence(self, brain: Brain) -> None:
        result = brain.add_rule("Prototype idea", "DRAFTING", state="INSTINCT", confidence=0.3)
        assert result["added"] is True
        assert result["state"] == "INSTINCT"
        assert result["confidence"] == 0.30

    def test_accepts_state_lowercase(self, brain: Brain) -> None:
        result = brain.add_rule("Test", "CAT", state="pattern")
        assert result["added"] is True
        assert result["state"] == "PATTERN"


class TestAddRuleRejection:
    def test_empty_description_rejected(self, brain: Brain) -> None:
        result = brain.add_rule("", "DRAFTING")
        assert result["added"] is False
        assert result["reason"] == "empty_description"

    def test_whitespace_description_rejected(self, brain: Brain) -> None:
        result = brain.add_rule("   ", "DRAFTING")
        assert result["added"] is False
        assert result["reason"] == "empty_description"

    def test_empty_category_rejected(self, brain: Brain) -> None:
        result = brain.add_rule("Some rule", "")
        assert result["added"] is False
        assert result["reason"] == "empty_category"

    def test_unknown_state_rejected(self, brain: Brain) -> None:
        result = brain.add_rule("Some rule", "CAT", state="BOGUS")
        assert result["added"] is False
        assert "unknown_state" in result["reason"]

    def test_invalid_confidence_rejected(self, brain: Brain) -> None:
        result = brain.add_rule("Some rule", "CAT", confidence="high")  # type: ignore[arg-type]
        assert result["added"] is False
        assert "invalid_confidence" in result["reason"]


class TestAddRuleDuplicates:
    def test_exact_duplicate_rejected(self, brain: Brain) -> None:
        first = brain.add_rule("Be concise", "DRAFTING")
        assert first["added"] is True

        second = brain.add_rule("Be concise", "DRAFTING")
        assert second["added"] is False
        assert second["reason"] == "duplicate"

    def test_whitespace_normalized_duplicate_rejected(self, brain: Brain) -> None:
        brain.add_rule("Be concise", "DRAFTING")
        dup = brain.add_rule("be   Concise", "DRAFTING")
        assert dup["added"] is False
        assert dup["reason"] == "duplicate"

    def test_different_category_allowed(self, brain: Brain) -> None:
        brain.add_rule("Be concise", "DRAFTING")
        other = brain.add_rule("Be concise", "PROCESS")
        assert other["added"] is True


class TestAddRuleConfidenceClamp:
    def test_over_one_clamped(self, brain: Brain) -> None:
        result = brain.add_rule("R1", "CAT", confidence=1.5)
        assert result["added"] is True
        assert result["confidence"] == 1.0

    def test_under_zero_clamped(self, brain: Brain) -> None:
        result = brain.add_rule("R2", "CAT", confidence=-0.5)
        assert result["added"] is True
        assert result["confidence"] == 0.0


class TestAddRuleData:
    def test_known_data_fields_applied(self, brain: Brain) -> None:
        result = brain.add_rule(
            "Use colons",
            "DRAFTING",
            data={"root_cause": "em-dashes are slop", "agent_type": "writer"},
        )
        assert result["added"] is True

        lessons = parse_lessons((brain.dir / "lessons.md").read_text(encoding="utf-8"))
        l = lessons[0]
        assert l.root_cause == "em-dashes are slop"
        assert l.agent_type == "writer"

    def test_unknown_data_keys_silently_ignored(self, brain: Brain) -> None:
        # Must not raise — graceful degradation for forward/back compat
        result = brain.add_rule(
            "R",
            "CAT",
            data={"nonexistent_field": "xyz", "root_cause": "keep this"},
        )
        assert result["added"] is True
        lessons = parse_lessons((brain.dir / "lessons.md").read_text(encoding="utf-8"))
        assert lessons[0].root_cause == "keep this"

    def test_protected_fields_ignored_in_data(self, brain: Brain) -> None:
        # data={"description": ...} must NOT override the explicit arg
        result = brain.add_rule(
            "Real description",
            "CAT",
            data={
                "description": "OVERRIDE",
                "category": "OTHER",
                "confidence": 0.0,
                "state": LessonState.INSTINCT,
            },
        )
        assert result["added"] is True
        lessons = parse_lessons((brain.dir / "lessons.md").read_text(encoding="utf-8"))
        l = lessons[0]
        assert l.description == "Real description"
        assert l.category == "CAT"
        assert l.state == LessonState.RULE
        assert l.confidence == 0.90


class TestAddRuleEvent:
    def test_emits_lesson_added_event(self, brain: Brain) -> None:
        brain.add_rule("R", "CAT")
        events = brain.query_events(event_type="LESSON_ADDED")
        assert len(events) == 1
        ev = events[0]
        assert ev["data"]["category"] == "CAT"
        assert ev["data"]["description"] == "R"
        assert ev["data"]["state"] == "RULE"
