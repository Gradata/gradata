"""Tests for behavioral_extractor — recurring pattern detection."""

from gradata.enhancements.behavioral_extractor import detect_recurring_patterns, RecurringPattern
from gradata._types import Lesson, LessonState


class TestRecurringPatterns:
    def _make_lesson(self, category, description, fire_count=3):
        return Lesson(
            date="2026-04-10",
            state=LessonState.PATTERN,
            confidence=0.65,
            category=category,
            description=description,
            fire_count=fire_count,
        )

    def test_groups_related_corrections_by_category(self):
        lessons = [
            self._make_lesson("TONE", "Use active voice in emails"),
            self._make_lesson("TONE", "Remove hedging from subject lines"),
            self._make_lesson("TONE", "Be direct in opening sentences"),
        ]
        patterns = detect_recurring_patterns(lessons)
        assert len(patterns) >= 1
        assert patterns[0].category == "TONE"
        assert patterns[0].correction_count >= 3

    def test_no_pattern_with_fewer_than_3(self):
        lessons = [
            self._make_lesson("TONE", "Use active voice"),
            self._make_lesson("TONE", "Be direct"),
        ]
        patterns = detect_recurring_patterns(lessons, min_corrections=3)
        assert len(patterns) == 0

    def test_multiple_category_patterns(self):
        lessons = [
            self._make_lesson("TONE", "Use active voice"),
            self._make_lesson("TONE", "Remove hedging"),
            self._make_lesson("TONE", "Be concise"),
            self._make_lesson("PROCESS", "Verify data before sending"),
            self._make_lesson("PROCESS", "Check CRM before drafting"),
            self._make_lesson("PROCESS", "Always confirm meeting time"),
        ]
        patterns = detect_recurring_patterns(lessons)
        categories = {p.category for p in patterns}
        assert "TONE" in categories
        assert "PROCESS" in categories

    def test_pattern_includes_summary(self):
        lessons = [
            self._make_lesson("TONE", "Use active voice"),
            self._make_lesson("TONE", "Remove hedging words"),
            self._make_lesson("TONE", "Be direct and concise"),
        ]
        patterns = detect_recurring_patterns(lessons)
        assert patterns[0].summary

    def test_empty_returns_empty(self):
        assert detect_recurring_patterns([]) == []
