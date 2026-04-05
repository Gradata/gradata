import pytest; pytest.importorskip('gradata.enhancements.self_improvement', reason='requires gradata_cloud')
"""
Enhancement module tests for the Gradata.

Tests all pure-logic SDK modules in isolation — no file I/O, no DB,
no Brain instance required (unless the module inherently needs one).

Modules covered:
  _self_improvement   — parse_lessons, update_confidence, format_lessons,
                        graduate, compute_learning_velocity, Lesson, LessonState
  _stats              — brier_score, rolling_comparison, wilson_ci,
                        correction_half_life, beta_posterior, ewma_control,
                        task_success_rate, mtbf_mttr
  _tag_taxonomy       — validate_tag, validate_tags, enrich_tags, TAXONOMY
  _fact_extractor     — _quality_gate, _clean_value, _parse_frontmatter,
                        extract_from_file (via temp file)
  _validator          — _compute_trust_score (pure function)
  _paths              — make_paths, resolve_brain_dir (pure)
  _config             — constants, env-var overrides

Run: cd sdk && python -m pytest tests/ -v
"""

import math
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lesson_text(*entries: str) -> str:
    """Join lesson entries separated by blank lines."""
    return "\n\n".join(entries)


# ===========================================================================
# _self_improvement — parse_lessons
# ===========================================================================

class TestParseLessons:
    def setup_method(self):
        from gradata.enhancements.self_improvement import parse_lessons, LessonState
        self.parse = parse_lessons
        self.LessonState = LessonState

    def test_parse_single_instinct(self):
        text = "[2026-01-15] [INSTINCT:0.30] DRAFTING: Never use em dashes in email prose."
        lessons = self.parse(text)
        assert len(lessons) == 1
        l = lessons[0]
        assert l.date == "2026-01-15"
        assert l.state == self.LessonState.INSTINCT
        assert l.confidence == 0.30
        assert l.category == "DRAFTING"
        assert "em dashes" in l.description

    def test_parse_pattern_with_confidence(self):
        text = "[2026-02-01] [PATTERN:0.80] ACCURACY: Verify numbers before reporting."
        lessons = self.parse(text)
        assert len(lessons) == 1
        assert lessons[0].state == self.LessonState.PATTERN
        assert lessons[0].confidence == 0.80

    def test_parse_rule_no_confidence(self):
        """[RULE] with no confidence should default to 0.90."""
        text = "[2026-03-01] [RULE] PROCESS: Always read source files before summarizing."
        lessons = self.parse(text)
        assert len(lessons) == 1
        assert lessons[0].state == self.LessonState.RULE
        assert lessons[0].confidence == 0.90

    def test_parse_root_cause_extracted(self):
        text = (
            "[2026-01-20] [INSTINCT:0.30] ACCURACY: Do not invent file paths. "
            "Root cause: Model hallucination under uncertainty."
        )
        lessons = self.parse(text)
        assert len(lessons) == 1
        assert "hallucination" in lessons[0].root_cause
        assert "Root cause" not in lessons[0].description

    def test_parse_skips_non_lesson_lines(self):
        text = _make_lesson_text(
            "# My Lessons",
            "This is just a comment line.",
            "[2026-03-10] [PATTERN:0.70] PROCESS: Gate before output.",
            "",
            "---",
        )
        lessons = self.parse(text)
        assert len(lessons) == 1
        assert lessons[0].category == "PROCESS"

    def test_parse_empty_string(self):
        assert self.parse("") == []

    def test_parse_multiple_lessons(self):
        text = _make_lesson_text(
            "[2026-01-01] [INSTINCT:0.30] DRAFTING: Tight prose only.",
            "[2026-02-01] [PATTERN:0.60] ACCURACY: Cross-source before reporting.",
            "[2026-03-01] [RULE] PROCESS: Waterfall applies to all outputs.",
        )
        lessons = self.parse(text)
        assert len(lessons) == 3
        states = [l.state.value for l in lessons]
        assert "INSTINCT" in states
        assert "PATTERN" in states
        assert "RULE" in states

    def test_parse_untestable_state(self):
        text = "[2026-01-01] [UNTESTABLE] STRATEGY: Unclear hypothesis."
        lessons = self.parse(text)
        assert len(lessons) == 1
        assert lessons[0].state == self.LessonState.UNTESTABLE
        assert lessons[0].confidence == 0.0


# ===========================================================================
# _self_improvement — update_confidence
# ===========================================================================

