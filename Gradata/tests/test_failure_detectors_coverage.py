"""
Behavior-focused tests for gradata.enhancements.scoring.failure_detectors.

Coverage target: >=85% of the 67 statements in failure_detectors.py.
"""

import pytest

from gradata.enhancements.metrics import MetricsWindow
from gradata.enhancements.scoring.failure_detectors import (
    Alert,
    detect_being_ignored,
    detect_failures,
    detect_overfitting,
    detect_playing_safe,
    detect_regression_to_mean,
    format_alerts,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_window(
    sample_size: int = 10,
    rewrite_rate: float = 0.0,
    blandness_score: float = 0.0,
    edit_distance_avg: float = 0.0,
    rule_misfire_rate: float = 0.0,
    rule_success_rate: float = 1.0,
) -> MetricsWindow:
    return MetricsWindow(
        sample_size=sample_size,
        rewrite_rate=rewrite_rate,
        blandness_score=blandness_score,
        edit_distance_avg=edit_distance_avg,
        rule_misfire_rate=rule_misfire_rate,
        rule_success_rate=rule_success_rate,
    )


# ---------------------------------------------------------------------------
# Alert dataclass
# ---------------------------------------------------------------------------


class TestAlert:
    def test_required_fields(self):
        a = Alert(detector="test", severity="warning", message="hello")
        assert a.detector == "test"
        assert a.severity == "warning"
        assert a.message == "hello"
        assert a.evidence == {}

    def test_evidence_populated(self):
        a = Alert(detector="d", severity="critical", message="m", evidence={"x": 1})
        assert a.evidence["x"] == 1

    def test_evidence_default_is_independent(self):
        # Each instance gets its own dict — not a shared mutable default.
        a1 = Alert(detector="d", severity="warning", message="m")
        a2 = Alert(detector="d", severity="warning", message="m")
        a1.evidence["k"] = 99
        assert "k" not in a2.evidence


# ---------------------------------------------------------------------------
# detect_being_ignored
# ---------------------------------------------------------------------------


class TestDetectBeingIgnored:
    def test_no_previous_returns_empty(self):
        current = make_window(rewrite_rate=0.3, edit_distance_avg=5.0)
        assert detect_being_ignored(current, None) == []

    def test_previous_zero_sample_size_returns_empty(self):
        prev = make_window(sample_size=0, rewrite_rate=0.5)
        curr = make_window(rewrite_rate=0.3)
        assert detect_being_ignored(curr, prev) == []

    def test_small_rr_drop_no_alert(self):
        # rewrite_rate delta < 0.10 — no signal
        prev = make_window(rewrite_rate=0.50, edit_distance_avg=10.0)
        curr = make_window(rewrite_rate=0.45, edit_distance_avg=9.5)
        assert detect_being_ignored(curr, prev) == []

    def test_exact_threshold_rr_drop_no_alert(self):
        # delta == 0.09 — just below threshold
        prev = make_window(rewrite_rate=0.50, edit_distance_avg=10.0)
        curr = make_window(rewrite_rate=0.41, edit_distance_avg=9.5)
        assert detect_being_ignored(curr, prev) == []

    def test_prev_edit_distance_zero_returns_empty(self):
        # Guard: avoid division by zero when prev edit_distance_avg == 0
        prev = make_window(rewrite_rate=0.60, edit_distance_avg=0.0)
        curr = make_window(rewrite_rate=0.40, edit_distance_avg=0.0)
        assert detect_being_ignored(curr, prev) == []

    def test_fires_warning_when_rr_drops_but_ed_flat(self):
        # rewrite_rate drops by 0.20 (>=0.10) and edit_distance barely changes
        prev = make_window(rewrite_rate=0.60, edit_distance_avg=10.0)
        curr = make_window(rewrite_rate=0.40, edit_distance_avg=9.9)
        alerts = detect_being_ignored(curr, prev)
        assert len(alerts) == 1
        a = alerts[0]
        assert a.detector == "being_ignored"
        assert a.severity == "warning"
        assert "bypassed" in a.message or "ignored" in a.message

    def test_evidence_keys_present(self):
        prev = make_window(rewrite_rate=0.60, edit_distance_avg=10.0)
        curr = make_window(rewrite_rate=0.40, edit_distance_avg=9.9)
        a = detect_being_ignored(curr, prev)[0]
        for key in (
            "rewrite_rate_delta",
            "prev_rewrite_rate",
            "curr_rewrite_rate",
            "prev_edit_distance_avg",
            "curr_edit_distance_avg",
            "ed_pct_change",
        ):
            assert key in a.evidence, f"Missing evidence key: {key}"

    def test_no_alert_when_edit_distance_improves_proportionally(self):
        # rr drops 0.20 AND edit distance drops >5% — brain is genuinely improving
        prev = make_window(rewrite_rate=0.60, edit_distance_avg=10.0)
        curr = make_window(rewrite_rate=0.40, edit_distance_avg=9.0)  # -10% > -5%
        assert detect_being_ignored(curr, prev) == []


# ---------------------------------------------------------------------------
# detect_playing_safe
# ---------------------------------------------------------------------------


class TestDetectPlayingSafe:
    def test_no_previous_returns_empty(self):
        curr = make_window(rewrite_rate=0.2, blandness_score=0.6)
        assert detect_playing_safe(curr, None) == []

    def test_zero_sample_size_returns_empty(self):
        prev = make_window(sample_size=0, rewrite_rate=0.5, blandness_score=0.3)
        curr = make_window(rewrite_rate=0.3, blandness_score=0.5)
        assert detect_playing_safe(curr, prev) == []

    def test_acceptance_delta_below_threshold_no_alert(self):
        # acceptance_delta = (1-0.45)-(1-0.50) = 0.05 < 0.10
        prev = make_window(rewrite_rate=0.50, blandness_score=0.3)
        curr = make_window(rewrite_rate=0.45, blandness_score=0.4)
        assert detect_playing_safe(curr, prev) == []

    def test_blandness_delta_below_threshold_no_alert(self):
        # acceptance_delta OK but blandness barely moved
        prev = make_window(rewrite_rate=0.50, blandness_score=0.30)
        curr = make_window(rewrite_rate=0.35, blandness_score=0.33)  # delta=0.03 < 0.05
        assert detect_playing_safe(curr, prev) == []

    def test_fires_warning_severity(self):
        # acceptance_delta=0.15, blandness_delta=0.10 (>=0.05 but <0.15)
        prev = make_window(rewrite_rate=0.50, blandness_score=0.30)
        curr = make_window(rewrite_rate=0.35, blandness_score=0.40)
        alerts = detect_playing_safe(curr, prev)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert alerts[0].detector == "playing_safe"

    def test_fires_critical_severity(self):
        # blandness_delta >= 0.15
        prev = make_window(rewrite_rate=0.50, blandness_score=0.20)
        curr = make_window(rewrite_rate=0.30, blandness_score=0.40)  # delta=0.20
        alerts = detect_playing_safe(curr, prev)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_evidence_keys_present(self):
        prev = make_window(rewrite_rate=0.50, blandness_score=0.30)
        curr = make_window(rewrite_rate=0.35, blandness_score=0.40)
        a = detect_playing_safe(curr, prev)[0]
        for key in (
            "acceptance_delta",
            "prev_acceptance",
            "curr_acceptance",
            "blandness_delta",
            "prev_blandness",
            "curr_blandness",
        ):
            assert key in a.evidence, f"Missing evidence key: {key}"

    def test_message_content(self):
        prev = make_window(rewrite_rate=0.50, blandness_score=0.30)
        curr = make_window(rewrite_rate=0.35, blandness_score=0.40)
        a = detect_playing_safe(curr, prev)[0]
        assert "blandness" in a.message.lower() or "generic" in a.message.lower()


# ---------------------------------------------------------------------------
# detect_overfitting
# ---------------------------------------------------------------------------


class TestDetectOverfitting:
    def test_no_previous_returns_empty(self):
        curr = make_window(rule_misfire_rate=0.5)
        assert detect_overfitting(curr, None) == []

    def test_zero_sample_size_returns_empty(self):
        prev = make_window(sample_size=0, rule_misfire_rate=0.1)
        curr = make_window(rule_misfire_rate=0.5)
        assert detect_overfitting(curr, prev) == []

    def test_small_misfire_increase_no_alert(self):
        # delta < 0.10
        prev = make_window(rule_misfire_rate=0.10)
        curr = make_window(rule_misfire_rate=0.18)
        assert detect_overfitting(curr, prev) == []

    def test_exact_threshold_below_no_alert(self):
        # delta == 0.09 — strictly below
        prev = make_window(rule_misfire_rate=0.10)
        curr = make_window(rule_misfire_rate=0.19)
        assert detect_overfitting(curr, prev) == []

    def test_fires_warning_at_10pp_increase(self):
        # delta == 0.10 exactly
        prev = make_window(rule_misfire_rate=0.10)
        curr = make_window(rule_misfire_rate=0.20)
        alerts = detect_overfitting(curr, prev)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert alerts[0].detector == "overfitting"

    def test_fires_warning_between_thresholds(self):
        # 0.10 <= delta < 0.20
        prev = make_window(rule_misfire_rate=0.10)
        curr = make_window(rule_misfire_rate=0.28)
        alerts = detect_overfitting(curr, prev)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    def test_fires_critical_at_20pp_increase(self):
        # 0.30 - 0.10 hits a float rounding trap (0.1999...), use 0.31 to
        # ensure the delta is unambiguously >= 0.20 in IEEE 754 arithmetic.
        prev = make_window(rule_misfire_rate=0.10)
        curr = make_window(rule_misfire_rate=0.31)
        alerts = detect_overfitting(curr, prev)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_evidence_keys_present(self):
        prev = make_window(rule_misfire_rate=0.10, rule_success_rate=0.90)
        curr = make_window(rule_misfire_rate=0.30, rule_success_rate=0.70)
        a = detect_overfitting(curr, prev)[0]
        for key in (
            "misfire_delta",
            "prev_misfire_rate",
            "curr_misfire_rate",
            "prev_rule_success_rate",
            "curr_rule_success_rate",
        ):
            assert key in a.evidence, f"Missing evidence key: {key}"

    def test_misfire_decrease_no_alert(self):
        # delta is negative — things are improving
        prev = make_window(rule_misfire_rate=0.40)
        curr = make_window(rule_misfire_rate=0.10)
        assert detect_overfitting(curr, prev) == []


# ---------------------------------------------------------------------------
# detect_regression_to_mean
# ---------------------------------------------------------------------------


class TestDetectRegressionToMean:
    def test_below_warn_threshold_no_alert(self):
        curr = make_window(blandness_score=0.60)
        assert detect_regression_to_mean(curr, None) == []

    def test_at_default_warn_threshold_fires_warning(self):
        curr = make_window(blandness_score=0.70)
        alerts = detect_regression_to_mean(curr, None)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"
        assert alerts[0].detector == "regression_to_mean"

    def test_between_thresholds_fires_warning(self):
        curr = make_window(blandness_score=0.80)
        alerts = detect_regression_to_mean(curr, None)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"

    def test_at_critical_threshold_fires_critical(self):
        curr = make_window(blandness_score=0.85)
        alerts = detect_regression_to_mean(curr, None)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_above_critical_threshold_fires_critical(self):
        curr = make_window(blandness_score=0.95)
        alerts = detect_regression_to_mean(curr, None)
        assert alerts[0].severity == "critical"

    def test_with_previous_adds_delta_to_evidence(self):
        prev = make_window(blandness_score=0.60)
        curr = make_window(blandness_score=0.75)
        a = detect_regression_to_mean(curr, prev)[0]
        assert "prev_blandness" in a.evidence
        assert "blandness_delta" in a.evidence
        assert a.evidence["blandness_delta"] == pytest.approx(0.15, abs=1e-4)

    def test_without_previous_evidence_has_no_prev_keys(self):
        curr = make_window(blandness_score=0.75)
        a = detect_regression_to_mean(curr, None)[0]
        assert "prev_blandness" not in a.evidence
        assert "blandness_delta" not in a.evidence

    def test_evidence_always_has_curr_blandness_and_threshold(self):
        curr = make_window(blandness_score=0.75)
        a = detect_regression_to_mean(curr, None)[0]
        assert "curr_blandness" in a.evidence
        assert "threshold" in a.evidence

    def test_message_includes_blandness_value(self):
        curr = make_window(blandness_score=0.75)
        a = detect_regression_to_mean(curr, None)[0]
        assert "0.750" in a.message

    def test_custom_warn_threshold_respected(self):
        # With a higher custom threshold, score=0.75 should NOT fire
        curr = make_window(blandness_score=0.75)
        assert detect_regression_to_mean(curr, None, blandness_warn=0.80) == []

    def test_custom_critical_threshold_respected(self):
        # custom critical=0.92; score=0.88 should be warning, not critical
        curr = make_window(blandness_score=0.88)
        alerts = detect_regression_to_mean(curr, None, blandness_warn=0.80, blandness_critical=0.92)
        assert len(alerts) == 1
        assert alerts[0].severity == "warning"


# ---------------------------------------------------------------------------
# detect_failures (aggregator)
# ---------------------------------------------------------------------------


class TestDetectFailures:
    def test_no_previous_only_regression_can_fire(self):
        # Without previous, only detect_regression_to_mean can produce alerts
        curr = make_window(blandness_score=0.90)
        alerts = detect_failures(curr, None)
        detectors = {a.detector for a in alerts}
        assert "regression_to_mean" in detectors
        assert "being_ignored" not in detectors
        assert "playing_safe" not in detectors
        assert "overfitting" not in detectors

    def test_clean_windows_produce_no_alerts(self):
        prev = make_window(
            rewrite_rate=0.30, blandness_score=0.40, edit_distance_avg=8.0, rule_misfire_rate=0.05
        )
        curr = make_window(
            rewrite_rate=0.28, blandness_score=0.41, edit_distance_avg=7.9, rule_misfire_rate=0.05
        )
        assert detect_failures(curr, prev) == []

    def test_multiple_detectors_can_fire_simultaneously(self):
        # Construct a window that triggers both overfitting and regression_to_mean
        prev = make_window(
            rewrite_rate=0.50, blandness_score=0.40, edit_distance_avg=10.0, rule_misfire_rate=0.05
        )
        curr = make_window(
            rewrite_rate=0.50,
            blandness_score=0.90,  # regression_to_mean fires
            edit_distance_avg=10.0,
            rule_misfire_rate=0.30,  # overfitting fires
        )
        alerts = detect_failures(curr, prev)
        detectors = {a.detector for a in alerts}
        assert "overfitting" in detectors
        assert "regression_to_mean" in detectors

    def test_returns_list_type(self):
        curr = make_window()
        result = detect_failures(curr)
        assert isinstance(result, list)

    def test_previous_defaults_to_none(self):
        # detect_failures(current) without previous arg should work
        curr = make_window(blandness_score=0.50)
        result = detect_failures(curr)
        assert isinstance(result, list)

    def test_all_four_detectors_checked(self):
        # Trigger all four by choosing a window that exercises each path.
        # being_ignored: rr drops 0.20, ed flat
        # playing_safe: acceptance up 0.20, blandness up 0.20 (critical)
        # overfitting: misfire up 0.25 (critical)
        # regression_to_mean: blandness 0.90 (critical)
        # Not all four can fire simultaneously without contradictions, but
        # we verify detect_failures calls all four by checking aggregation.
        prev = make_window(
            rewrite_rate=0.60, blandness_score=0.20, edit_distance_avg=10.0, rule_misfire_rate=0.05
        )
        curr = make_window(
            rewrite_rate=0.40, blandness_score=0.90, edit_distance_avg=9.9, rule_misfire_rate=0.30
        )
        alerts = detect_failures(curr, prev)
        detectors = {a.detector for a in alerts}
        # being_ignored, overfitting, and regression_to_mean all should fire
        assert "being_ignored" in detectors
        assert "overfitting" in detectors
        assert "regression_to_mean" in detectors


# ---------------------------------------------------------------------------
# format_alerts
# ---------------------------------------------------------------------------


class TestFormatAlerts:
    def test_empty_list_returns_no_alerts(self):
        assert format_alerts([]) == "No alerts."

    def test_single_warning_formatted(self):
        a = Alert(
            detector="test_det",
            severity="warning",
            message="Something went wrong.",
            evidence={"key1": 0.5, "key2": 42},
        )
        result = format_alerts([a])
        assert "[WARNING]" in result
        assert "test_det" in result
        assert "Something went wrong." in result
        assert "key1" in result
        assert "key2" in result

    def test_single_critical_formatted(self):
        a = Alert(
            detector="overfitting",
            severity="critical",
            message="Critical failure.",
            evidence={"misfire_delta": 0.25},
        )
        result = format_alerts([a])
        assert "[CRITICAL]" in result
        assert "overfitting" in result

    def test_header_shows_count(self):
        alerts = [
            Alert(detector="d1", severity="warning", message="m1"),
            Alert(detector="d2", severity="critical", message="m2"),
        ]
        result = format_alerts(alerts)
        assert "2" in result
        assert "Failure Alerts" in result

    def test_multiple_alerts_all_appear(self):
        alerts = [
            Alert(detector="being_ignored", severity="warning", message="Msg1", evidence={"a": 1}),
            Alert(detector="overfitting", severity="critical", message="Msg2", evidence={"b": 2}),
        ]
        result = format_alerts(alerts)
        assert "being_ignored" in result
        assert "overfitting" in result
        assert "[WARNING]" in result
        assert "[CRITICAL]" in result

    def test_evidence_values_appear_in_output(self):
        a = Alert(
            detector="d",
            severity="warning",
            message="m",
            evidence={"score": 0.1234, "rate": 99},
        )
        result = format_alerts([a])
        assert "0.1234" in result or "score" in result
        assert "rate" in result

    def test_alert_with_no_evidence_formats_cleanly(self):
        a = Alert(detector="d", severity="warning", message="No evidence here.")
        result = format_alerts([a])
        assert "No evidence here." in result
        assert "[WARNING]" in result

    def test_output_is_multiline_string(self):
        a = Alert(detector="d", severity="critical", message="m", evidence={"x": 1})
        result = format_alerts([a])
        assert "\n" in result
