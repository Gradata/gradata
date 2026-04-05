"""Tests for machine-mode FSRS recalibration."""

import copy

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import (
    MACHINE_CONTRADICTION_PENALTY,
    MACHINE_KILL_LIMITS,
    MACHINE_SEVERITY_WEIGHTS,
    _detect_machine_context,
    fsrs_bonus,
    fsrs_penalty,
    graduate,
    update_confidence,
)


def _make_lesson(
    desc: str = "test lesson",
    category: str = "CONTENT",
    state: LessonState = LessonState.INSTINCT,
    confidence: float = 0.40,
    fire_count: int = 0,
) -> Lesson:
    return Lesson(
        date="2026-04-03",
        description=desc,
        category=category,
        state=state,
        confidence=confidence,
        fire_count=fire_count,
    )


class TestDetectMachineContext:
    def test_explicit_true(self):
        assert _detect_machine_context([], explicit=True) is True

    def test_explicit_false_with_many_corrections(self):
        corrections = [{"category": "X"}] * 20
        assert _detect_machine_context(corrections, explicit=False) is False

    def test_auto_detect_above_threshold(self):
        corrections = [{"category": "X"}] * 26
        assert _detect_machine_context(corrections) is True

    def test_auto_detect_below_threshold(self):
        corrections = [{"category": "X"}] * 15
        assert _detect_machine_context(corrections) is False

    def test_auto_detect_at_threshold(self):
        corrections = [{"category": "X"}] * 25
        assert _detect_machine_context(corrections) is False  # > not >=

    def test_auto_detect_empty(self):
        assert _detect_machine_context([]) is False


class TestFSRSMachineMode:
    def test_bonus_machine_larger_at_high_confidence(self):
        """Machine mode flatter curve → bigger bonus at high confidence."""
        human_bonus = fsrs_bonus(0.90, machine=False)
        machine_bonus = fsrs_bonus(0.90, machine=True)
        assert machine_bonus > human_bonus

    def test_penalty_machine_smaller(self):
        """Machine mode halved base penalty."""
        human_penalty = fsrs_penalty(0.50, machine=False)
        machine_penalty = fsrs_penalty(0.50, machine=True)
        assert machine_penalty < human_penalty

    def test_bonus_machine_false_matches_default(self):
        assert fsrs_bonus(0.60, machine=False) == fsrs_bonus(0.60)

    def test_penalty_machine_false_matches_default(self):
        assert fsrs_penalty(0.60, machine=False) == fsrs_penalty(0.60)


class TestUpdateConfidenceMachineMode:
    def test_machine_mode_survives_20_contradictions(self):
        """In machine mode, 20 contradictions shouldn't collapse confidence to 0."""
        lesson = _make_lesson(confidence=0.40, fire_count=3)
        lessons = [lesson]

        # 20 contradicting corrections
        corrections = [{"category": "CONTENT", "description": "changed X to Y"}] * 20
        update_confidence(lessons, corrections, machine_mode=True)

        # Should still be positive (human mode would collapse to 0.0)
        assert lesson.confidence > 0.0

    def test_human_mode_explicit_matches_default(self):
        """machine_mode=False should produce identical results to default."""
        lesson_a = _make_lesson(confidence=0.50, fire_count=2)
        lesson_b = _make_lesson(confidence=0.50, fire_count=2)

        corrections = [{"category": "CONTENT"}] * 3

        update_confidence([lesson_a], corrections, machine_mode=False)
        update_confidence([lesson_b], corrections, machine_mode=None)  # auto-detect: 3 < 10

        assert lesson_a.confidence == lesson_b.confidence

    def test_auto_detect_triggers_machine_for_many_corrections(self):
        """>25 corrections auto-triggers machine mode."""
        lesson_human = _make_lesson(confidence=0.40)
        lesson_auto = _make_lesson(confidence=0.40)

        corrections_few = [{"category": "CONTENT"}] * 3
        corrections_many = [{"category": "CONTENT"}] * 30

        update_confidence([lesson_human], corrections_few)  # auto: human
        update_confidence([lesson_auto], corrections_many)  # auto: machine

        # Machine mode should lose less confidence
        assert lesson_auto.confidence >= lesson_human.confidence


class TestGraduateMachineMode:
    def test_machine_kill_limits_higher(self):
        """Machine mode uses higher kill limits."""
        # Lesson that would be killed in human mode (15 sessions) but not machine (30)
        lesson = _make_lesson(
            state=LessonState.INSTINCT,
            confidence=0.30,
            fire_count=0,
        )
        lesson.sessions_since_fire = 16  # > 15 (human INFANT kill) but < 30 (machine)

        lessons_human = [copy.deepcopy(lesson)]
        lessons_machine = [copy.deepcopy(lesson)]

        graduate(lessons_human, machine_mode=False)
        graduate(lessons_machine, machine_mode=True)

        # Human mode: should be UNTESTABLE
        assert lessons_human[0].state == LessonState.UNTESTABLE
        # Machine mode: should still be INSTINCT
        assert lessons_machine[0].state == LessonState.INSTINCT


class TestMachineConstants:
    def test_machine_penalty_softer_than_human(self):
        from gradata.enhancements.self_improvement import CONTRADICTION_PENALTY
        assert abs(MACHINE_CONTRADICTION_PENALTY) < abs(CONTRADICTION_PENALTY)

    def test_machine_kill_limits_are_doubled(self):
        assert MACHINE_KILL_LIMITS["INFANT"] >= 25

    def test_machine_severity_weights_are_softer(self):
        assert MACHINE_SEVERITY_WEIGHTS["moderate"] < 0.60
