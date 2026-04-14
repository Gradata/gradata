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
    MAX_PER_SESSION_DELTA,
    MAX_PER_STEP_PENALTY,
    MIN_APPLICATIONS_FOR_PATTERN,
    MIN_APPLICATIONS_FOR_RULE,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
    graduate,
    update_confidence,
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
        # Must mention the exact fire-count thresholds
        assert "fire_count >= 3" in doc or "MIN_APPLICATIONS_FOR_PATTERN" in doc, (
            "Docstring does not document the 3-fire requirement for PATTERN"
        )
        assert "fire_count >= 5" in doc or "MIN_APPLICATIONS_FOR_RULE" in doc, (
            "Docstring does not document the 5-fire requirement for RULE"
        )

    def test_docstring_mentions_pattern_and_rule_thresholds(self) -> None:
        doc = graduate.__doc__
        assert doc is not None
        # Must mention the specific transitions
        assert "INSTINCT -> PATTERN" in doc or "INSTINCT → PATTERN" in doc, (
            "Docstring must document INSTINCT -> PATTERN transition"
        )
        assert "PATTERN -> RULE" in doc or "PATTERN → RULE" in doc, (
            "Docstring must document PATTERN -> RULE transition"
        )


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


class TestSurvivalBonusRequiresInjectionEvidence:
    """Fix for gap-analysis/01-internal-audit.md #1.10.

    Survival path must not bypass the no-promotion-from-silence invariant
    by auto-incrementing fire_count for lessons that were never injected.
    """

    def test_silent_survival_does_not_increment_fire_count(self) -> None:
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.30,
            fire_count=0,
            category="DRAFTING",
        )
        update_confidence([lesson], [{"category": "ACCURACY"}])
        assert lesson.fire_count == 0, (
            "Survival without injection evidence must NOT increment fire_count"
        )
        # Confidence bonus is still applied (legacy behaviour preserved)
        assert lesson.confidence > 0.30

    def test_injected_flag_allows_fire_count_increment(self) -> None:
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.30,
            fire_count=0,
            category="DRAFTING",
        )
        lesson._was_injected_this_session = True  # type: ignore[attr-defined]
        update_confidence([lesson], [{"category": "ACCURACY"}])
        assert lesson.fire_count == 1

    def test_injected_keys_set_allows_fire_count_increment(self) -> None:
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.30,
            fire_count=0,
            category="DRAFTING",
            description="keep prose tight",
        )
        key = f"DRAFTING:{'keep prose tight'[:60]}"
        update_confidence(
            [lesson],
            [{"category": "ACCURACY"}],
            injected_lesson_keys={key},
        )
        assert lesson.fire_count == 1

    def test_silent_survival_cannot_graduate_from_zero(self) -> None:
        """Sybil scenario: 3 silent survivals must not promote INSTINCT->PATTERN."""
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.55,
            fire_count=0,  # never actually injected
            category="DRAFTING",
        )
        for _ in range(5):
            update_confidence([lesson], [{"category": "ACCURACY"}])
        # Without injection evidence, fire_count gate must still block promotion
        assert lesson.fire_count == 0
        assert lesson.state == LessonState.INSTINCT


class TestPenaltyCap:
    """Fix for gap-analysis/01-internal-audit.md #1.3.

    Compound FSRS penalty must not exceed MAX_PER_STEP_PENALTY in one tick,
    even when ACCELERATION * streak_mult * severity_boost * rule_override
    combine with a rewrite severity weight.
    """

    def test_rewrite_contradiction_capped_on_rule(self) -> None:
        """Full-stacked penalty on a RULE must not exceed the cap."""
        lesson = _make_lesson(
            state=LessonState.RULE,
            confidence=0.90,
            fire_count=8,
            category="DRAFTING",
            description="tighten prose",
        )
        pre = lesson.confidence
        update_confidence(
            [lesson],
            [
                {
                    "category": "DRAFTING",
                    "description": "loosen prose more",
                    "direction": "CONTRADICTING",
                    "severity_label": "rewrite",
                }
            ],
            severity_data={"DRAFTING": "rewrite"},
        )
        drop = pre - lesson.confidence
        assert drop > 0, "Penalty must still apply"
        assert drop <= MAX_PER_STEP_PENALTY + 1e-9, (
            f"Penalty {drop} exceeded cap {MAX_PER_STEP_PENALTY}"
        )

    def test_sybil_burst_cannot_chain_tier_transitions(self) -> None:
        """10 same-session reinforcements must not push INSTINCT through RULE.

        gap-analysis/01-internal-audit.md Gap 4: without a per-session cap,
        a fresh lesson can be pushed 0 -> PATTERN -> RULE in one call by
        stacking +0.12/rewrite reinforcements. The cap allows at most ONE
        tier transition (INSTINCT->PATTERN OR PATTERN->RULE) per session.
        """
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.50,
            fire_count=10,  # satisfy fire_count gate
            category="DRAFTING",
            description="tighten prose",
        )
        lesson._was_injected_this_session = True  # type: ignore[attr-defined]
        update_confidence(
            [lesson],
            [
                {
                    "category": "DRAFTING",
                    "direction": "REINFORCING",
                    "severity_label": "rewrite",
                }
            ] * 10,
            severity_data={"DRAFTING": "rewrite"},
        )
        # Cannot chain INSTINCT -> PATTERN -> RULE in a single tick
        assert lesson.state != LessonState.RULE, (
            f"Sybil burst promoted past ONE tier: {lesson.state} at {lesson.confidence}"
        )
        # Net confidence delta bounded by MAX_PER_SESSION_DELTA
        drop = abs(lesson.confidence - 0.50)
        assert drop <= MAX_PER_SESSION_DELTA + 1e-9, (
            f"Per-session delta {drop} exceeded cap {MAX_PER_SESSION_DELTA}"
        )

    def test_monotone_under_alternating_corrections(self) -> None:
        """Alternating contradict/reinforce must not oscillate wildly.

        Each contradict tick must decrease confidence; each reinforce tick
        must not decrease it. The Bayesian blend cannot pull the update in
        the opposite direction of the current event.
        """
        lesson = _make_lesson(
            state=LessonState.PATTERN,
            confidence=0.70,
            fire_count=5,
            category="DRAFTING",
            description="tighten prose",
        )
        # 5 contradict events then 5 reinforce events
        prev = lesson.confidence
        for _ in range(5):
            update_confidence(
                [lesson],
                [{"category": "DRAFTING", "direction": "CONTRADICTING"}],
            )
            assert lesson.confidence <= prev + 1e-9, (
                "Contradict event must not increase confidence"
            )
            prev = lesson.confidence
        for _ in range(5):
            update_confidence(
                [lesson],
                [{"category": "DRAFTING", "direction": "REINFORCING"}],
            )
            assert lesson.confidence >= prev - 1e-9, (
                "Reinforce event must not decrease confidence"
            )
            prev = lesson.confidence
