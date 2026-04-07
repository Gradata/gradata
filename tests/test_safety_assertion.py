"""Tests for graduate() safety assertions and fire-count guards.

Validates that:
- INSTINCT cannot promote to PATTERN without 3+ fires
- PATTERN cannot promote to RULE without 5+ fires
- Zero confidence never promotes regardless of fires
- graduate() docstring documents the fire-count requirements
- Confidence jump warning fires when _pre_session_confidence is set
"""

from __future__ import annotations

import logging

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import (
    MIN_APPLICATIONS_FOR_PATTERN,
    MIN_APPLICATIONS_FOR_RULE,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
    graduate,
)


def _make_lesson(
    *,
    state: LessonState = LessonState.INSTINCT,
    confidence: float = 0.50,
    fire_count: int = 0,
    category: str = "TEST",
    description: str = "test lesson",
) -> Lesson:
    return Lesson(
        date="2026-04-07",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
    )


class TestFireCountGuards:
    """INSTINCT->PATTERN requires 3+ fires, PATTERN->RULE requires 5+ fires."""

    def test_no_pattern_without_3_fires(self) -> None:
        """High confidence alone cannot promote INSTINCT -> PATTERN."""
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=PATTERN_THRESHOLD + 0.05,
            fire_count=MIN_APPLICATIONS_FOR_PATTERN - 1,  # 2 fires, need 3
        )
        active, graduated = graduate([lesson])
        assert lesson.state == LessonState.INSTINCT, (
            f"Promoted to {lesson.state} with only {lesson.fire_count} fires"
        )

    def test_pattern_with_3_fires(self) -> None:
        """INSTINCT -> PATTERN succeeds with 3+ fires and sufficient confidence."""
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=PATTERN_THRESHOLD + 0.05,
            fire_count=MIN_APPLICATIONS_FOR_PATTERN,
        )
        active, graduated = graduate([lesson])
        assert lesson.state == LessonState.PATTERN

    def test_no_rule_without_5_fires(self) -> None:
        """High confidence alone cannot promote PATTERN -> RULE."""
        lesson = _make_lesson(
            state=LessonState.PATTERN,
            confidence=RULE_THRESHOLD + 0.01,
            fire_count=MIN_APPLICATIONS_FOR_RULE - 1,  # 4 fires, need 5
        )
        active, graduated = graduate([lesson])
        assert lesson.state == LessonState.PATTERN, (
            f"Promoted to {lesson.state} with only {lesson.fire_count} fires"
        )

    def test_rule_with_5_fires(self) -> None:
        """PATTERN -> RULE succeeds with 5+ fires and sufficient confidence."""
        lesson = _make_lesson(
            state=LessonState.PATTERN,
            confidence=RULE_THRESHOLD + 0.01,
            fire_count=MIN_APPLICATIONS_FOR_RULE,
        )
        active, graduated = graduate([lesson])
        assert lesson.state == LessonState.RULE


class TestZeroConfidenceNeverPromotes:
    """Zero confidence lessons get killed, never promoted."""

    def test_zero_confidence_instinct_killed(self) -> None:
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.0,
            fire_count=100,  # Lots of fires, but zero confidence
        )
        graduate([lesson])
        assert lesson.state == LessonState.KILLED

    def test_zero_confidence_pattern_killed(self) -> None:
        lesson = _make_lesson(
            state=LessonState.PATTERN,
            confidence=0.0,
            fire_count=100,
        )
        graduate([lesson])
        assert lesson.state == LessonState.KILLED


class TestDocstring:
    """graduate() docstring must document fire-count requirements."""

    def test_docstring_mentions_min_applications(self) -> None:
        doc = graduate.__doc__
        assert doc is not None, "graduate() has no docstring"
        # Must mention the 3-fire requirement
        assert "3" in doc or "MIN_APPLICATIONS" in doc, (
            "Docstring does not document the 3-fire requirement"
        )

    def test_docstring_mentions_pattern_and_rule_thresholds(self) -> None:
        doc = graduate.__doc__
        assert doc is not None
        assert "PATTERN" in doc
        assert "RULE" in doc


class TestConfidenceJumpWarning:
    """Safety assertion logs warning on excessive single-session confidence jump."""

    def test_large_jump_logs_warning(self, caplog) -> None:
        """Confidence jump > PATTERN_THRESHOLD triggers warning log."""
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.80,
            fire_count=MIN_APPLICATIONS_FOR_PATTERN,
        )
        lesson._pre_session_confidence = 0.10  # type: ignore[attr-defined]
        # jump = 0.80 - 0.10 = 0.70 > PATTERN_THRESHOLD (0.60)
        with caplog.at_level(logging.WARNING, logger="gradata.enhancements.self_improvement"):
            graduate([lesson])
        assert any("Safety assertion" in r.message for r in caplog.records), (
            "Expected warning about confidence jump"
        )

    def test_small_jump_no_warning(self, caplog) -> None:  # type: ignore[override]
        """Small confidence jump does not trigger warning."""
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.65,
            fire_count=MIN_APPLICATIONS_FOR_PATTERN,
        )
        lesson._pre_session_confidence = 0.55  # type: ignore[attr-defined]
        # jump = 0.65 - 0.55 = 0.10 < PATTERN_THRESHOLD (0.60)
        with caplog.at_level(logging.WARNING, logger="gradata.enhancements.self_improvement"):
            graduate([lesson])
        assert not any("Safety assertion" in r.message for r in caplog.records)
