from __future__ import annotations

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import graduate


def _lesson(
    *,
    state: LessonState,
    confidence: float,
    fire_count: int,
    category: str = "PROCESS",
    description: str = "Confirm the business constraint before drafting",
) -> Lesson:
    return Lesson(
        date="2026-05-07",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
    )


def test_three_low_volume_corrections_can_reach_pattern() -> None:
    lesson = _lesson(
        state=LessonState.INSTINCT,
        confidence=0.65,
        fire_count=3,
    )

    graduate([lesson])

    assert lesson.state == LessonState.PATTERN


def test_four_low_volume_corrections_can_reach_rule() -> None:
    lesson = _lesson(
        state=LessonState.PATTERN,
        confidence=0.92,
        fire_count=4,
    )
    lesson.alpha = 40.0
    lesson.beta_param = 1.0

    graduate([lesson])

    assert lesson.state == LessonState.RULE


def test_beta_lower_bound_still_blocks_noisy_small_samples() -> None:
    lesson = _lesson(
        state=LessonState.PATTERN,
        confidence=0.95,
        fire_count=3,
    )
    lesson.alpha = 2.0
    lesson.beta_param = 2.0

    graduate([lesson])

    assert lesson.state == LessonState.PATTERN