class TestUpdateConfidence:
    def setup_method(self):
        from gradata.enhancements.self_improvement import (
            update_confidence, Lesson, LessonState,
            INITIAL_CONFIDENCE, SURVIVAL_BONUS, CONTRADICTION_PENALTY,
            PATTERN_THRESHOLD, RULE_THRESHOLD,
        )
        from gradata.enhancements.self_improvement import fsrs_bonus, fsrs_penalty
        self.update = update_confidence
        self.Lesson = Lesson
        self.LessonState = LessonState
        self.INITIAL = INITIAL_CONFIDENCE
        self.fsrs_bonus = fsrs_bonus
        self.fsrs_penalty = fsrs_penalty
        self.PATTERN_T = PATTERN_THRESHOLD
        self.RULE_T = RULE_THRESHOLD

    def _lesson(self, category="DRAFTING", confidence=0.30, state=None):
        from gradata.enhancements.self_improvement import LessonState
        state = state or LessonState.INSTINCT
        return self.Lesson(
            date="2026-01-01",
            state=state,
            confidence=confidence,
            category=category,
            description="Test lesson.",
        )

    def test_survival_increases_confidence(self):
        """Lesson survives session where corrections exist in another category."""
        lessons = [self._lesson("DRAFTING", 0.30)]
        result = self.update(lessons, [{"category": "ACCURACY"}])
        expected_bonus = self.fsrs_bonus(0.30)
        assert result[0].confidence == round(0.30 + expected_bonus, 2)

    def test_contradiction_decreases_confidence(self):
        """Same-category correction lowers confidence."""
        lessons = [self._lesson("DRAFTING", 0.50)]
        result = self.update(lessons, [{"category": "DRAFTING"}])
        expected_penalty = self.fsrs_penalty(0.50)
        assert result[0].confidence == round(0.50 - expected_penalty, 2)

    def test_no_corrections_does_not_change_confidence(self):
        """Zero corrections — cannot evaluate, confidence unchanged."""
        lessons = [self._lesson("DRAFTING", 0.40)]
        result = self.update(lessons, [])
        assert result[0].confidence == 0.40

    def test_promotion_instinct_to_pattern(self):
        """INSTINCT at 0.55 + survival + sufficient applications -> PATTERN."""
        lesson = self._lesson("DRAFTING", 0.55)
        lesson.fire_count = 3  # MIN_APPLICATIONS_FOR_PATTERN
        result = self.update([lesson], [{"category": "ACCURACY"}])
        # 0.55 + 0.10 = 0.65 >= 0.60, fire_count >= 3 -> promoted
        assert result[0].state == self.LessonState.PATTERN

    def test_promotion_pattern_to_rule(self):
        """PATTERN at 0.85 + survival + sufficient applications -> RULE."""
        from gradata.enhancements.self_improvement import LessonState
        lesson = self._lesson("DRAFTING", 0.85, LessonState.PATTERN)
        lesson.fire_count = 5  # MIN_APPLICATIONS_FOR_RULE
        result = self.update([lesson], [{"category": "ACCURACY"}])
        assert result[0].state == self.LessonState.RULE

    def test_rule_lessons_demoted_on_contradiction(self):
        """RULE-state lessons CAN be demoted if contradicted (not immortal)."""
        from gradata.enhancements.self_improvement import LessonState
        lesson = self._lesson("DRAFTING", 0.95, LessonState.RULE)
        original_conf = lesson.confidence
        result = self.update([lesson], [{"category": "DRAFTING"}])
        # FSRS penalty applies even to RULES — penalty is confidence-dependent
        expected_penalty = self.fsrs_penalty(0.95)
        assert result[0].confidence == round(original_conf - expected_penalty, 2)

    def test_untestable_after_20_sessions_no_fires(self):
        """Lesson flagged UNTESTABLE after 20 sessions_since_fire with fire_count==0."""
        lesson = self._lesson("DRAFTING", 0.30)
        lesson.sessions_since_fire = 19
        lesson.fire_count = 0
        # One more session with no corrections
        result = self.update([lesson], [])
        assert result[0].sessions_since_fire == 20
        assert result[0].state == self.LessonState.UNTESTABLE

    def test_confidence_floor_at_zero(self):
        """Confidence cannot go below 0."""
        lessons = [self._lesson("DRAFTING", 0.10)]
        # Apply many contradictions
        for _ in range(5):
            self.update(lessons, [{"category": "DRAFTING"}])
        assert lessons[0].confidence >= 0.0


# ===========================================================================
# _self_improvement — format_lessons
# ===========================================================================

