"""
CLB — Correction Learning Benchmark.

End-to-end functional test proving the graduation pipeline is wired:
  Brain.init() → log_output() → correct() → parse → update_confidence → graduate

This proves the PIPELINE WORKS, not that learning is statistically significant.
Statistical proof requires 200+ sessions (see GATE0-PROOF.md).
"""

import pytest

from gradata import Brain
from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import (
    parse_lessons,
    update_confidence,
    graduate,
    format_lessons,
    compute_learning_velocity,
    fsrs_bonus,
    fsrs_penalty,
    INITIAL_CONFIDENCE,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
)


@pytest.fixture
def brain(tmp_path):
    """Create a fresh brain for testing."""
    return Brain.init(str(tmp_path / "clb-brain"), domain="test", interactive=False)


class TestCLBWiring:
    """Prove the graduation pipeline is wired end-to-end."""

    def test_brain_init_creates_brain(self, brain):
        assert brain is not None
        assert brain.dir.exists()

    def test_log_output_with_rules_applied(self, brain):
        event = brain.log_output(
            "Draft email to CTO about demo",
            output_type="email",
            rules_applied=["DRAFTING:0042", "TONE:0017"],
        )
        assert event["type"] == "OUTPUT"
        assert event["data"]["rules_applied"] == ["DRAFTING:0042", "TONE:0017"]

    def test_correct_returns_event_with_diff(self, brain):
        event = brain.correct(
            draft="Please find attached the proposal.",
            final="Attached: the proposal for your review.",
        )
        assert event["type"] == "CORRECTION"
        assert "edit_distance" in event["data"]
        assert event["data"]["severity"] in ("as-is", "minor", "moderate", "major", "discarded")

    def test_correct_rejects_identical(self, brain):
        with pytest.raises(ValueError, match="identical"):
            brain.correct(draft="same text", final="same text")

    def test_correct_rejects_empty(self, brain):
        with pytest.raises(ValueError, match="empty"):
            brain.correct(draft="", final="")


class TestCLBGraduation:
    """Prove the graduation state machine works end-to-end."""

    def test_parse_format_roundtrip(self):
        text = "[2026-01-01] [INSTINCT:0.30] DRAFTING: Use tight prose.\n"
        lessons = parse_lessons(text)
        assert len(lessons) == 1
        assert lessons[0].state == LessonState.INSTINCT
        assert lessons[0].confidence == 0.30
        assert lessons[0].category == "DRAFTING"

        formatted = format_lessons(lessons)
        reparsed = parse_lessons(formatted)
        assert reparsed[0].category == "DRAFTING"
        assert reparsed[0].confidence == 0.30

    def test_confidence_increases_on_survival(self):
        lesson = Lesson("2026-01-01", LessonState.INSTINCT, 0.30, "DRAFTING", "test")
        result = update_confidence([lesson], [{"category": "ACCURACY"}])
        assert result[0].confidence > 0.30

    def test_confidence_decreases_on_contradiction(self):
        lesson = Lesson("2026-01-01", LessonState.INSTINCT, 0.50, "DRAFTING", "test")
        result = update_confidence([lesson], [{"category": "DRAFTING"}])
        assert result[0].confidence < 0.50

    def test_graduation_instinct_to_pattern(self):
        lesson = Lesson("2026-01-01", LessonState.INSTINCT, 0.55, "DRAFTING", "test")
        lesson.fire_count = 3
        # Survival should boost past PATTERN_THRESHOLD
        update_confidence([lesson], [{"category": "ACCURACY"}])
        assert lesson.state == LessonState.PATTERN

    def test_graduation_pattern_to_rule(self):
        lesson = Lesson("2026-01-01", LessonState.PATTERN, 0.85, "DRAFTING", "test")
        lesson.fire_count = 5
        update_confidence([lesson], [{"category": "ACCURACY"}])
        assert lesson.state == LessonState.RULE

    def test_graduate_splits_active_and_graduated(self):
        lessons = [
            Lesson("2026-01-01", LessonState.INSTINCT, 0.40, "A", "test"),
            Lesson("2026-01-01", LessonState.RULE, 0.95, "B", "test"),
        ]
        active, graduated = graduate(lessons)
        assert len(active) == 1
        assert len(graduated) == 1
        assert active[0].category == "A"
        assert graduated[0].category == "B"

    def test_full_lifecycle(self):
        """Simulate a lesson going from INSTINCT → PATTERN → RULE."""
        lesson = Lesson("2026-01-01", LessonState.INSTINCT, INITIAL_CONFIDENCE, "TONE", "Be concise")

        # Simulate 10 sessions of survival (corrections in other categories)
        for _ in range(10):
            update_confidence([lesson], [{"category": "ACCURACY"}])
            lesson.fire_count += 1  # simulate rule being applied

        # Should have graduated to at least PATTERN
        assert lesson.state in (LessonState.PATTERN, LessonState.RULE), (
            f"After 10 survivals + 10 fires, expected PATTERN+, got {lesson.state} "
            f"at confidence {lesson.confidence}"
        )

    def test_learning_velocity(self):
        lessons = [
            Lesson("2026-01-01", LessonState.RULE, 0.95, "A", "test"),
            Lesson("2026-01-01", LessonState.PATTERN, 0.70, "B", "test"),
            Lesson("2026-01-01", LessonState.INSTINCT, 0.30, "C", "test"),
        ]
        result = compute_learning_velocity(lessons)
        assert result["total_lessons"] == 3
        assert result["graduation_rate"] > 0  # at least 1 RULE


class TestCLBFSRS:
    """Verify FSRS-inspired confidence functions are well-behaved."""

    def test_bonus_diminishes_at_high_confidence(self):
        low = fsrs_bonus(0.20)
        high = fsrs_bonus(0.90)
        assert low > high, "Bonus should diminish at high confidence"

    def test_penalty_increases_at_high_confidence(self):
        low = fsrs_penalty(0.20)
        high = fsrs_penalty(0.90)
        assert high > low, "Penalty should increase at high confidence"

    def test_bonus_always_positive(self):
        for conf in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            assert fsrs_bonus(conf) > 0, f"Bonus should be positive at {conf}"

    def test_penalty_always_positive(self):
        for conf in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            assert fsrs_penalty(conf) > 0, f"Penalty should be positive at {conf}"

    def test_confidence_stays_bounded(self):
        """Confidence should never leave [0.0, 1.0] regardless of operations."""
        lesson = Lesson("2026-01-01", LessonState.INSTINCT, 0.99, "X", "test")
        for _ in range(20):
            update_confidence([lesson], [{"category": "Y"}])
        assert 0.0 <= lesson.confidence <= 1.0

        lesson2 = Lesson("2026-01-01", LessonState.INSTINCT, 0.01, "X", "test")
        for _ in range(20):
            update_confidence([lesson2], [{"category": "X"}])
        assert 0.0 <= lesson2.confidence <= 1.0
