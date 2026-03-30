"""
Rule A/B Testing — Statistical comparison of rule variants.
=============================================================
Inspired by: Jarvis (ethanplusai/jarvis) ab_testing.py

When two rules compete for the same category, A/B tests them with
Wilson score confidence intervals to determine which actually reduces
corrections better. Auto-promotes the winner.

Usage::

    from gradata.enhancements.rule_ab_testing import (
        RuleExperiment, ExperimentResult, wilson_score_interval,
    )

    exp = RuleExperiment(
        experiment_id="tone_v1_vs_v2",
        variant_a="Use casual tone in all emails",
        variant_b="Match the recipient's tone from their last email",
        category="TONE",
    )

    # Record outcomes
    exp.record("a", success=True)
    exp.record("b", success=True)
    exp.record("a", success=False)  # correction happened

    result = exp.evaluate()
    print(result.winner)       # "b" or "a" or None (inconclusive)
    print(result.confidence)   # 0.0-1.0
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "wilson_score_interval",
    "RuleExperiment",
    "ExperimentResult",
    "ExperimentManager",
]


def wilson_score_interval(
    successes: int,
    trials: int,
    z: float = 1.96,
) -> tuple[float, float]:
    """Compute Wilson score confidence interval.

    More robust than simple success/failure ratio, especially for
    small sample sizes. Used in Jarvis's A/B testing.

    Args:
        successes: Number of successful outcomes.
        trials: Total number of trials.
        z: Z-score for confidence level (1.96 = 95%).

    Returns:
        (lower_bound, upper_bound) of the confidence interval.
    """
    if trials == 0:
        return (0.0, 0.0)

    p_hat = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials

    center = (p_hat + z2 / (2 * trials)) / denominator
    spread = (z / denominator) * math.sqrt(
        (p_hat * (1 - p_hat) + z2 / (4 * trials)) / trials
    )

    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)

    return (round(lower, 4), round(upper, 4))


@dataclass
class ExperimentResult:
    """Result of evaluating an A/B experiment.

    Attributes:
        winner: "a", "b", or None if inconclusive.
        confidence: How confident we are in the winner (0-1).
        a_success_rate: Success rate of variant A.
        b_success_rate: Success rate of variant B.
        a_interval: Wilson confidence interval for A.
        b_interval: Wilson confidence interval for B.
        a_trials: Total trials for A.
        b_trials: Total trials for B.
        sufficient_data: Whether we have enough data to decide.
        margin: Gap between success rates.
    """
    winner: str | None = None
    confidence: float = 0.0
    a_success_rate: float = 0.0
    b_success_rate: float = 0.0
    a_interval: tuple[float, float] = (0.0, 0.0)
    b_interval: tuple[float, float] = (0.0, 0.0)
    a_trials: int = 0
    b_trials: int = 0
    sufficient_data: bool = False
    margin: float = 0.0

    @property
    def is_conclusive(self) -> bool:
        return self.winner is not None and self.sufficient_data


@dataclass
class RuleExperiment:
    """A/B test between two rule variants.

    Attributes:
        experiment_id: Unique identifier.
        variant_a: Description of rule variant A.
        variant_b: Description of rule variant B.
        category: Correction category being tested.
        min_trials: Minimum trials per variant before deciding.
        min_margin: Minimum success rate gap to declare a winner.
    """
    experiment_id: str
    variant_a: str
    variant_b: str
    category: str = ""
    min_trials: int = 20
    min_margin: float = 0.10
    # Internal state
    _a_successes: int = 0
    _a_trials: int = 0
    _b_successes: int = 0
    _b_trials: int = 0

    def assign(self) -> str:
        """Randomly assign to variant A or B.

        Uses simple random assignment. Returns "a" or "b".
        """
        return random.choice(["a", "b"])

    def record(self, variant: str, success: bool) -> None:
        """Record an outcome for a variant.

        Args:
            variant: "a" or "b".
            success: True if no correction was needed (rule worked).

        Raises:
            ValueError: If variant is not "a" or "b".
        """
        if variant == "a":
            self._a_trials += 1
            if success:
                self._a_successes += 1
        elif variant == "b":
            self._b_trials += 1
            if success:
                self._b_successes += 1
        else:
            raise ValueError(f"variant must be 'a' or 'b', got {variant!r}")

    def evaluate(self) -> ExperimentResult:
        """Evaluate the experiment and determine the winner.

        Uses Wilson confidence intervals. A winner is declared when:
        1. Both variants have at least min_trials
        2. The confidence intervals don't overlap
        3. The margin exceeds min_margin

        Returns:
            ExperimentResult with winner and statistical details.
        """
        a_rate = self._a_successes / self._a_trials if self._a_trials else 0.0
        b_rate = self._b_successes / self._b_trials if self._b_trials else 0.0
        a_interval = wilson_score_interval(self._a_successes, self._a_trials)
        b_interval = wilson_score_interval(self._b_successes, self._b_trials)

        sufficient = (
            self._a_trials >= self.min_trials
            and self._b_trials >= self.min_trials
        )

        margin = abs(a_rate - b_rate)
        winner = None
        confidence = 0.0

        if sufficient and margin >= self.min_margin:
            # Check if intervals don't overlap
            if a_interval[0] > b_interval[1]:
                winner = "a"
                confidence = min(1.0, margin / 0.5)
            elif b_interval[0] > a_interval[1]:
                winner = "b"
                confidence = min(1.0, margin / 0.5)
            else:
                # Intervals overlap but margin exists
                if margin >= self.min_margin * 2:
                    winner = "a" if a_rate > b_rate else "b"
                    confidence = min(1.0, margin / 0.5) * 0.7  # Lower confidence

        return ExperimentResult(
            winner=winner,
            confidence=round(confidence, 4),
            a_success_rate=round(a_rate, 4),
            b_success_rate=round(b_rate, 4),
            a_interval=a_interval,
            b_interval=b_interval,
            a_trials=self._a_trials,
            b_trials=self._b_trials,
            sufficient_data=sufficient,
            margin=round(margin, 4),
        )

    @property
    def total_trials(self) -> int:
        return self._a_trials + self._b_trials

    def to_dict(self) -> dict[str, Any]:
        """Serialize experiment state."""
        return {
            "experiment_id": self.experiment_id,
            "variant_a": self.variant_a,
            "variant_b": self.variant_b,
            "category": self.category,
            "a_successes": self._a_successes,
            "a_trials": self._a_trials,
            "b_successes": self._b_successes,
            "b_trials": self._b_trials,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuleExperiment:
        """Deserialize experiment state."""
        exp = cls(
            experiment_id=data["experiment_id"],
            variant_a=data["variant_a"],
            variant_b=data["variant_b"],
            category=data.get("category", ""),
        )
        exp._a_successes = data.get("a_successes", 0)
        exp._a_trials = data.get("a_trials", 0)
        exp._b_successes = data.get("b_successes", 0)
        exp._b_trials = data.get("b_trials", 0)
        return exp


class ExperimentManager:
    """Manages multiple concurrent A/B experiments.

    Tracks active experiments, auto-promotes winners, and archives
    completed experiments.
    """

    def __init__(self) -> None:
        self._experiments: dict[str, RuleExperiment] = {}
        self._completed: list[dict[str, Any]] = []

    def create(
        self,
        experiment_id: str,
        variant_a: str,
        variant_b: str,
        category: str = "",
    ) -> RuleExperiment:
        """Create a new experiment."""
        exp = RuleExperiment(
            experiment_id=experiment_id,
            variant_a=variant_a,
            variant_b=variant_b,
            category=category,
        )
        self._experiments[experiment_id] = exp
        return exp

    def get(self, experiment_id: str) -> RuleExperiment | None:
        """Get an experiment by ID."""
        return self._experiments.get(experiment_id)

    def evaluate_all(self) -> list[ExperimentResult]:
        """Evaluate all active experiments and archive completed ones."""
        results = []
        completed_ids = []

        for exp_id, exp in self._experiments.items():
            result = exp.evaluate()
            results.append(result)
            if result.is_conclusive:
                self._completed.append({
                    "experiment": exp.to_dict(),
                    "result": {
                        "winner": result.winner,
                        "confidence": result.confidence,
                        "margin": result.margin,
                    },
                })
                completed_ids.append(exp_id)

        for exp_id in completed_ids:
            del self._experiments[exp_id]

        return results

    @property
    def active_count(self) -> int:
        return len(self._experiments)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    def stats(self) -> dict[str, Any]:
        return {
            "active_experiments": self.active_count,
            "completed_experiments": self.completed_count,
            "total_trials": sum(e.total_trials for e in self._experiments.values()),
        }
