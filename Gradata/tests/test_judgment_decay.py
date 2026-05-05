"""Tests for judgment_decay.py — confidence decay algorithm for brain lessons.

These tests cover:
- Documented decay rate (-0.02/idle session)
- Reinforcement when applied this session (+0.05)
- RULE tier immunity
- UNTESTABLE archival after 20+ idle sessions
- Confidence floor (0.10)
- INSTINCT/PATTERN tier ceiling clamping
- Session-type-aware filtering
- Batch decay aggregation
"""

import pytest

from gradata.enhancements.graduation.judgment_decay import (
    CONFIDENCE_FLOOR,
    DECAY_PER_IDLE_SESSION,
    INSTINCT_CEILING,
    PATTERN_CEILING,
    REINFORCEMENT_BONUS,
    UNTESTABLE_THRESHOLD,
    compute_batch_decay,
    compute_decay,
    is_category_testable,
)
from gradata.enhancements.self_improvement import Lesson, LessonState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_lesson(
    state: LessonState = LessonState.INSTINCT,
    confidence: float = 0.45,
    category: str = "ACCURACY",
) -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description="test lesson",
    )


# ---------------------------------------------------------------------------
# compute_decay — happy paths
# ---------------------------------------------------------------------------


class TestComputeDecayBasic:
    def test_one_idle_session_decays_by_documented_rate(self):
        lesson = make_lesson(confidence=0.45)
        result = compute_decay(
            lesson, sessions_since_applied=1, was_applied_this_session=False, total_idle_sessions=0
        )
        assert result.action == "decayed"
        assert result.new_confidence == pytest.approx(0.45 - DECAY_PER_IDLE_SESSION, abs=1e-9)

    def test_three_idle_sessions_decays_by_accumulated_rate(self):
        lesson = make_lesson(confidence=0.50)
        result = compute_decay(
            lesson, sessions_since_applied=3, was_applied_this_session=False, total_idle_sessions=0
        )
        expected = round(0.50 - 3 * DECAY_PER_IDLE_SESSION, 2)
        assert result.new_confidence == expected
        assert result.action == "decayed"

    def test_no_idle_sessions_skips_decay(self):
        lesson = make_lesson(confidence=0.45)
        result = compute_decay(
            lesson, sessions_since_applied=0, was_applied_this_session=False, total_idle_sessions=0
        )
        assert result.action == "skipped"
        assert result.new_confidence == 0.45

    def test_applied_this_session_reinforces(self):
        lesson = make_lesson(state=LessonState.INSTINCT, confidence=0.40)
        result = compute_decay(
            lesson, sessions_since_applied=0, was_applied_this_session=True, total_idle_sessions=0
        )
        assert result.action == "reinforced"
        assert result.new_confidence == pytest.approx(0.40 + REINFORCEMENT_BONUS, abs=1e-9)

    def test_reinforcement_capped_at_instinct_ceiling(self):
        lesson = make_lesson(state=LessonState.INSTINCT, confidence=INSTINCT_CEILING - 0.01)
        result = compute_decay(
            lesson, sessions_since_applied=0, was_applied_this_session=True, total_idle_sessions=0
        )
        assert result.new_confidence <= INSTINCT_CEILING

    def test_reinforcement_capped_at_pattern_ceiling(self):
        lesson = make_lesson(state=LessonState.PATTERN, confidence=PATTERN_CEILING - 0.01)
        result = compute_decay(
            lesson, sessions_since_applied=0, was_applied_this_session=True, total_idle_sessions=0
        )
        assert result.new_confidence <= PATTERN_CEILING


# ---------------------------------------------------------------------------
# RULE tier immunity
# ---------------------------------------------------------------------------


