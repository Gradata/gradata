"""Tests for rule domain scoping — per-domain misfire tracking and auto-disable."""
from gradata._types import Lesson, LessonState


def test_lesson_has_domain_scores_field():
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
    )
    assert hasattr(lesson, "domain_scores")
    assert lesson.domain_scores == {}


def test_domain_scores_round_trip():
    from gradata.enhancements.self_improvement import parse_lessons, format_lessons
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        fire_count=10,
        domain_scores={"CODE": {"fires": 8, "misfires": 1}, "DRAFTING": {"fires": 2, "misfires": 0}},
    )
    text = format_lessons([lesson])
    parsed = parse_lessons(text)
    assert len(parsed) == 1
    assert parsed[0].domain_scores == {"CODE": {"fires": 8, "misfires": 1}, "DRAFTING": {"fires": 2, "misfires": 0}}
