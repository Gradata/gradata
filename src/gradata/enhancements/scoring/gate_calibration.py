"""Empirical ROC-based threshold tuning for quality gates. Collects human accept/reject truth +
auto scores; once 50+ rated, recommends F1-maximal threshold over the arbitrary 8.0 default."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThresholdCandidate:
    """Analysis of a specific threshold value."""

    threshold: float
    precision: float  # Of those predicted pass, how many were actually accepted?
    recall: float  # Of those actually accepted, how many were predicted pass?
    f1: float  # Harmonic mean of precision and recall
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int


@dataclass
class CalibrationResult:
    """Result of ROC-based threshold optimization."""

    recommended_threshold: float
    f1_at_recommended: float
    current_threshold: float
    current_f1: float
    n_samples: int
    sufficient_data: bool  # True if n_samples >= min_samples
    candidates: list[ThresholdCandidate]
    human_accept_rate: float  # Fraction of outputs the human accepted
    auto_pass_rate: float  # Fraction that pass at current threshold


class GateCalibrator:
    """Collects human ratings vs auto scores to calibrate gate thresholds.

    The gate threshold (currently 8.0) should be set where the automated
    scorer's pass/fail decisions best match the human's accept/reject
    decisions. This module finds that point.
    """

    def __init__(
        self,
        current_threshold: float = 8.0,
        min_samples: int = 50,
        sweep_min: float = 5.0,
        sweep_max: float = 9.5,
        prefer_higher_on_tie: bool = True,
    ) -> None:
        self._current_threshold = current_threshold
        self._min_samples = min_samples
        self._sweep_min = sweep_min
        self._sweep_max = sweep_max
        self._prefer_higher_on_tie = prefer_higher_on_tie
        self._data: list[tuple[float, bool]] = []  # (auto_score, human_accepted)

    def record(self, auto_score: float, human_accepted: bool) -> None:
        """Record a scored output with its human verdict.

        Args:
            auto_score: The automated quality score (0-10).
            human_accepted: True if the human accepted the output as-is
                           or with minor edits. False if rejected/rewritten.
        """
        self._data.append((auto_score, human_accepted))

    def load(self, data: list[tuple[float, bool]]) -> None:
        """Load historical score-verdict pairs."""
        self._data.extend(data)

    @property
    def n_samples(self) -> int:
        return len(self._data)

    def compute_optimal_threshold(self) -> CalibrationResult:
        """Find the threshold that maximizes F1 score.

        Sweeps thresholds from 5.0 to 9.5 in 0.1 increments and computes
        precision, recall, and F1 at each point.
        """
        n = len(self._data)
        sufficient = n >= self._min_samples

        if n == 0:
            return CalibrationResult(
                recommended_threshold=self._current_threshold,
                f1_at_recommended=0.0,
                current_threshold=self._current_threshold,
                current_f1=0.0,
                n_samples=0,
                sufficient_data=False,
                candidates=[],
                human_accept_rate=0.0,
                auto_pass_rate=0.0,
            )

        human_accepted = sum(1 for _, h in self._data if h)
        human_accept_rate = human_accepted / n

        candidates: list[ThresholdCandidate] = []
        best_f1 = 0.0
        best_threshold = self._current_threshold
        current_f1 = 0.0

        # Sweep thresholds (configurable range)
        sweep_start = int(self._sweep_min * 10)
        sweep_end = int(self._sweep_max * 10) + 1
        for t_int in range(sweep_start, sweep_end):
            t = t_int / 10.0
            candidate = self._evaluate_threshold(t)
            candidates.append(candidate)

            # On tie: prefer higher threshold (fewer false positives)
            if candidate.f1 > best_f1 or (
                candidate.f1 == best_f1 and self._prefer_higher_on_tie and t > best_threshold
            ):
                best_f1 = candidate.f1
                best_threshold = t

            if abs(t - self._current_threshold) < 0.05:
                current_f1 = candidate.f1

        auto_pass = sum(1 for s, _ in self._data if s >= self._current_threshold)
        auto_pass_rate = auto_pass / n

        return CalibrationResult(
            recommended_threshold=round(best_threshold, 1),
            f1_at_recommended=round(best_f1, 4),
            current_threshold=self._current_threshold,
            current_f1=round(current_f1, 4),
            n_samples=n,
            sufficient_data=sufficient,
            candidates=candidates,
            human_accept_rate=round(human_accept_rate, 4),
            auto_pass_rate=round(auto_pass_rate, 4),
        )

    def _evaluate_threshold(self, threshold: float) -> ThresholdCandidate:
        """Compute precision/recall/F1 at a specific threshold."""
        tp = fp = tn = fn = 0

        for score, accepted in self._data:
            predicted_pass = score >= threshold
            if predicted_pass and accepted:
                tp += 1
            elif predicted_pass and not accepted:
                fp += 1
            elif not predicted_pass and accepted:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return ThresholdCandidate(
            threshold=round(threshold, 1),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
        )

    def to_pairs(self) -> list[tuple[float, bool]]:
        """Export data for DB persistence."""
        return list(self._data)