class TestRuleTierImmunity:
    def test_rule_tier_is_immune_to_decay(self):
        lesson = make_lesson(state=LessonState.RULE, confidence=0.95)
        result = compute_decay(
            lesson,
            sessions_since_applied=50,
            was_applied_this_session=False,
            total_idle_sessions=50,
        )
        assert result.action == "skipped"
        assert result.new_confidence == 0.95
        assert "immune" in result.reason

    def test_rule_tier_is_immune_even_at_untestable_threshold(self):
        lesson = make_lesson(state=LessonState.RULE, confidence=0.92)
        result = compute_decay(
            lesson,
            sessions_since_applied=UNTESTABLE_THRESHOLD + 5,
            was_applied_this_session=False,
            total_idle_sessions=UNTESTABLE_THRESHOLD + 5,
        )
        assert result.action == "skipped"
        assert result.new_confidence == 0.92


# ---------------------------------------------------------------------------
# Confidence floor
# ---------------------------------------------------------------------------


class TestConfidenceFloor:
    def test_decay_never_goes_below_floor(self):
        lesson = make_lesson(confidence=CONFIDENCE_FLOOR + 0.01)
        result = compute_decay(
            lesson, sessions_since_applied=10, was_applied_this_session=False, total_idle_sessions=0
        )
        assert result.new_confidence >= CONFIDENCE_FLOOR

    def test_decay_at_exact_floor_does_not_go_negative(self):
        lesson = make_lesson(confidence=CONFIDENCE_FLOOR)
        result = compute_decay(
            lesson, sessions_since_applied=5, was_applied_this_session=False, total_idle_sessions=0
        )
        assert result.new_confidence == CONFIDENCE_FLOOR


# ---------------------------------------------------------------------------
# UNTESTABLE archival
# ---------------------------------------------------------------------------


class TestUntestableArchival:
    def test_exactly_at_threshold_archives(self):
        lesson = make_lesson(confidence=0.45)
        result = compute_decay(
            lesson,
            sessions_since_applied=5,
            was_applied_this_session=False,
            total_idle_sessions=UNTESTABLE_THRESHOLD,
        )
        assert result.action == "archived"
        assert result.new_confidence == 0.0

    def test_one_below_threshold_does_not_archive(self):
        lesson = make_lesson(confidence=0.45)
        result = compute_decay(
            lesson,
            sessions_since_applied=5,
            was_applied_this_session=False,
            total_idle_sessions=UNTESTABLE_THRESHOLD - 1,
        )
        assert result.action != "archived"

    def test_far_above_threshold_archives(self):
        lesson = make_lesson(confidence=0.55)
        result = compute_decay(
            lesson,
            sessions_since_applied=5,
            was_applied_this_session=False,
            total_idle_sessions=UNTESTABLE_THRESHOLD + 100,
        )
        assert result.action == "archived"


# ---------------------------------------------------------------------------
# Session-type-aware filtering
# ---------------------------------------------------------------------------


class TestSessionTypeFiltering:
    def test_sales_lesson_skipped_in_system_session(self):
        lesson = make_lesson(category="DRAFTING")
        result = compute_decay(
            lesson,
            sessions_since_applied=5,
            was_applied_this_session=False,
            total_idle_sessions=0,
            session_type="system",
        )
        assert result.action == "skipped"
        assert "not testable" in result.reason

    def test_sales_lesson_decays_in_sales_session(self):
        lesson = make_lesson(category="DRAFTING", confidence=0.45)
        result = compute_decay(
            lesson,
            sessions_since_applied=1,
            was_applied_this_session=False,
            total_idle_sessions=0,
            session_type="sales",
        )
        assert result.action == "decayed"

    def test_universal_lesson_decays_in_any_session(self):
        for session_type in ("sales", "system", "pipeline", "mixed"):
            lesson = make_lesson(category="ACCURACY", confidence=0.45)
            result = compute_decay(
                lesson,
                sessions_since_applied=1,
                was_applied_this_session=False,
                total_idle_sessions=0,
                session_type=session_type,
            )
            assert result.action == "decayed", f"Expected decay in {session_type} session"

    def test_none_session_type_applies_decay_to_all(self):
        lesson = make_lesson(category="DRAFTING", confidence=0.45)
        result = compute_decay(
            lesson,
            sessions_since_applied=1,
            was_applied_this_session=False,
            total_idle_sessions=0,
            session_type=None,
        )
        # Backward compat: no session_type = always testable
        assert result.action == "decayed"


