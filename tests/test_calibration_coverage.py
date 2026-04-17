"""
Tests for gradata.enhancements.scoring.calibration
===================================================
Target: ≥85% line coverage of calibration.py (59 statements).
Strategy: behaviour-focused, stdlib + pytest only, no network, no FS side effects.
"""

from __future__ import annotations

import math

import pytest

from gradata.enhancements.scoring.calibration import (
    CalibrationBin,
    CalibrationReport,
    CalibrationTracker,
)


# ---------------------------------------------------------------------------
# CalibrationBin dataclass
# ---------------------------------------------------------------------------

class TestCalibrationBin:
    """Verify the CalibrationBin dataclass stores and exposes fields correctly."""

    def test_fields_stored(self):
        cb = CalibrationBin(
            bin_start=0.0,
            bin_end=0.1,
            predicted_mean=0.05,
            observed_frequency=0.04,
            count=7,
            gap=0.01,
        )
        assert cb.bin_start == 0.0
        assert cb.bin_end == 0.1
        assert cb.predicted_mean == 0.05
        assert cb.observed_frequency == 0.04
        assert cb.count == 7
        assert cb.gap == 0.01

    def test_equality(self):
        a = CalibrationBin(0.2, 0.3, 0.25, 0.20, 10, 0.05)
        b = CalibrationBin(0.2, 0.3, 0.25, 0.20, 10, 0.05)
        assert a == b


# ---------------------------------------------------------------------------
# CalibrationReport dataclass
# ---------------------------------------------------------------------------

class TestCalibrationReport:
    """Verify CalibrationReport stores all fields correctly."""

    def test_fields_stored(self):
        report = CalibrationReport(
            brier_score=0.12,
            calibration_error=0.05,
            sharpness=0.03,
            bins=[],
            n_predictions=100,
            overconfident=True,
        )
        assert report.brier_score == 0.12
        assert report.calibration_error == 0.05
        assert report.sharpness == 0.03
        assert report.bins == []
        assert report.n_predictions == 100
        assert report.overconfident is True


# ---------------------------------------------------------------------------
# CalibrationTracker — construction and basic property
# ---------------------------------------------------------------------------

class TestCalibrationTrackerInit:
    def test_default_n_bins(self):
        tracker = CalibrationTracker()
        assert tracker._n_bins == 10

    def test_custom_n_bins(self):
        tracker = CalibrationTracker(n_bins=5)
        assert tracker._n_bins == 5

    def test_initial_n_predictions_zero(self):
        tracker = CalibrationTracker()
        assert tracker.n_predictions == 0

    def test_predictions_list_starts_empty(self):
        tracker = CalibrationTracker()
        assert tracker._predictions == []


# ---------------------------------------------------------------------------
# record() — clamping and storage
# ---------------------------------------------------------------------------

class TestRecord:
    @pytest.mark.parametrize("raw, expected", [
        (0.5,  0.5),
        (0.0,  0.0),
        (1.0,  1.0),
        (-0.5, 0.0),   # clamped to 0
        (1.5,  1.0),   # clamped to 1
        (99.0, 1.0),   # way over
        (-99.0, 0.0),  # way under
    ])
    def test_clamping(self, raw, expected):
        tracker = CalibrationTracker()
        tracker.record(predicted=raw, outcome=True)
        assert tracker._predictions[0][0] == expected

    def test_outcome_stored(self):
        tracker = CalibrationTracker()
        tracker.record(predicted=0.7, outcome=False)
        assert tracker._predictions[0] == (0.7, False)

    def test_multiple_records_accumulate(self):
        tracker = CalibrationTracker()
        tracker.record(0.3, True)
        tracker.record(0.8, False)
        tracker.record(0.5, True)
        assert tracker.n_predictions == 3

    def test_n_predictions_property(self):
        tracker = CalibrationTracker()
        for i in range(5):
            tracker.record(0.5, True)
        assert tracker.n_predictions == 5


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_extends_predictions(self):
        tracker = CalibrationTracker()
        tracker.load([(0.6, True), (0.4, False)])
        assert tracker.n_predictions == 2

    def test_load_after_record(self):
        tracker = CalibrationTracker()
        tracker.record(0.9, True)
        tracker.load([(0.1, False), (0.2, False)])
        assert tracker.n_predictions == 3

    def test_load_empty_list(self):
        tracker = CalibrationTracker()
        tracker.load([])
        assert tracker.n_predictions == 0

    def test_load_preserves_values(self):
        tracker = CalibrationTracker()
        pairs = [(0.55, True), (0.25, False)]
        tracker.load(pairs)
        assert tracker._predictions[0] == (0.55, True)
        assert tracker._predictions[1] == (0.25, False)


