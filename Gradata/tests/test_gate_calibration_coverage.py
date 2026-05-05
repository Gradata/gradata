"""
Behavior-focused pytest coverage for gate_calibration.py.

Target: >=85% line coverage of
  src/gradata/enhancements/scoring/gate_calibration.py
stdlib + pytest only; no network, no FS side-effects outside tmp_path.
"""

from __future__ import annotations

import pytest
from src.gradata.enhancements.scoring.gate_calibration import (
    CalibrationResult,
    GateCalibrator,
    ThresholdCandidate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calibrator(**kwargs) -> GateCalibrator:
    """Return a GateCalibrator with default args, overridable via kwargs."""
    return GateCalibrator(**kwargs)


def _clear_accept_reject_data(
    n_accept: int, n_reject: int, accept_score: float = 9.0, reject_score: float = 5.0
) -> list[tuple[float, bool]]:
    """Produce a simple labelled dataset with no ambiguity."""
    return [(accept_score, True)] * n_accept + [(reject_score, False)] * n_reject


# ---------------------------------------------------------------------------
# Dataclass shape tests
# ---------------------------------------------------------------------------


class TestDataclassShapes:
    def test_threshold_candidate_fields(self):
        tc = ThresholdCandidate(
            threshold=8.0,
            precision=0.9,
            recall=0.8,
            f1=0.847,
            true_positives=9,
            false_positives=1,
            true_negatives=10,
            false_negatives=2,
        )
        assert tc.threshold == 8.0
        assert tc.true_positives == 9
        assert tc.false_negatives == 2

    def test_calibration_result_fields(self):
        cr = CalibrationResult(
            recommended_threshold=7.5,
            f1_at_recommended=0.84,
            current_threshold=8.0,
            current_f1=0.71,
            n_samples=60,
            sufficient_data=True,
            candidates=[],
            human_accept_rate=0.6,
            auto_pass_rate=0.5,
        )
        assert cr.sufficient_data is True
        assert cr.n_samples == 60


# ---------------------------------------------------------------------------
# GateCalibrator construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self):
        gc = GateCalibrator()
        assert gc.n_samples == 0
        assert gc._current_threshold == 8.0
        assert gc._min_samples == 50
        assert gc._sweep_min == 5.0
        assert gc._sweep_max == 9.5
        assert gc._prefer_higher_on_tie is True

    def test_custom_params(self):
        gc = GateCalibrator(
            current_threshold=7.5,
            min_samples=20,
            sweep_min=6.0,
            sweep_max=9.0,
            prefer_higher_on_tie=False,
        )
        assert gc._current_threshold == 7.5
        assert gc._min_samples == 20
        assert gc._sweep_min == 6.0
        assert gc._sweep_max == 9.0
        assert gc._prefer_higher_on_tie is False


# ---------------------------------------------------------------------------
# record() and n_samples
# ---------------------------------------------------------------------------


class TestRecord:
    def test_single_record(self):
        gc = GateCalibrator()
        gc.record(8.5, True)
        assert gc.n_samples == 1

    def test_multiple_records(self):
        gc = GateCalibrator()
        for score, verdict in [(7.0, False), (8.0, True), (9.0, True)]:
            gc.record(score, verdict)
        assert gc.n_samples == 3

    def test_record_stores_exact_values(self):
        gc = GateCalibrator()
        gc.record(7.123, False)
        pairs = gc.to_pairs()
        assert len(pairs) == 1
        assert pairs[0] == (7.123, False)


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_extends_data(self):
        gc = GateCalibrator()
        gc.record(8.0, True)
        gc.load([(7.0, False), (9.0, True)])
        assert gc.n_samples == 3

    def test_load_empty_list(self):
        gc = GateCalibrator()
        gc.load([])
        assert gc.n_samples == 0

    def test_load_then_record(self):
        gc = GateCalibrator()
        gc.load([(8.5, True)] * 5)
        gc.record(6.0, False)
        assert gc.n_samples == 6


# ---------------------------------------------------------------------------
# to_pairs()
# ---------------------------------------------------------------------------


class TestToPairs:
    def test_empty(self):
        gc = GateCalibrator()
        assert gc.to_pairs() == []

    def test_returns_copy_not_reference(self):
        gc = GateCalibrator()
        gc.record(8.0, True)
        pairs = gc.to_pairs()
        pairs.append((1.0, False))  # mutate the return value
        assert gc.n_samples == 1  # internal list must be unchanged

    def test_order_preserved(self):
        gc = GateCalibrator()
        data = [(8.0, True), (7.0, False), (9.0, True)]
        gc.load(data)
        assert gc.to_pairs() == data


# ---------------------------------------------------------------------------
# compute_optimal_threshold — empty data
# ---------------------------------------------------------------------------


class TestComputeEmpty:
    def test_empty_returns_sentinel(self):
        gc = GateCalibrator()
        result = gc.compute_optimal_threshold()
        assert isinstance(result, CalibrationResult)
        assert result.n_samples == 0
        assert result.sufficient_data is False
        assert result.f1_at_recommended == 0.0
        assert result.current_f1 == 0.0
        assert result.candidates == []
        assert result.human_accept_rate == 0.0
        assert result.auto_pass_rate == 0.0
        # Falls back to current threshold
        assert result.recommended_threshold == 8.0


# ---------------------------------------------------------------------------
# compute_optimal_threshold — insufficient data (n < min_samples)
# ---------------------------------------------------------------------------


class TestComputeInsufficientData:
    def test_insufficient_data_flag(self):
        gc = GateCalibrator(min_samples=50)
        gc.load(_clear_accept_reject_data(10, 10))
        result = gc.compute_optimal_threshold()
        assert result.sufficient_data is False
        assert result.n_samples == 20

    def test_still_returns_candidates_when_insufficient(self):
        gc = GateCalibrator(min_samples=50)
        gc.load(_clear_accept_reject_data(5, 5))
        result = gc.compute_optimal_threshold()
        # Sweep 5.0–9.5 in 0.1 steps = 46 candidates
        assert len(result.candidates) == 46


# ---------------------------------------------------------------------------
# compute_optimal_threshold — sufficient data (n >= min_samples)
# ---------------------------------------------------------------------------


class TestComputeSufficientData:
    def test_sufficient_data_flag(self):
        gc = GateCalibrator(min_samples=50)
        gc.load(_clear_accept_reject_data(30, 25))
        result = gc.compute_optimal_threshold()
        assert result.sufficient_data is True
        assert result.n_samples == 55

    def test_perfect_separation_recommends_boundary(self):
        """All accepts score 9.0, all rejects score 5.0 — any threshold
        between 5.0 and 9.0 should yield F1=1.0; tie-break picks highest."""
        gc = GateCalibrator(min_samples=1, sweep_min=5.0, sweep_max=9.5)
        gc.load(_clear_accept_reject_data(30, 30, accept_score=9.0, reject_score=5.0))
        result = gc.compute_optimal_threshold()
        assert result.f1_at_recommended == 1.0
        # With prefer_higher_on_tie=True, should pick the highest t that still
        # achieves F1=1.0, which is 9.0 (score >= 9.0 captures all accepts)
        assert result.recommended_threshold == 9.0

    def test_human_accept_rate_correct(self):
        gc = GateCalibrator(min_samples=1)
        gc.load([(9.0, True)] * 3 + [(5.0, False)] * 7)
        result = gc.compute_optimal_threshold()
        assert result.human_accept_rate == pytest.approx(0.3, abs=1e-4)

    def test_auto_pass_rate_correct(self):
        # current_threshold=8.0; scores: 9 > 8 (pass), 5 < 8 (fail)
        gc = GateCalibrator(current_threshold=8.0, min_samples=1)
        gc.load([(9.0, True)] * 4 + [(5.0, False)] * 6)
        result = gc.compute_optimal_threshold()
        assert result.auto_pass_rate == pytest.approx(0.4, abs=1e-4)

    def test_candidate_count_matches_sweep(self):
        """Default sweep 5.0–9.5 in 0.1 increments = 46 candidates."""
        gc = GateCalibrator(min_samples=1)
        gc.load(_clear_accept_reject_data(30, 25))
        result = gc.compute_optimal_threshold()
        assert len(result.candidates) == 46

    def test_custom_sweep_range(self):
        gc = GateCalibrator(min_samples=1, sweep_min=7.0, sweep_max=8.0)
        gc.load(_clear_accept_reject_data(10, 10))
        result = gc.compute_optimal_threshold()
        # 7.0–8.0 in 0.1 = 11 candidates
        assert len(result.candidates) == 11

    def test_current_threshold_f1_captured(self):
        """current_f1 reflects F1 at the current threshold (8.0)."""
        gc = GateCalibrator(current_threshold=8.0, min_samples=1)
        # All 9.0 accepted, all 5.0 rejected — at threshold 8.0 => F1=1.0
        gc.load(_clear_accept_reject_data(20, 20, accept_score=9.0, reject_score=5.0))
        result = gc.compute_optimal_threshold()
        assert result.current_f1 == pytest.approx(1.0, abs=1e-3)

    def test_result_fields_rounded(self):
        gc = GateCalibrator(min_samples=1)
        gc.load(_clear_accept_reject_data(30, 25))
        result = gc.compute_optimal_threshold()
        # recommended_threshold rounded to 1dp
        assert result.recommended_threshold == round(result.recommended_threshold, 1)
        # f1 rounded to 4dp
        assert result.f1_at_recommended == round(result.f1_at_recommended, 4)


# ---------------------------------------------------------------------------
# _evaluate_threshold — direct coverage of all quadrants
# ---------------------------------------------------------------------------


class TestEvaluateThreshold:
    """Drive _evaluate_threshold through every TP/FP/TN/FN branch."""

    def _gc_with(self, data):
        gc = GateCalibrator(min_samples=1)
        gc.load(data)
        return gc

    def test_all_true_positives(self):
        """score >= threshold AND accepted => TP only."""
        gc = self._gc_with([(9.0, True)] * 5)
        c = gc._evaluate_threshold(8.0)
        assert c.true_positives == 5
        assert c.false_positives == 0
        assert c.false_negatives == 0
        assert c.true_negatives == 0
        assert c.precision == 1.0
        assert c.recall == 1.0
        assert c.f1 == 1.0

    def test_all_false_positives(self):
        """score >= threshold AND NOT accepted => FP only."""
        gc = self._gc_with([(9.0, False)] * 4)
        c = gc._evaluate_threshold(8.0)
        assert c.false_positives == 4
        assert c.true_positives == 0
        assert c.precision == 0.0
        assert c.recall == 0.0
        assert c.f1 == 0.0

    def test_all_true_negatives(self):
        """score < threshold AND NOT accepted => TN only."""
        gc = self._gc_with([(5.0, False)] * 6)
        c = gc._evaluate_threshold(8.0)
        assert c.true_negatives == 6
        assert c.false_negatives == 0
        # precision/recall undefined (0/0) => 0.0
        assert c.precision == 0.0
        assert c.recall == 0.0

    def test_all_false_negatives(self):
        """score < threshold AND accepted => FN only."""
        gc = self._gc_with([(5.0, True)] * 3)
        c = gc._evaluate_threshold(8.0)
        assert c.false_negatives == 3
        assert c.true_positives == 0
        assert c.recall == 0.0
        assert c.f1 == 0.0

    def test_mixed_all_quadrants(self):
        data = [
            (9.0, True),  # TP
            (9.0, False),  # FP
            (5.0, False),  # TN
            (5.0, True),  # FN
        ]
        gc = self._gc_with(data)
        c = gc._evaluate_threshold(8.0)
        assert c.true_positives == 1
        assert c.false_positives == 1
        assert c.true_negatives == 1
        assert c.false_negatives == 1
        assert c.precision == pytest.approx(0.5, abs=1e-4)
        assert c.recall == pytest.approx(0.5, abs=1e-4)
        # F1 = 2*0.5*0.5/(0.5+0.5) = 0.5
        assert c.f1 == pytest.approx(0.5, abs=1e-4)

    def test_candidate_threshold_rounded(self):
        gc = self._gc_with([(8.0, True)])
        c = gc._evaluate_threshold(7.15)
        assert c.threshold == round(7.15, 1)


# ---------------------------------------------------------------------------
# Tie-breaking: prefer_higher_on_tie
# ---------------------------------------------------------------------------


class TestTieBreaking:
    def _tie_data(self):
        """Dataset where multiple thresholds yield the same F1=1.0."""
        return _clear_accept_reject_data(25, 25, accept_score=9.0, reject_score=5.0)

    def test_prefer_higher_picks_highest_tied_threshold(self):
        gc = GateCalibrator(
            min_samples=1,
            prefer_higher_on_tie=True,
            sweep_min=5.0,
            sweep_max=9.5,
        )
        gc.load(self._tie_data())
        result = gc.compute_optimal_threshold()
        assert result.recommended_threshold == 9.0

    def test_prefer_lower_picks_first_tied_threshold(self):
        """With prefer_higher_on_tie=False, the first F1-max wins (5.1 —
        the first threshold above 5.0 that captures all 9.0-scored accepts
        while excluding 5.0-scored rejects)."""
        gc = GateCalibrator(
            min_samples=1,
            prefer_higher_on_tie=False,
            sweep_min=5.0,
            sweep_max=9.5,
        )
        gc.load(self._tie_data())
        result = gc.compute_optimal_threshold()
        # First threshold that correctly separates 9.0 from 5.0 is 5.1
        assert result.recommended_threshold == pytest.approx(5.1, abs=0.05)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_all_accepted(self):
        """100% human accept rate — auto_pass_rate and F1 still computable."""
        gc = GateCalibrator(min_samples=1)
        gc.load([(8.5, True)] * 30)
        result = gc.compute_optimal_threshold()
        assert result.human_accept_rate == 1.0
        # All scores above any threshold <= 8.5 => F1=1.0 for low thresholds
        assert result.f1_at_recommended > 0.0

    def test_all_rejected(self):
        """100% human reject rate — recall is always 0 (no positives)."""
        gc = GateCalibrator(min_samples=1)
        gc.load([(5.0, False)] * 30)
        result = gc.compute_optimal_threshold()
        assert result.human_accept_rate == 0.0
        assert result.f1_at_recommended == 0.0

    def test_single_sample(self):
        gc = GateCalibrator(min_samples=1)
        gc.record(8.5, True)
        result = gc.compute_optimal_threshold()
        assert result.n_samples == 1
        assert result.sufficient_data is True

    def test_threshold_exactly_at_score(self):
        """score == threshold counts as pass (>= boundary)."""
        gc = GateCalibrator(min_samples=1)
        gc.record(8.0, True)
        c = gc._evaluate_threshold(8.0)
        assert c.true_positives == 1

    def test_current_threshold_not_in_sweep_still_returns(self):
        """If sweep range excludes current_threshold, current_f1 stays 0."""
        gc = GateCalibrator(
            current_threshold=8.0,
            min_samples=1,
            sweep_min=5.0,
            sweep_max=7.0,
        )
        gc.load(_clear_accept_reject_data(10, 10))
        result = gc.compute_optimal_threshold()
        # 8.0 is not in [5.0, 7.0] sweep, so current_f1 stays 0.0
        assert result.current_f1 == 0.0

    def test_load_and_record_interleaved(self):
        gc = GateCalibrator(min_samples=1)
        gc.load([(9.0, True)] * 5)
        gc.record(5.0, False)
        gc.load([(8.5, True)] * 4)
        assert gc.n_samples == 10

    def test_recommended_threshold_within_sweep_bounds(self):
        gc = GateCalibrator(min_samples=1, sweep_min=6.0, sweep_max=8.0)
        gc.load(_clear_accept_reject_data(20, 20))
        result = gc.compute_optimal_threshold()
        assert 6.0 <= result.recommended_threshold <= 8.0

    def test_precision_recall_zero_when_no_positives_predicted(self):
        """All scores below threshold => no predicted positives => precision=recall=0."""
        gc = GateCalibrator(min_samples=1)
        gc.load([(4.0, True)] * 5)  # all below any sweep threshold
        c = gc._evaluate_threshold(5.0)
        # score 4.0 < 5.0 => predicted fail; accepted=True => FN
        assert c.false_negatives == 5
        assert c.true_positives == 0
        assert c.precision == 0.0
        assert c.recall == 0.0
        assert c.f1 == 0.0