class TestIsCategoryTestable:
    def test_known_sales_category_in_sales_session(self):
        assert is_category_testable("DRAFTING", "sales") is True

    def test_known_sales_category_in_system_session(self):
        assert is_category_testable("DRAFTING", "system") is False

    def test_universal_category_is_always_testable(self):
        for st in ("sales", "system", "pipeline", "mixed"):
            assert is_category_testable("ACCURACY", st) is True

    def test_unknown_category_defaults_to_testable(self):
        # Unknown categories fall back to ALL_SESSION_TYPES (safe fallback)
        assert is_category_testable("SOME_UNKNOWN_CATEGORY", "sales") is True

    def test_none_session_type_is_always_testable(self):
        assert is_category_testable("DRAFTING", None) is True


# ---------------------------------------------------------------------------
# DecayResult fields
# ---------------------------------------------------------------------------


class TestDecayResultFields:
    def test_decay_result_preserves_category_and_tier(self):
        lesson = make_lesson(state=LessonState.PATTERN, confidence=0.70, category="CONTEXT")
        result = compute_decay(
            lesson, sessions_since_applied=2, was_applied_this_session=False, total_idle_sessions=0
        )
        assert result.category == "CONTEXT"
        assert result.tier == "PATTERN"
        assert result.old_confidence == 0.70

    def test_decay_result_reason_mentions_idle_sessions(self):
        lesson = make_lesson(confidence=0.50)
        result = compute_decay(
            lesson, sessions_since_applied=3, was_applied_this_session=False, total_idle_sessions=0
        )
        assert "idle sessions" in result.reason
        assert "3" in result.reason


# ---------------------------------------------------------------------------
# compute_batch_decay
# ---------------------------------------------------------------------------


class TestComputeBatchDecay:
    def test_batch_returns_one_result_per_lesson(self):
        lessons = [
            make_lesson(category="ACCURACY", confidence=0.45),
            make_lesson(category="DRAFTING", confidence=0.50),
        ]
        app_data = {
            "ACCURACY": {
                "last_applied_session": 5,
                "applied_this_session": False,
                "total_idle_sessions": 0,
            },
            "DRAFTING": {
                "last_applied_session": 3,
                "applied_this_session": False,
                "total_idle_sessions": 0,
            },
        }
        results = compute_batch_decay(lessons, app_data, current_session=10)
        assert len(results) == 2

    def test_batch_applied_lesson_is_reinforced(self):
        lesson = make_lesson(category="ACCURACY", confidence=0.40)
        app_data = {
            "ACCURACY": {
                "last_applied_session": 10,
                "applied_this_session": True,
                "total_idle_sessions": 0,
            },
        }
        results = compute_batch_decay([lesson], app_data, current_session=10)
        assert results[0].action == "reinforced"

    def test_batch_missing_app_data_skips_lesson(self):
        lesson = make_lesson(category="ACCURACY", confidence=0.45)
        results = compute_batch_decay([lesson], application_data={}, current_session=10)
        # No last_applied_session => sessions_since = 0 => no change
        assert results[0].action == "skipped"

    def test_batch_session_type_propagates(self):
        """DRAFTING lessons should be skipped in a system session."""
        lesson = make_lesson(category="DRAFTING", confidence=0.45)
        app_data = {
            "DRAFTING": {
                "last_applied_session": 5,
                "applied_this_session": False,
                "total_idle_sessions": 0,
            },
        }
        results = compute_batch_decay([lesson], app_data, current_session=10, session_type="system")
        assert results[0].action == "skipped"
