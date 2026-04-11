"""Tests for budget-aware rule injection."""

from gradata._types import Lesson, LessonState
from gradata.rules.budget import ContextBudget, filter_by_budget, format_by_budget


def _make_lessons():
    return [
        Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="TONE",
            description="Be direct",
        ),
        Lesson(
            date="2026-01-02",
            state=LessonState.RULE,
            confidence=0.91,
            category="ACCURACY",
            description="Cite sources",
        ),
        Lesson(
            date="2026-01-03",
            state=LessonState.PATTERN,
            confidence=0.70,
            category="TONE",
            description="Match energy",
        ),
        Lesson(
            date="2026-01-04",
            state=LessonState.RULE,
            confidence=0.92,
            category="STRUCTURE",
            description="Lead with answer",
        ),
        Lesson(
            date="2026-01-05",
            state=LessonState.INSTINCT,
            confidence=0.45,
            category="FORMAT",
            description="No em dashes",
        ),
    ]


class TestFilterByBudget:
    def test_emergency_returns_one(self):
        result = filter_by_budget(_make_lessons(), budget=1)
        assert len(result) == 1
        assert result[0].confidence == 0.95

    def test_minimal_returns_two_rules_only(self):
        result = filter_by_budget(_make_lessons(), budget=2)
        assert len(result) == 2
        assert all(l.state == LessonState.RULE for l in result)

    def test_compact_returns_three_rules_only(self):
        result = filter_by_budget(_make_lessons(), budget=3)
        assert len(result) == 3
        assert all(l.state == LessonState.RULE for l in result)

    def test_standard_includes_patterns(self):
        result = filter_by_budget(_make_lessons(), budget=4)
        states = {l.state for l in result}
        assert LessonState.RULE in states

    def test_full_same_as_standard(self):
        r4 = filter_by_budget(_make_lessons(), budget=4)
        r5 = filter_by_budget(_make_lessons(), budget=5)
        assert len(r4) == len(r5)

    def test_instinct_excluded_at_all_levels(self):
        for budget in range(1, 6):
            result = filter_by_budget(_make_lessons(), budget=budget)
            assert all(l.state != LessonState.INSTINCT for l in result)


class TestFormatByBudget:
    def test_emergency_bare_text(self):
        l = _make_lessons()[0]
        assert format_by_budget(l, budget=1) == "Be direct"

    def test_minimal_category_prefix(self):
        l = _make_lessons()[0]
        assert format_by_budget(l, budget=2) == "TONE: Be direct"

    def test_standard_has_xml_and_confidence(self):
        l = _make_lessons()[0]
        result = format_by_budget(l, budget=4)
        assert "<rule" in result
        assert "0.95" in result