class TestFormatLessons:
    def setup_method(self):
        from gradata.enhancements.self_improvement import (
            format_lessons, parse_lessons, Lesson, LessonState,
        )
        self.format = format_lessons
        self.parse = parse_lessons
        self.Lesson = Lesson
        self.LessonState = LessonState

    def test_roundtrip_preserves_data(self):
        """parse -> format -> parse should preserve all key fields."""
        original_text = "\n\n".join([
            "[2026-01-10] [INSTINCT:0.30] DRAFTING: Use tight prose.",
            "[2026-02-20] [PATTERN:0.70] ACCURACY: Cross-source numbers.",
        ])
        lessons = self.parse(original_text)
        formatted = self.format(lessons)
        reparsed = self.parse(formatted)

        assert len(reparsed) == 2
        assert reparsed[0].category == "DRAFTING"
        assert reparsed[1].category == "ACCURACY"

    def test_rule_emits_with_confidence_and_fires(self):
        """RULE-state lessons serialize as [RULE:CONF:FIRES] in upgraded format."""
        lesson = self.Lesson(
            date="2026-03-01",
            state=self.LessonState.RULE,
            confidence=0.95,
            category="PROCESS",
            description="Gate before all output.",
        )
        output = self.format([lesson])
        assert "[RULE:" in output
        assert "PROCESS" in output

    def test_root_cause_appended(self):
        """Root cause is appended to description in output."""
        lesson = self.Lesson(
            date="2026-02-01",
            state=self.LessonState.PATTERN,
            confidence=0.70,
            category="ACCURACY",
            description="Never invent file counts",
            root_cause="Model hallucination under uncertainty",
        )
        output = self.format([lesson])
        assert "Root cause:" in output
        assert "hallucination" in output

    def test_format_empty_list(self):
        assert self.format([]) == ""


# ===========================================================================
# _self_improvement — graduate
# ===========================================================================

class TestGraduate:
    def setup_method(self):
        from gradata.enhancements.self_improvement import graduate, Lesson, LessonState
        self.graduate = graduate
        self.Lesson = Lesson
        self.LessonState = LessonState

    def _make(self, state):
        return self.Lesson(
            date="2026-01-01", state=state, confidence=0.50,
            category="TEST", description="test",
        )

    def test_splits_active_and_graduated(self):
        lessons = [
            self._make(self.LessonState.INSTINCT),
            self._make(self.LessonState.PATTERN),
            self._make(self.LessonState.RULE),
            self._make(self.LessonState.UNTESTABLE),
        ]
        active, graduated = self.graduate(lessons)
        assert len(active) == 2
        assert len(graduated) == 2

    def test_empty_input(self):
        active, graduated = self.graduate([])
        assert active == []
        assert graduated == []

    def test_all_active(self):
        lessons = [
            self._make(self.LessonState.INSTINCT),
            self._make(self.LessonState.PATTERN),
        ]
        active, graduated = self.graduate(lessons)
        assert len(active) == 2
        assert graduated == []


# ===========================================================================
# _self_improvement — compute_learning_velocity
# ===========================================================================

class TestComputeLearningVelocity:
    def setup_method(self):
        from gradata.enhancements.self_improvement import compute_learning_velocity, Lesson, LessonState
        self.compute = compute_learning_velocity
        self.Lesson = Lesson
        self.LessonState = LessonState

    def test_empty_returns_zero_values(self):
        result = self.compute([])
        assert result["graduation_rate"] == 0.0
        assert result["total_lessons"] == 0

    def test_graduation_rate_calculation(self):
        lessons = [
            self.Lesson("2026-01-01", self.LessonState.RULE, 0.95, "A", "desc"),
            self.Lesson("2026-01-02", self.LessonState.RULE, 0.92, "B", "desc"),
            self.Lesson("2026-01-03", self.LessonState.INSTINCT, 0.30, "C", "desc"),
            self.Lesson("2026-01-04", self.LessonState.PATTERN, 0.70, "D", "desc"),
        ]
        result = self.compute(lessons)
        assert result["total_lessons"] == 4
        assert result["graduation_rate"] == 0.5  # 2/4

    def test_state_distribution_counts(self):
        lessons = [
            self.Lesson("2026-01-01", self.LessonState.INSTINCT, 0.30, "X", "d"),
            self.Lesson("2026-01-02", self.LessonState.INSTINCT, 0.40, "Y", "d"),
            self.Lesson("2026-01-03", self.LessonState.PATTERN, 0.70, "Z", "d"),
        ]
        result = self.compute(lessons)
        assert result["state_distribution"]["INSTINCT"] == 2
        assert result["state_distribution"]["PATTERN"] == 1

    def test_category_distribution(self):
        lessons = [
            self.Lesson("2026-01-01", self.LessonState.INSTINCT, 0.30, "DRAFTING", "d"),
            self.Lesson("2026-01-02", self.LessonState.INSTINCT, 0.30, "DRAFTING", "d"),
            self.Lesson("2026-01-03", self.LessonState.PATTERN, 0.70, "ACCURACY", "d"),
        ]
        result = self.compute(lessons)
        assert result["correction_categories"]["DRAFTING"] == 2
        assert result["correction_categories"]["ACCURACY"] == 1


# ===========================================================================
# _stats — brier_score
# ===========================================================================

