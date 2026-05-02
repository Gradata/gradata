from __future__ import annotations

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import graduate
from gradata.enhancements.self_improvement._confidence import (
    INITIAL_CONFIDENCE,
    MIN_APPLICATIONS_FOR_PATTERN,
    PATTERN_THRESHOLD,
)


def _lesson(confidence: float, fire_count: int) -> Lesson:
    return Lesson(
        date="2026-05-02",
        state=LessonState.INSTINCT,
        confidence=confidence,
        category="PROCESS",
        description="Follow the existing process",
        fire_count=fire_count,
    )


def test_fresh_lesson_starts_as_instinct() -> None:
    lesson = _lesson(INITIAL_CONFIDENCE, 0)

    assert lesson.state is LessonState.INSTINCT


def test_pattern_threshold_tie_does_not_promote() -> None:
    lesson = _lesson(PATTERN_THRESHOLD, MIN_APPLICATIONS_FOR_PATTERN)

    active, graduated = graduate([lesson])

    assert lesson.state is LessonState.INSTINCT
    assert active == [lesson]
    assert graduated == []


def test_above_pattern_threshold_with_enough_fires_promotes() -> None:
    lesson = _lesson(PATTERN_THRESHOLD + 0.01, MIN_APPLICATIONS_FOR_PATTERN)

    graduate([lesson])

    assert lesson.state is LessonState.PATTERN