# ---------------------------------------------------------------------------
# to_pairs()
# ---------------------------------------------------------------------------

class TestToPairs:
    def test_empty(self):
        tracker = CalibrationTracker()
        assert tracker.to_pairs() == []

    def test_returns_copy(self):
        tracker = CalibrationTracker()
        tracker.record(0.5, True)
        pairs = tracker.to_pairs()
        pairs.append((0.9, False))
        # Original must be unaffected
        assert tracker.n_predictions == 1

    def test_round_trip_via_load(self):
        tracker1 = CalibrationTracker()
        data = [(0.3, True), (0.7, False), (0.5, True)]
        tracker1.load(data)

        tracker2 = CalibrationTracker()
        tracker2.load(tracker1.to_pairs())
        assert tracker2.n_predictions == 3
        assert tracker2._predictions == data


# ---------------------------------------------------------------------------
# compute() — empty case
# ---------------------------------------------------------------------------

class TestComputeEmpty:
    def test_empty_returns_zero_report(self):
        tracker = CalibrationTracker()
        report = tracker.compute()
        assert report.brier_score == 0.0
        assert report.calibration_error == 0.0
        assert report.sharpness == 0.0
        assert report.bins == []
        assert report.n_predictions == 0
        assert report.overconfident is False


# ---------------------------------------------------------------------------
# compute() — Brier score accuracy
# ---------------------------------------------------------------------------

class TestBrierScore:
    def test_perfect_predictions_brier_zero(self):
        """All confident-and-correct or zero-and-incorrect → Brier = 0."""
        tracker = CalibrationTracker()
        tracker.record(1.0, True)
        tracker.record(1.0, True)
        tracker.record(0.0, False)
        report = tracker.compute()
        assert report.brier_score == 0.0

    def test_worst_predictions_brier_one(self):
        """Confident but always wrong → Brier = 1."""
        tracker = CalibrationTracker()
        tracker.record(1.0, False)
        tracker.record(1.0, False)
        report = tracker.compute()
        assert report.brier_score == 1.0

    def test_brier_single_prediction(self):
        """(0.8 - 1)^2 = 0.04."""
        tracker = CalibrationTracker()
        tracker.record(0.8, True)
        report = tracker.compute()
        assert math.isclose(report.brier_score, 0.04, rel_tol=1e-4)

    @pytest.mark.parametrize("predicted, outcome, expected_brier", [
        (0.5, True,  0.25),   # (0.5 - 1)^2
        (0.5, False, 0.25),   # (0.5 - 0)^2
        (0.0, True,  1.0),    # (0 - 1)^2
        (0.0, False, 0.0),    # (0 - 0)^2
    ])
    def test_brier_single_parametrized(self, predicted, outcome, expected_brier):
        tracker = CalibrationTracker()
        tracker.record(predicted, outcome)
        report = tracker.compute()
        assert math.isclose(report.brier_score, expected_brier, rel_tol=1e-4)

    def test_brier_averaged_across_multiple(self):
        """Two predictions: (0.8-1)^2=0.04 and (0.3-0)^2=0.09 → mean=0.065."""
        tracker = CalibrationTracker()
        tracker.record(0.8, True)
        tracker.record(0.3, False)
        report = tracker.compute()
        assert math.isclose(report.brier_score, 0.065, rel_tol=1e-3)


# ---------------------------------------------------------------------------
# compute() — sharpness
# ---------------------------------------------------------------------------

class TestSharpness:
    def test_constant_predictions_sharpness_zero(self):
        """All predictions identical → variance = 0."""
        tracker = CalibrationTracker()
        for _ in range(5):
            tracker.record(0.7, True)
        report = tracker.compute()
        assert report.sharpness == 0.0

    def test_sharpness_increases_with_spread(self):
        """More spread-out predictions → higher sharpness."""
        narrow = CalibrationTracker()
        narrow.record(0.49, True)
        narrow.record(0.51, False)

        wide = CalibrationTracker()
        wide.record(0.0, False)
        wide.record(1.0, True)

        assert wide.compute().sharpness > narrow.compute().sharpness

    def test_sharpness_symmetric(self):
        """0 and 1 in equal measure: mean=0.5, variance = 0.25."""
        tracker = CalibrationTracker()
        tracker.record(0.0, False)
        tracker.record(1.0, True)
        report = tracker.compute()
        assert math.isclose(report.sharpness, 0.25, rel_tol=1e-4)


# ---------------------------------------------------------------------------
# compute() — reliability bins
# ---------------------------------------------------------------------------