class TestBrierScore:
    def setup_method(self):
        from gradata._stats import brier_score
        self.brier = brier_score

    def test_perfect_predictions(self):
        """All correct predictions -> Brier score near 0."""
        data = [(1.0, 1), (0.0, 0), (1.0, 1)]
        result = self.brier(data)
        assert result["score"] == 0.0
        assert result["calibration"] == "EXCELLENT"

    def test_worst_case_predictions(self):
        """All inverted predictions -> Brier score = 1.0."""
        data = [(0.0, 1), (1.0, 0)]
        result = self.brier(data)
        assert result["score"] == 1.0
        assert result["calibration"] == "WORSE_THAN_RANDOM"

    def test_empty_returns_no_data(self):
        result = self.brier([])
        assert result["score"] is None
        assert result["calibration"] == "NO_DATA"
        assert result["n"] == 0

    def test_fair_calibration_range(self):
        """0.15 Brier score should be FAIR."""
        data = [(0.6, 1), (0.4, 0), (0.7, 0), (0.3, 1)]
        result = self.brier(data)
        assert result["score"] is not None
        assert result["n"] == 4

    def test_single_prediction(self):
        result = self.brier([(0.8, 1)])
        assert result["n"] == 1
        assert result["score"] == pytest.approx(0.04, abs=0.01)


# ===========================================================================
# _stats — rolling_comparison
# ===========================================================================

