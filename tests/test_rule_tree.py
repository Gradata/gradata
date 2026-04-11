"""Tests for hierarchical rule tree."""

import pytest
from gradata._types import Lesson, LessonState


class TestLessonTreeFields:
    def test_lesson_has_path_field(self):
        lesson = Lesson(
            date="2026-04-11",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="TONE",
            description="Be casual with VPs",
        )
        assert lesson.path == ""

    def test_lesson_has_secondary_categories(self):
        lesson = Lesson(
            date="2026-04-11",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="TONE",
            description="No em dashes",
            secondary_categories=["FORMAT"],
        )
        assert lesson.secondary_categories == ["FORMAT"]

    def test_lesson_has_climb_tracking(self):
        lesson = Lesson(
            date="2026-04-11",
            state=LessonState.INSTINCT,
            confidence=0.50,
            category="TONE",
            description="Be direct",
        )
        assert lesson.climb_count == 0
        assert lesson.last_climb_session == 0
        assert lesson.tree_level == 0