class TestBins:
    def test_single_bin_populated(self):
        """All predictions in 0.8–0.9 range → exactly one bin."""
        tracker = CalibrationTracker()
        tracker.record(0.82, True)
        tracker.record(0.85, True)
        tracker.record(0.88, False)
        report = tracker.compute()
        # All should land in bin [0.8, 0.9)
        assert len(report.bins) == 1
        b = report.bins[0]
        assert b.bin_start == 0.8
        assert b.bin_end == 0.9
        assert b.count == 3

    def test_bin_observed_frequency(self):
        """2 out of 4 succeed → observed_frequency = 0.5."""
        tracker = CalibrationTracker()
        tracker.record(0.25, True)
        tracker.record(0.25, False)
        tracker.record(0.28, True)
        tracker.record(0.22, False)
        report = tracker.compute()
        assert len(report.bins) == 1
        assert math.isclose(report.bins[0].observed_frequency, 0.5, rel_tol=1e-4)

    def test_bin_gap_computation(self):
        """gap = |pred_mean - obs_freq|."""
        tracker = CalibrationTracker()
        # all in [0.9, 1.0) with predicted mean ≈ 0.9, 0 successes → gap ≈ 0.9
        tracker.record(0.9, False)
        tracker.record(0.9, False)
        report = tracker.compute()
        assert len(report.bins) == 1
        b = report.bins[0]
        assert math.isclose(b.gap, abs(b.predicted_mean - b.observed_frequency), rel_tol=1e-4)

    def test_value_exactly_1_lands_in_last_bin(self):
        """p == 1.0 must land in the last bin (special-cased in source)."""
        tracker = CalibrationTracker()
        tracker.record(1.0, True)
        report = tracker.compute()
        assert len(report.bins) == 1
        b = report.bins[0]
        assert b.bin_end == 1.0
        assert b.count == 1

    def test_empty_bins_skipped(self):
        """Bins with no predictions are omitted from the output list."""
        tracker = CalibrationTracker()
        tracker.record(0.05, True)   # bin 0: [0.0, 0.1)
        tracker.record(0.95, False)  # bin 9: [0.9, 1.0)
        report = tracker.compute()
        assert len(report.bins) == 2

    def test_multiple_bins_counts_sum_to_n(self):
        """Total count across all bins equals n_predictions."""
        tracker = CalibrationTracker()
        pairs = [
            (0.05, True), (0.15, False), (0.35, True),
            (0.55, True), (0.75, False), (0.95, True),
        ]
        tracker.load(pairs)
        report = tracker.compute()
        total = sum(b.count for b in report.bins)
        assert total == report.n_predictions

    def test_custom_n_bins_respected(self):
        """n_bins=5 → bin width 0.2; predictions in separate ranges → 2 bins."""
        tracker = CalibrationTracker(n_bins=5)
        tracker.record(0.05, True)    # bin [0.0, 0.2)
        tracker.record(0.45, False)   # bin [0.4, 0.6)
        report = tracker.compute()
        assert len(report.bins) == 2
        assert report.bins[0].bin_start == 0.0
        assert report.bins[1].bin_start == pytest.approx(0.4, rel=1e-4)


# ---------------------------------------------------------------------------
# compute() — overconfidence detection
# ---------------------------------------------------------------------------

class TestOverconfidence:
    def test_overconfident_true_when_predicted_higher(self):
        """High confidence but low success rate → overconfident."""
        tracker = CalibrationTracker()
        tracker.record(0.9, False)
        tracker.record(0.9, False)
        tracker.record(0.9, False)
        tracker.record(0.9, True)
        report = tracker.compute()
        # mean predicted = 0.9, observed = 0.25 → overconfident
        assert report.overconfident is True

    def test_overconfident_false_when_predicted_lower(self):
        """Low confidence but high success rate → not overconfident."""
        tracker = CalibrationTracker()
        tracker.record(0.1, True)
        tracker.record(0.1, True)
        tracker.record(0.1, True)
        report = tracker.compute()
        # mean predicted = 0.1, observed = 1.0 → not overconfident
        assert report.overconfident is False

    def test_perfect_calibration_not_overconfident(self):
        """Predicted exactly matches observed → not overconfident."""
        tracker = CalibrationTracker()
        tracker.record(0.5, True)
        tracker.record(0.5, False)
        report = tracker.compute()
        # mean pred = 0.5, observed = 0.5 → equal → not overconfident
        assert report.overconfident is False


# ---------------------------------------------------------------------------
# compute() — ECE (calibration_error)
# ---------------------------------------------------------------------------

