"""Tests for the self-healing engine."""
from __future__ import annotations

import pytest
from gradata._types import Lesson, LessonState


class TestDetectRuleFailure:
    """detect_rule_failure: given lessons + a correction category, find rules that should have prevented it."""

    def test_detects_failure_when_rule_covers_category(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks in emails",
            fire_count=8,
        )
        result = detect_rule_failure(
            lessons=[rule],
            correction_category="TONE",
            correction_description="Removed exclamation marks from email draft",
            min_confidence=0.80,
        )
        assert result is not None
        assert result["failed_rule_category"] == "TONE"
        assert result["failed_rule_description"] == rule.description
        assert result["failed_rule_confidence"] == 0.92

    def test_returns_none_when_no_rule_covers_category(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="FORMAT", description="Use bullet points in reports",
            fire_count=5,
        )
        result = detect_rule_failure(
            lessons=[rule],
            correction_category="TONE",
            correction_description="Fixed the tone",
        )
        assert result is None

    def test_ignores_low_confidence_rules(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        pattern = Lesson(
            date="2026-04-01", state=LessonState.PATTERN, confidence=0.65,
            category="TONE", description="Watch tone in emails",
            fire_count=4,
        )
        result = detect_rule_failure(
            lessons=[pattern],
            correction_category="TONE",
            correction_description="Fixed tone",
            min_confidence=0.80,
        )
        assert result is None

    def test_ignores_killed_rules(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        killed = Lesson(
            date="2026-04-01", state=LessonState.KILLED, confidence=0.95,
            category="TONE", description="Old tone rule",
            fire_count=10, kill_reason="manual_rollback",
        )
        result = detect_rule_failure(
            lessons=[killed],
            correction_category="TONE",
            correction_description="Fixed tone",
        )
        assert result is None

    def test_includes_memory_context_when_provided(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
        )
        memory_ctx = {"active_memories": ["user prefers formal tone"], "domain": "sales"}
        result = detect_rule_failure(
            lessons=[rule],
            correction_category="TONE",
            correction_description="Removed exclamation marks",
            memory_context=memory_ctx,
        )
        assert result is not None
        assert result["memory_context"] == memory_ctx

    def test_picks_highest_confidence_rule_on_multi_match(self):
        from gradata.enhancements.self_healing import detect_rule_failure

        rule_a = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.91,
            category="TONE", description="Be formal",
            fire_count=6,
        )
        rule_b = Lesson(
            date="2026-04-02", state=LessonState.RULE, confidence=0.95,
            category="TONE", description="Never use slang",
            fire_count=10,
        )
        result = detect_rule_failure(
            lessons=[rule_a, rule_b],
            correction_category="TONE",
            correction_description="Removed slang",
        )
        assert result is not None
        assert result["failed_rule_confidence"] == 0.95


class TestBrainCorrectRuleFailure:
    """brain.correct() emits RULE_FAILURE when a RULE should have caught the correction."""

    @pytest.fixture
    def brain_with_rule(self, tmp_path):
        """Create a brain with a graduated RULE in TONE category."""
        from gradata.brain import Brain
        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import format_lessons
        from gradata._db import write_lessons_safe

        brain = Brain.init(str(tmp_path / "test-brain"))
        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks in professional emails",
            fire_count=8,
        )
        lessons_path = brain._find_lessons_path(create=True)
        write_lessons_safe(lessons_path, format_lessons([rule]))
        return brain

    def test_correction_in_ruled_category_emits_rule_failure(self, brain_with_rule):
        result = brain_with_rule.correct(
            draft="Great to hear from you! Let's connect!",
            final="Great to hear from you. Let's connect.",
            category="TONE",
        )
        # Check that a RULE_FAILURE event was emitted
        events = brain_with_rule.query_events(event_type="RULE_FAILURE", limit=10)
        assert len(events) >= 1
        failure = events[0]
        assert failure["data"]["failed_rule_category"] == "TONE"
        assert failure["data"]["failed_rule_confidence"] >= 0.80

    def test_correction_in_unruled_category_no_rule_failure(self, brain_with_rule):
        result = brain_with_rule.correct(
            draft="wrong format", final="correct format",
            category="FORMAT",
        )
        events = brain_with_rule.query_events(event_type="RULE_FAILURE", limit=10)
        assert len(events) == 0


class TestPatchRule:
    """brain.patch_rule() rewrites a rule's description while preserving metadata."""

    @pytest.fixture
    def brain_with_rule(self, tmp_path):
        from gradata.brain import Brain
        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import format_lessons
        from gradata._db import write_lessons_safe

        brain = Brain.init(str(tmp_path / "test-brain"))
        rule = Lesson(
            date="2026-04-01", state=LessonState.RULE, confidence=0.92,
            category="TONE", description="Never use exclamation marks",
            fire_count=8,
        )
        lessons_path = brain._find_lessons_path(create=True)
        write_lessons_safe(lessons_path, format_lessons([rule]))
        return brain

    def test_patch_rewrites_description(self, brain_with_rule):
        result = brain_with_rule.patch_rule(
            category="TONE",
            old_description="Never use exclamation marks",
            new_description="Never use exclamation marks in professional emails (casual is OK)",
            reason="Rule was too broad - failed on casual context",
        )
        assert result["patched"] is True
        assert result["old_description"] == "Never use exclamation marks"
        assert result["new_description"].startswith("Never use exclamation marks in professional")

        # Verify the lesson was actually updated on disk
        lessons = brain_with_rule._load_lessons()
        tone_rules = [l for l in lessons if l.category == "TONE" and l.state.value == "RULE"]
        assert len(tone_rules) == 1
        assert "professional emails" in tone_rules[0].description

    def test_patch_preserves_confidence_and_metadata(self, brain_with_rule):
        result = brain_with_rule.patch_rule(
            category="TONE",
            old_description="Never use exclamation marks",
            new_description="Avoid exclamation marks in formal contexts",
            reason="Narrowing scope",
        )
        lessons = brain_with_rule._load_lessons()
        tone_rules = [l for l in lessons if l.category == "TONE"]
        assert tone_rules[0].confidence == 0.92
        assert tone_rules[0].fire_count == 8

    def test_patch_emits_rule_patched_event(self, brain_with_rule):
        brain_with_rule.patch_rule(
            category="TONE",
            old_description="Never use exclamation marks",
            new_description="Avoid exclamation marks in formal contexts",
            reason="Too broad",
        )
        events = brain_with_rule.query_events(event_type="RULE_PATCHED", limit=10)
        assert len(events) >= 1
        assert events[0]["data"]["reason"] == "Too broad"

    def test_patch_nonexistent_rule_returns_not_found(self, brain_with_rule):
        result = brain_with_rule.patch_rule(
            category="TONE",
            old_description="This rule does not exist",
            new_description="New version",
            reason="test",
        )
        assert result["patched"] is False
        assert "not_found" in result.get("error", "")
