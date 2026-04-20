"""Tests for _types.py dataclass fields."""

from gradata._types import Lesson, LessonState


class TestLessonBetaFields:
    def test_lesson_has_alpha_beta(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.INSTINCT,
            confidence=0.40,
            category="TONE",
            description="Be direct",
        )
        assert lesson.alpha == 1.0
        assert lesson.beta_param == 1.0

    def test_lesson_custom_alpha_beta(self):
        lesson = Lesson(
            date="2026-04-10",
            state=LessonState.PATTERN,
            confidence=0.72,
            category="TONE",
            description="Be direct",
            alpha=8.0,
            beta_param=3.0,
        )
        assert lesson.alpha == 8.0
        assert lesson.beta_param == 3.0
