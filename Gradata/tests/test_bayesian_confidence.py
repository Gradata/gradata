"""Tests for Bayesian confidence integration in self_improvement."""

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import update_confidence, format_lessons, parse_lessons


class TestBayesianConfidence:
    def test_reinforcing_increments_alpha(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.PATTERN,
            confidence=0.65,
            category="TONE",
            description="Be direct",
            alpha=3.0,
            beta_param=1.0,
        )
        corrections = [{"category": "TONE", "direction": "REINFORCING"}]
        update_confidence([lesson], corrections)
        assert lesson.alpha > 3.0
        assert lesson.beta_param == 1.0

    def test_contradicting_increments_beta(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.PATTERN,
            confidence=0.65,
            category="TONE",
            description="Be direct",
            alpha=3.0,
            beta_param=1.0,
        )
        corrections = [{"category": "TONE", "direction": "CONTRADICTING"}]
        update_confidence([lesson], corrections)
        assert lesson.alpha == 3.0
        assert lesson.beta_param > 1.0

    def test_bayesian_blending_produces_valid_confidence(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.INSTINCT,
            confidence=0.40,
            category="TONE",
            description="Be direct",
            alpha=1.0,
            beta_param=1.0,
        )
        for _ in range(5):
            corrections = [{"category": "TONE", "direction": "REINFORCING"}]
            update_confidence([lesson], corrections)
        assert 0.0 <= lesson.confidence <= 1.0
        assert lesson.alpha > 1.0

    def test_survival_does_not_touch_beta_params(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.PATTERN,
            confidence=0.65,
            category="TONE",
            description="Be direct",
            alpha=3.0,
            beta_param=1.0,
        )
        corrections = [{"category": "STYLE"}]
        update_confidence([lesson], corrections)
        assert lesson.alpha == 3.0
        assert lesson.beta_param == 1.0

    def test_alpha_beta_roundtrip(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.PATTERN,
            confidence=0.72,
            category="TONE",
            description="Be direct",
            alpha=8.5,
            beta_param=2.0,
            fire_count=7,
        )
        text = format_lessons([lesson])
        restored = parse_lessons(text)
        assert len(restored) == 1
        assert restored[0].alpha == 8.5
        assert restored[0].beta_param == 2.0