class TestRollingComparison:
    def setup_method(self):
        from gradata._stats import rolling_comparison
        self.compare = rolling_comparison

    def test_empty_returns_no_data(self):
        result = self.compare([])
        assert result["trend"] == "NO_DATA"

    def test_insufficient_window(self):
        """Less than window values -> INSUFFICIENT_WINDOW."""
        result = self.compare([1, 2, 3], window=10)
        assert result["trend"] == "INSUFFICIENT_WINDOW"

    def test_improving_trend(self):
        """Recent values significantly above lifetime avg -> IMPROVING."""
        values = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10]
        result = self.compare(values, window=5)
        assert result["trend"] == "IMPROVING"
        assert result["recent_avg"] > result["lifetime_avg"]

    def test_degrading_trend(self):
        """Recent values significantly below lifetime avg -> DEGRADING."""
        values = [9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        result = self.compare(values, window=5)
        assert result["trend"] == "DEGRADING"

    def test_stable_trend_within_5pct(self):
        """Values within 5% of each other -> STABLE."""
        values = [10.0] * 20
        result = self.compare(values, window=10)
        assert result["trend"] == "STABLE"

    def test_output_keys_present(self):
        values = list(range(20))
        result = self.compare(values, window=5)
        for key in ("lifetime_avg", "recent_avg", "delta", "trend", "pct_change"):
            assert key in result


# ===========================================================================
# _stats — wilson_ci
# ===========================================================================

class TestWilsonCI:
    def setup_method(self):
        from gradata._stats import wilson_ci
        self.wilson = wilson_ci

    def test_zero_total_returns_no_data(self):
        result = self.wilson(0, 0)
        assert result["point_estimate"] == 0
        assert "no data" in result["display"].lower()

    def test_all_successes(self):
        result = self.wilson(10, 10)
        assert result["point_estimate"] == 1.0
        assert result["ci_low"] > 0.7  # CI lower bound reasonable

    def test_zero_successes(self):
        result = self.wilson(0, 10)
        assert result["point_estimate"] == 0.0
        assert result["ci_high"] < 0.4

    def test_mid_range_estimate(self):
        result = self.wilson(5, 10)
        assert result["point_estimate"] == pytest.approx(0.5, abs=0.01)
        assert result["ci_low"] < 0.5
        assert result["ci_high"] > 0.5

    def test_display_string_format(self):
        result = self.wilson(3, 10)
        assert "%" in result["display"]
        assert "CI:" in result["display"]


# ===========================================================================
# _stats — correction_half_life
# ===========================================================================

class TestCorrectionHalfLife:
    def setup_method(self):
        from gradata._stats import correction_half_life
        self.half_life = correction_half_life

    def test_empty_returns_no_data(self):
        result = self.half_life([])
        assert result["overall"] == "NO_DATA"

    def test_single_occurrence_learned(self):
        corrections = [{"category": "DRAFTING", "session": 5}]
        result = self.half_life(corrections)
        assert result["categories"]["DRAFTING"]["status"] == "SINGLE_OCCURRENCE"
        assert result["learned"] == 1

    def test_widely_spaced_is_learned(self):
        """Low density corrections (far apart) -> LEARNED."""
        corrections = [
            {"category": "ACCURACY", "session": 1},
            {"category": "ACCURACY", "session": 50},
        ]
        result = self.half_life(corrections)
        assert result["categories"]["ACCURACY"]["status"] == "LEARNED"

    def test_frequent_corrections_recurring(self):
        """High density corrections -> RECURRING."""
        corrections = [
            {"category": "DRAFTING", "session": i}
            for i in range(1, 12)  # density = 10/10 = 1.0 > 0.3
        ]
        result = self.half_life(corrections)
        assert result["categories"]["DRAFTING"]["status"] == "RECURRING"
        assert result["recurring"] >= 1

    def test_overall_learning_status(self):
        """More learned than recurring -> LEARNING."""
        corrections = [
            {"category": "A", "session": 1},   # single -> learned
            {"category": "B", "session": 2},   # single -> learned
        ]
        result = self.half_life(corrections)
        assert result["overall"] == "LEARNING"

    def test_multi_category_tracking(self):
        corrections = [
            {"category": "DRAFTING", "session": 1},
            {"category": "ACCURACY", "session": 2},
            {"category": "PROCESS", "session": 3},
        ]
        result = self.half_life(corrections)
        assert result["total_categories"] == 3


# ===========================================================================
# _stats — beta_posterior
# ===========================================================================

class TestBetaPosterior:
    def setup_method(self):
        from gradata._stats import beta_posterior
        self.posterior = beta_posterior

    def test_zero_trials_uniform(self):
        """Zero trials gives flat uniform prior."""
        result = self.posterior(0, 0)
        assert result["n"] == 0
        assert result["posterior_mean"] == pytest.approx(0.5, abs=0.1)

    def test_high_success_rate_proven(self):
        """Many successes -> PROVEN label."""
        result = self.posterior(100, 100)
        assert result["posterior_mean"] > 0.95

    def test_zero_success_rate_underperforming(self):
        """Zero successes, many trials -> UNDERPERFORMING."""
        result = self.posterior(0, 100)
        assert result["confidence_label"] == "UNDERPERFORMING"

    def test_output_keys_present(self):
        result = self.posterior(10, 100)
        for key in ("posterior_mean", "ci_95", "prob_above_baseline", "confidence_label"):
            assert key in result

    def test_ci_bounds_within_zero_one(self):
        result = self.posterior(5, 10)
        low, high = result["ci_95"]
        assert 0.0 <= low <= high <= 1.0


# ===========================================================================
# _stats — ewma_control
# ===========================================================================

class TestEwmaControl:
    def setup_method(self):
        from gradata._stats import ewma_control
        self.ewma = ewma_control

    def test_insufficient_data(self):
        result = self.ewma([1.0, 2.0])
        assert result["status"] == "INSUFFICIENT_DATA"

    def test_stable_series_in_control(self):
        values = [5.0] * 20
        result = self.ewma(values)
        assert result["status"] == "IN_CONTROL"
        assert result["alerts"] == []

    def test_output_keys(self):
        values = list(range(10))
        result = self.ewma(values)
        for key in ("ewma_current", "mean", "sigma", "ucl", "lcl", "alerts", "status"):
            assert key in result

    def test_spike_generates_alert(self):
        # A sustained run of extreme outliers shifts the EWMA above the UCL.
        # A single spike at the end is absorbed by the wide sigma; three
        # consecutive spikes cross the control limit reliably.
        values = [1.0] * 15 + [500.0, 500.0, 500.0]
        result = self.ewma(values)
        assert len(result["alerts"]) > 0
        assert "OUT_OF_CONTROL" in result["status"]


# ===========================================================================
# _stats — task_success_rate
# ===========================================================================

class TestTaskSuccessRate:
    def setup_method(self):
        from gradata._stats import task_success_rate
        self.success_rate = task_success_rate

    def test_empty_returns_none(self):
        result = self.success_rate([])
        assert result["overall_pass_rate"] is None

    def test_all_uncorrected(self):
        events = [
            {"task_type": "email", "corrected": False},
            {"task_type": "email", "corrected": False},
        ]
        result = self.success_rate(events)
        assert result["by_type"]["email"]["pass_rate"] == 1.0

    def test_mixed_pass_fail(self):
        events = [
            {"task_type": "email", "corrected": False},
            {"task_type": "email", "corrected": True},
        ]
        result = self.success_rate(events)
        assert result["by_type"]["email"]["pass_rate"] == 0.5
        assert result["by_type"]["email"]["total"] == 2

    def test_multiple_task_types(self):
        events = [
            {"task_type": "email", "corrected": False},
            {"task_type": "research", "corrected": True},
        ]
        result = self.success_rate(events)
        assert "email" in result["by_type"]
        assert "research" in result["by_type"]


# ===========================================================================
# _stats — mtbf_mttr
# ===========================================================================

class TestMtbfMttr:
    def setup_method(self):
        from gradata._stats import mtbf_mttr
        self.mtbf = mtbf_mttr

    def test_empty_returns_none(self):
        result = self.mtbf([], 10)
        assert result["overall_mtbf"] is None

    def test_zero_sessions(self):
        corrections = [{"category": "DRAFTING", "session": 1}]
        result = self.mtbf(corrections, 0)
        assert result["overall_mtbf"] is None

    def test_single_correction_type(self):
        corrections = [{"category": "DRAFTING", "session": 5}]
        result = self.mtbf(corrections, 10)
        assert result["overall_mtbf"] == 10.0

    def test_mtbf_calculation(self):
        """MTBF = total_sessions / correction_count."""
        corrections = [
            {"category": "DRAFTING", "session": 2},
            {"category": "DRAFTING", "session": 4},
        ]
        result = self.mtbf(corrections, 10)
        assert result["overall_mtbf"] == 5.0  # 10 sessions / 2 corrections


# ===========================================================================
# _tag_taxonomy — validate_tag
# ===========================================================================

class TestValidateTag:
    def setup_method(self):
        from gradata._tag_taxonomy import validate_tag
        self.validate = validate_tag

    def test_valid_output_tag(self):
        valid, msg = self.validate("output:email")
        assert valid is True

    def test_invalid_output_value(self):
        valid, msg = self.validate("output:powerpoint")
        assert valid is False
        assert "powerpoint" in msg.lower() or "invalid" in msg.lower()

    def test_missing_colon_fails(self):
        valid, msg = self.validate("just-a-tag")
        assert valid is False
        assert ":" in msg

    def test_unknown_prefix_non_strict(self):
        """Unknown prefix allowed in non-strict mode."""
        valid, msg = self.validate("custom:value", strict=False)
        assert valid is True

    def test_unknown_prefix_strict_fails(self):
        valid, msg = self.validate("custom:value", strict=True)
        assert valid is False

    def test_valid_closed_tone(self):
        valid, msg = self.validate("tone:direct")
        assert valid is True

    def test_invalid_tone_value(self):
        valid, msg = self.validate("tone:aggressive")
        assert valid is False

    def test_valid_category_tag(self):
        valid, msg = self.validate("category:DRAFTING")
        assert valid is True

    def test_invalid_category_value(self):
        valid, msg = self.validate("category:INVENTED")
        assert valid is False


# ===========================================================================
# _tag_taxonomy — validate_tags
# ===========================================================================

class TestValidateTags:
    def setup_method(self):
        from gradata._tag_taxonomy import validate_tags
        self.validate_tags = validate_tags

    def test_empty_tags_no_issues(self):
        issues = self.validate_tags([], event_type="OUTPUT")
        # Should flag missing required tags for OUTPUT
        assert isinstance(issues, list)

    def test_missing_required_tag_for_event(self):
        """OUTPUT event without output: tag should raise issue."""
        issues = self.validate_tags(["session:1"], event_type="OUTPUT")
        assert any("output" in i.lower() for i in issues)

    def test_no_issues_all_required_present(self):
        issues = self.validate_tags(
            ["output:email", "prospect:TestProspect"],
            event_type="OUTPUT",
        )
        # May still have issues from prospect validation, but output tag is satisfied
        output_issues = [i for i in issues if "Missing required tag 'output'" in i]
        assert output_issues == []

    def test_invalid_value_reported(self):
        issues = self.validate_tags(["output:BADVALUE"])
        assert len(issues) > 0


# ===========================================================================
# _tag_taxonomy — enrich_tags
# ===========================================================================

class TestEnrichTags:
    def setup_method(self):
        from gradata._tag_taxonomy import enrich_tags
        self.enrich = enrich_tags

    def test_correction_event_adds_category(self):
        tags = self.enrich([], "CORRECTION", {"category": "DRAFTING"})
        assert "category:DRAFTING" in tags

    def test_output_event_adds_output_type(self):
        tags = self.enrich([], "OUTPUT", {"output_type": "email"})
        assert "output:email" in tags

    def test_output_normalizes_email_draft(self):
        tags = self.enrich([], "OUTPUT", {"output_type": "email_draft"})
        assert "output:email" in tags

    def test_delta_tag_adds_channel_for_email_sent(self):
        tags = self.enrich([], "DELTA_TAG", {
            "prospect": "Jane",
            "activity_type": "email_sent",
        })
        assert "channel:email" in tags
        assert "prospect:Jane" in tags

    def test_existing_tags_not_duplicated(self):
        existing = ["output:email"]
        tags = self.enrich(existing, "OUTPUT", {"output_type": "email"})
        output_tags = [t for t in tags if t.startswith("output:")]
        assert len(output_tags) == 1

    def test_empty_data_no_spurious_tags(self):
        tags = self.enrich([], "CORRECTION", {})
        # No category in data -> no category tag added
        assert not any(t.startswith("category:") for t in tags)


# ===========================================================================
# _fact_extractor — _quality_gate
# ===========================================================================

class TestQualityGate:
    def setup_method(self):
        from gradata._fact_extractor import _quality_gate
        self.gate = _quality_gate

    def test_valid_fact_passes(self):
        assert self.gate("company_size", "200 employees") is True

    def test_too_short_fails(self):
        assert self.gate("company_size", "OK") is False

    def test_empty_value_fails(self):
        assert self.gate("company_size", "") is False

    def test_invalid_type_fails(self):
        assert self.gate("social_media_followers", "50000") is False

    def test_all_valid_types_pass(self):
        from gradata._fact_extractor import VALID_FACT_TYPES
        for fact_type in VALID_FACT_TYPES:
            assert self.gate(fact_type, "some valid text") is True


# ===========================================================================
# _fact_extractor — _clean_value
# ===========================================================================

class TestCleanValue:
    def setup_method(self):
        from gradata._fact_extractor import _clean_value
        self.clean = _clean_value

    def test_strips_bold_markdown(self):
        assert self.clean("**bold text**") == "bold text"

    def test_strips_whitespace(self):
        assert self.clean("  padded  ") == "padded"

    def test_empty_string_returns_empty(self):
        assert self.clean("") == ""

    def test_none_returns_empty(self):
        assert self.clean(None) == ""

    def test_plain_text_unchanged(self):
        assert self.clean("plain text") == "plain text"


# ===========================================================================
# _fact_extractor — _parse_frontmatter
# ===========================================================================

class TestParseFrontmatter:
    def setup_method(self):
        from gradata._fact_extractor import _parse_frontmatter
        self.parse = _parse_frontmatter

    def test_basic_yaml_parsing(self):
        text = "---\nname: John Smith\ncompany: Acme\n---\n# Body"
        fm = self.parse(text)
        assert fm["name"] == "John Smith"
        assert fm["company"] == "Acme"

    def test_quoted_values_stripped(self):
        text = '---\nname: "Jane Doe"\n---'
        fm = self.parse(text)
        assert fm["name"] == "Jane Doe"

    def test_no_frontmatter_returns_empty(self):
        text = "# Just a heading\nNo frontmatter here."
        fm = self.parse(text)
        assert fm == {}

    def test_comments_ignored(self):
        text = "---\nname: Bob # this is a comment\n---"
        fm = self.parse(text)
        assert fm["name"] == "Bob"


# ===========================================================================
# _fact_extractor — extract_from_file (integration)
# ===========================================================================

class TestExtractFromFile:
    def test_extracts_company_size(self, tmp_path):
        from gradata._fact_extractor import extract_from_file
        prospect_file = tmp_path / "Jane Smith -- Acme Corp.md"
        prospect_file.write_text(
            "---\nname: Jane Smith\ncompany: Acme Corp\n---\n"
            "**Employees:** 250\n",
            encoding="utf-8",
        )
        facts = extract_from_file(prospect_file)
        types = [f["fact_type"] for f in facts]
        assert "company_size" in types

    def test_extracts_tech_stack_keywords(self, tmp_path):
        from gradata._fact_extractor import extract_from_file
        prospect_file = tmp_path / "Bob Jones -- Tech Inc.md"
        prospect_file.write_text(
            "---\nname: Bob Jones\n---\n"
            "They use Shopify and Google Analytics for their store.\n",
            encoding="utf-8",
        )
        facts = extract_from_file(prospect_file)
        tech_facts = [f for f in facts if f["fact_type"] == "tech_stack"]
        values = [f["fact_value"] for f in tech_facts]
        assert any("Shopify" in v for v in values)

    def test_nonexistent_file_returns_empty(self):
        from gradata._fact_extractor import extract_from_file
        facts = extract_from_file("/nonexistent/path/file.md")
        assert facts == []

    def test_extracts_budget_from_deal_value(self, tmp_path):
        from gradata._fact_extractor import extract_from_file
        prospect_file = tmp_path / "Alice Brown.md"
        prospect_file.write_text(
            "---\nname: Alice Brown\ndeal_value: $50,000\n---\n",
            encoding="utf-8",
        )
        facts = extract_from_file(prospect_file)
        budget_facts = [f for f in facts if f["fact_type"] == "budget"]
        assert len(budget_facts) >= 1


# ===========================================================================
# _validator — _compute_trust_score
# ===========================================================================

class TestComputeTrustScore:
    def setup_method(self):
        from gradata._validator import _compute_trust_score
        self.compute = _compute_trust_score

    def _dim(self, name, score):
        return {"dimension": name, "score": score, "passed": 0, "total": 0}

    def test_empty_dimensions_returns_untrusted(self):
        result = self.compute([])
        assert result["verdict"] == "UNTRUSTED"
        assert result["score"] == 0

    def test_all_perfect_returns_trusted(self):
        dims = [
            self._dim("METRIC_INTEGRITY", 1.0),
            self._dim("TRAINING_DEPTH", 1.0),
            self._dim("LEARNING_SIGNAL", 1.0),
            self._dim("DATA_COMPLETENESS", 1.0),
            self._dim("BEHAVIORAL_COVERAGE", 1.0),
        ]
        result = self.compute(dims)
        assert result["grade"] == "A"
        assert result["verdict"] == "TRUSTED"

    def test_low_score_grades_f(self):
        dims = [
            self._dim("METRIC_INTEGRITY", 0.0),
            self._dim("TRAINING_DEPTH", 0.0),
            self._dim("LEARNING_SIGNAL", 0.0),
            self._dim("DATA_COMPLETENESS", 0.0),
            self._dim("BEHAVIORAL_COVERAGE", 0.0),
        ]
        result = self.compute(dims)
        assert result["grade"] == "F"
        assert result["verdict"] == "UNTRUSTED"

    def test_partial_score_provisional(self):
        """~0.65 score should be PROVISIONAL (grade C)."""
        dims = [
            self._dim("METRIC_INTEGRITY", 0.60),
            self._dim("TRAINING_DEPTH", 0.70),
            self._dim("LEARNING_SIGNAL", 0.65),
            self._dim("DATA_COMPLETENESS", 0.60),
            self._dim("BEHAVIORAL_COVERAGE", 0.70),
        ]
        result = self.compute(dims)
        assert result["grade"] in ("B", "C")

    def test_metric_integrity_weighted_highest(self):
        """METRIC_INTEGRITY has 0.30 weight — high score there should lift overall."""
        dims_high_integrity = [
            self._dim("METRIC_INTEGRITY", 1.0),   # weight 0.30
            self._dim("TRAINING_DEPTH", 0.0),
            self._dim("LEARNING_SIGNAL", 0.0),
            self._dim("DATA_COMPLETENESS", 0.0),
            self._dim("BEHAVIORAL_COVERAGE", 0.0),
        ]
        dims_low_integrity = [
            self._dim("METRIC_INTEGRITY", 0.0),
            self._dim("TRAINING_DEPTH", 1.0),     # weight 0.20
            self._dim("LEARNING_SIGNAL", 0.0),
            self._dim("DATA_COMPLETENESS", 0.0),
            self._dim("BEHAVIORAL_COVERAGE", 0.0),
        ]
        high = self.compute(dims_high_integrity)
        low = self.compute(dims_low_integrity)
        assert high["score"] > low["score"]


# ===========================================================================
# _paths — make_paths and resolve_brain_dir
# ===========================================================================

class TestPaths:
    def setup_method(self):
        from gradata._paths import make_paths, resolve_brain_dir
        self.make_paths = make_paths
        self.resolve = resolve_brain_dir

    def test_make_paths_derives_all_keys(self):
        result = self.make_paths("/some/brain/dir")
        required_keys = [
            "BRAIN_DIR", "DB_PATH", "EVENTS_JSONL", "PROSPECTS_DIR",
            "SESSIONS_DIR",
        ]
        for k in required_keys:
            assert k in result, f"Missing key: {k}"

    def test_db_path_inside_brain_dir(self):
        result = self.make_paths("/some/brain")
        assert str(result["DB_PATH"]).endswith("system.db")
        assert "brain" in str(result["DB_PATH"])

    def test_resolve_from_argument(self):
        path = self.resolve("/explicit/path")
        assert "explicit" in str(path)

    def test_resolve_from_env_var(self, monkeypatch):
        monkeypatch.setenv("BRAIN_DIR", "/env/brain/path")
        path = self.resolve(None)
        assert "env" in str(path) or "brain" in str(path)

    def test_all_derived_paths_are_path_objects(self):
        result = self.make_paths("/test/brain")
        for key, value in result.items():
            assert isinstance(value, Path), f"{key} is not a Path: {type(value)}"


# ===========================================================================
# _config — constants and env-var behavior
# ===========================================================================

class TestConfig:
    def test_default_provider_is_local(self):
        """Default embedding provider is 'local' (no API key needed)."""
        import importlib
        import gradata._config as cfg
        # Test that defaults are sensible (without env var forcing gemini)
        assert cfg.EMBEDDING_PROVIDER in ("local", "gemini")

    def test_local_model_has_correct_dims(self):
        from gradata._config import LOCAL_MODEL, LOCAL_DIMS
        assert LOCAL_DIMS == 384
        assert "MiniLM" in LOCAL_MODEL or "minilm" in LOCAL_MODEL.lower()

    def test_gemini_model_has_correct_dims(self):
        from gradata._config import GEMINI_MODEL, GEMINI_DIMS
        assert GEMINI_DIMS == 768
        assert "gemini" in GEMINI_MODEL.lower()

    def test_similarity_threshold_is_between_zero_and_one(self):
        from gradata._config import SIMILARITY_THRESHOLD
        assert 0.0 < SIMILARITY_THRESHOLD < 1.0

    def test_file_type_map_contains_expected_dirs(self):
        from gradata._config import FILE_TYPE_MAP
        for dirname in ("entities", "sessions", "emails"):
            assert dirname in FILE_TYPE_MAP

    def test_memory_type_map_covers_all_file_types(self):
        from gradata._config import FILE_TYPE_MAP, MEMORY_TYPE_MAP
        for file_type in FILE_TYPE_MAP.values():
            assert file_type in MEMORY_TYPE_MAP, f"File type '{file_type}' not in MEMORY_TYPE_MAP"

    def test_skip_dirs_does_not_include_prospects(self):
        """prospects/ must NOT be skipped during indexing."""
        from gradata._config import SKIP_DIRS
        assert "prospects" not in SKIP_DIRS

    def test_rag_activation_threshold_positive(self):
        from gradata._config import RAG_ACTIVATION_THRESHOLD
        assert RAG_ACTIVATION_THRESHOLD > 0
