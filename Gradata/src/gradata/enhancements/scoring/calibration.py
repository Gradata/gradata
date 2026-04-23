"""
Calibration Tracking — Brier Score for Confidence Verification
===============================================================
Layer 1 Enhancement: pure logic, stdlib only.

Answers the question: "When the system says confidence is 0.70, is the
lesson actually correct 70% of the time?"

Without calibration, confidence numbers are arbitrary. This module
tracks predictions (confidence values) against outcomes (did the lesson
fire correctly or misfire?) and computes:

- Brier score (mean squared error of predictions, lower = better)
- Reliability diagram data (binned calibration curve)
- Sharpness (how spread out the predictions are)

Usage:
    tracker = CalibrationTracker()
    tracker.record(predicted=0.80, outcome=True)   # lesson fired correctly
    tracker.record(predicted=0.80, outcome=False)   # lesson misfired
    report = tracker.compute()
    print(report.brier_score)       # 0.12 (lower is better)
    print(report.calibration_error) # 0.05 (how far off from perfect)

Reference: Brier (1950), "Verification of Forecasts Expressed in Terms
of Probability." Monthly Weather Review.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CalibrationBin:
    """A single bin in the reliability diagram.

    Groups predictions by confidence range and compares predicted
    probability against observed frequency.
    """

    bin_start: float
    bin_end: float
    predicted_mean: float  # Average confidence in this bin
    observed_frequency: float  # Fraction that actually succeeded
    count: int  # Number of predictions in this bin
    gap: float  # |predicted_mean - observed_frequency|


@dataclass
class CalibrationReport:
    """Full calibration analysis.

    Attributes:
        brier_score: Mean squared error of predictions. Range [0, 1].
            0.0 = perfect predictions. 0.25 = no better than random.
        calibration_error: Expected Calibration Error (ECE). Weighted
            average of |predicted - observed| across bins. Lower = better.
        sharpness: Variance of predictions. Higher = more decisive
            (making strong predictions rather than hedging at 0.5).
        bins: Reliability diagram data for visualization.
        n_predictions: Total predictions tracked.
        overconfident: True if system predicts higher than observed outcomes
            (most common failure mode).
    """

    brier_score: float
    calibration_error: float
    sharpness: float
    bins: list[CalibrationBin]
    n_predictions: int
    overconfident: bool


class CalibrationTracker:
    """Track confidence predictions against outcomes for Brier scoring.

    Thread-safe for single-writer scenarios (one session at a time).
    """

    def __init__(self, n_bins: int = 10) -> None:
        self._predictions: list[tuple[float, bool]] = []
        self._n_bins = n_bins

    def record(self, predicted: float, outcome: bool) -> None:
        """Record a prediction-outcome pair.

        Args:
            predicted: Confidence value (0.0 to 1.0) at time of prediction.
            outcome: True if the lesson fired correctly, False if it misfired
                     or was contradicted.
        """
        predicted = max(0.0, min(1.0, predicted))
        self._predictions.append((predicted, outcome))

    def load(self, predictions: list[tuple[float, bool]]) -> None:
        """Load historical prediction-outcome pairs (e.g., from DB)."""
        self._predictions.extend(predictions)

    @property
    def n_predictions(self) -> int:
        return len(self._predictions)

    def compute(self) -> CalibrationReport:
        """Compute full calibration analysis.

        Returns a CalibrationReport with Brier score, ECE, sharpness,
        and reliability diagram bins.
        """
        n = len(self._predictions)
        if n == 0:
            return CalibrationReport(
                brier_score=0.0,
                calibration_error=0.0,
                sharpness=0.0,
                bins=[],
                n_predictions=0,
                overconfident=False,
            )

        # Brier score: mean squared error
        brier = (
            sum((pred - (1.0 if outcome else 0.0)) ** 2 for pred, outcome in self._predictions) / n
        )

        # Sharpness: variance of predictions
        mean_pred = sum(p for p, _ in self._predictions) / n
        sharpness = sum((p - mean_pred) ** 2 for p, _ in self._predictions) / n

        # Reliability diagram: bin predictions by confidence
        bin_width = 1.0 / self._n_bins
        bins: list[CalibrationBin] = []
        total_gap_weighted = 0.0

        for i in range(self._n_bins):
            bin_start = i * bin_width
            bin_end = (i + 1) * bin_width

            in_bin = [
                (p, o)
                for p, o in self._predictions
                if bin_start <= p < bin_end or (i == self._n_bins - 1 and p == 1.0)
            ]

            if not in_bin:
                continue

            pred_mean = sum(p for p, _ in in_bin) / len(in_bin)
            obs_freq = sum(1 for _, o in in_bin if o) / len(in_bin)
            gap = abs(pred_mean - obs_freq)

            bins.append(
                CalibrationBin(
                    bin_start=round(bin_start, 2),
                    bin_end=round(bin_end, 2),
                    predicted_mean=round(pred_mean, 4),
                    observed_frequency=round(obs_freq, 4),
                    count=len(in_bin),
                    gap=round(gap, 4),
                )
            )

            total_gap_weighted += gap * len(in_bin)

        ece = total_gap_weighted / n if n > 0 else 0.0

        # Overconfidence: predicted mean > observed mean
        overall_predicted = mean_pred
        overall_observed = sum(1 for _, o in self._predictions if o) / n
        overconfident = overall_predicted > overall_observed

        return CalibrationReport(
            brier_score=round(brier, 4),
            calibration_error=round(ece, 4),
            sharpness=round(sharpness, 4),
            bins=bins,
            n_predictions=n,
            overconfident=overconfident,
        )

    def to_pairs(self) -> list[tuple[float, bool]]:
        """Export all prediction-outcome pairs (for DB persistence)."""
        return list(self._predictions)