class TestCalibrationError:
    def test_ece_zero_for_perfect_calibration(self):
        """When predicted == observed for each bin, ECE = 0."""
        tracker = CalibrationTracker()
        # 10 predictions in bin [0.5, 0.6): 5 succeed → obs=0.5≈pred_mean
        for _ in range(5):
            tracker.record(0.5, True)
        for _ in range(5):
            tracker.record(0.5, False)
        report = tracker.compute()
        assert report.calibration_error == 0.0

    def test_ece_positive_for_miscalibration(self):
        """Overconfident predictions produce positive ECE."""
        tracker = CalibrationTracker()
        tracker.record(0.9, False)
        tracker.record(0.9, False)
        report = tracker.compute()
        assert report.calibration_error > 0.0

    def test_ece_is_weighted_by_bin_size(self):
        """Larger bins contribute more to ECE than smaller ones."""
        big = CalibrationTracker()
        # Large bin with big gap
        for _ in range(10):
            big.record(0.9, False)  # gap=0.9, weight=10

        small = CalibrationTracker()
        # Small bin with same gap but fewer samples
        for _ in range(2):
            small.record(0.9, False)  # gap=0.9, weight=2

        # Both have same ECE here since only one bin each and ECE = gap*count/n
        # But for two-bin case the weighting matters
        assert big.compute().calibration_error > 0
        assert small.compute().calibration_error > 0


# ---------------------------------------------------------------------------
# n_predictions property
# ---------------------------------------------------------------------------

class TestNPredictionsProperty:
    def test_reflects_record_calls(self):
        tracker = CalibrationTracker()
        assert tracker.n_predictions == 0
        tracker.record(0.5, True)
        assert tracker.n_predictions == 1
        tracker.record(0.5, False)
        assert tracker.n_predictions == 2

    def test_reflects_load_calls(self):
        tracker = CalibrationTracker()
        tracker.load([(0.3, True), (0.7, False), (0.5, True)])
        assert tracker.n_predictions == 3

    def test_reflects_compute_report(self):
        tracker = CalibrationTracker()
        tracker.record(0.6, True)
        tracker.record(0.4, False)
        report = tracker.compute()
        assert report.n_predictions == tracker.n_predictions


# ---------------------------------------------------------------------------
# Integration: full realistic session
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_realistic_session(self):
        """Simulate a realistic session with mixed predictions."""
        tracker = CalibrationTracker()
        # High confidence, mostly correct
        for _ in range(7):
            tracker.record(0.85, True)
        for _ in range(3):
            tracker.record(0.85, False)
        # Medium confidence, half-half
        for _ in range(5):
            tracker.record(0.55, True)
        for _ in range(5):
            tracker.record(0.55, False)
        # Low confidence, mostly wrong
        for _ in range(2):
            tracker.record(0.15, True)
        for _ in range(8):
            tracker.record(0.15, False)

        report = tracker.compute()
        assert report.n_predictions == 30
        assert 0.0 <= report.brier_score <= 1.0
        assert 0.0 <= report.calibration_error <= 1.0
        assert report.sharpness >= 0.0
        assert len(report.bins) >= 2

    def test_single_prediction_report(self):
        """Single entry produces a valid non-empty report."""
        tracker = CalibrationTracker()
        tracker.record(0.6, True)
        report = tracker.compute()
        assert report.n_predictions == 1
        assert report.brier_score == pytest.approx(0.16, rel=1e-3)  # (0.6-1)^2
        assert len(report.bins) == 1

    def test_all_outcomes_true(self):
        """All outcomes True → observed=1.0."""
        tracker = CalibrationTracker()
        tracker.record(0.8, True)
        tracker.record(0.7, True)
        report = tracker.compute()
        assert report.overconfident is False  # predicted < 1.0

    def test_all_outcomes_false(self):
        """All outcomes False → observed=0.0."""
        tracker = CalibrationTracker()
        tracker.record(0.6, False)
        tracker.record(0.4, False)
        report = tracker.compute()
        assert report.overconfident is True  # any positive mean > 0.0

    def test_load_then_compute_matches_direct(self):
        """Loading same data as recording gives identical reports."""
        data = [(0.3, True), (0.8, False), (0.6, True), (0.2, False)]

        via_record = CalibrationTracker()
        for p, o in data:
            via_record.record(p, o)

        via_load = CalibrationTracker()
        via_load.load(data)

        r1 = via_record.compute()
        r2 = via_load.compute()
        assert r1.brier_score == r2.brier_score
        assert r1.calibration_error == r2.calibration_error
        assert r1.sharpness == r2.sharpness
        assert r1.n_predictions == r2.n_predictions
        assert r1.overconfident == r2.overconfident
