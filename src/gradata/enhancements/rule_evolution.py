"""
Rule Evolution — A/B testing + conflict detection for rule lifecycle.
=====================================================================
Merged from: rule_ab_testing.py + rule_conflicts.py (S79 consolidation)

Two concerns:
  1. A/B Testing: Statistical comparison of rule variants with Wilson scores.
  2. Conflict Detection: Updates/Extends/Derives relationship classification.

Usage::

    from gradata.enhancements.rule_evolution import (
        RuleExperiment, ExperimentResult, wilson_score_interval,
        detect_rule_conflict, RuleRelation, classify_all_relations,
    )
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from gradata._types import ELIGIBLE_STATES, Lesson
from gradata.enhancements.diff_engine import compute_diff

__all__ = [
    "ExperimentManager",
    "ExperimentResult",
    "RuleExperiment",
    # Conflict Detection
    "RuleRelation",
    "classify_all_relations",
    "detect_rule_conflict",
    # A/B Testing
    "wilson_score_interval",
]


# ═══════════════════════════════════════════════════════════════════════
# A/B Testing (Wilson Score Confidence Intervals)
# ═══════════════════════════════════════════════════════════════════════


def wilson_score_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Compute Wilson score confidence interval for small samples."""
    if trials == 0:
        return (0.0, 0.0)
    p_hat = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    center = (p_hat + z2 / (2 * trials)) / denominator
    spread = (z / denominator) * math.sqrt((p_hat * (1 - p_hat) + z2 / (4 * trials)) / trials)
    return (round(max(0.0, center - spread), 4), round(min(1.0, center + spread), 4))


@dataclass
class ExperimentResult:
    """Result of evaluating an A/B experiment."""
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
    """A/B test between two rule variants."""
    experiment_id: str
    variant_a: str
    variant_b: str
    category: str = ""
    min_trials: int = 20
    min_margin: float = 0.10
    _a_successes: int = 0
    _a_trials: int = 0
    _b_successes: int = 0
    _b_trials: int = 0

    def assign(self) -> str:
        return random.choice(["a", "b"])

    def record(self, variant: str, success: bool) -> None:
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
        a_rate = self._a_successes / self._a_trials if self._a_trials else 0.0
        b_rate = self._b_successes / self._b_trials if self._b_trials else 0.0
        a_interval = wilson_score_interval(self._a_successes, self._a_trials)
        b_interval = wilson_score_interval(self._b_successes, self._b_trials)
        sufficient = self._a_trials >= self.min_trials and self._b_trials >= self.min_trials
        margin = abs(a_rate - b_rate)
        winner = None
        confidence = 0.0
        if sufficient and margin >= self.min_margin:
            if a_interval[0] > b_interval[1]:
                winner = "a"
                confidence = min(1.0, margin / 0.5)
            elif b_interval[0] > a_interval[1]:
                winner = "b"
                confidence = min(1.0, margin / 0.5)
            elif margin >= self.min_margin * 2:
                winner = "a" if a_rate > b_rate else "b"
                confidence = min(1.0, margin / 0.5) * 0.7
        return ExperimentResult(
            winner=winner, confidence=round(confidence, 4),
            a_success_rate=round(a_rate, 4), b_success_rate=round(b_rate, 4),
            a_interval=a_interval, b_interval=b_interval,
            a_trials=self._a_trials, b_trials=self._b_trials,
            sufficient_data=sufficient, margin=round(margin, 4),
        )

    @property
    def total_trials(self) -> int:
        return self._a_trials + self._b_trials

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id, "variant_a": self.variant_a,
            "variant_b": self.variant_b, "category": self.category,
            "a_successes": self._a_successes, "a_trials": self._a_trials,
            "b_successes": self._b_successes, "b_trials": self._b_trials,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuleExperiment:
        exp = cls(experiment_id=data["experiment_id"], variant_a=data["variant_a"],
                  variant_b=data["variant_b"], category=data.get("category", ""))
        exp._a_successes = data.get("a_successes", 0)
        exp._a_trials = data.get("a_trials", 0)
        exp._b_successes = data.get("b_successes", 0)
        exp._b_trials = data.get("b_trials", 0)
        return exp


class ExperimentManager:
    """Manages multiple concurrent A/B experiments."""

    def __init__(self) -> None:
        self._experiments: dict[str, RuleExperiment] = {}
        self._completed: list[dict[str, Any]] = []

    def create(self, experiment_id: str, variant_a: str, variant_b: str, category: str = "") -> RuleExperiment:
        exp = RuleExperiment(experiment_id=experiment_id, variant_a=variant_a, variant_b=variant_b, category=category)
        self._experiments[experiment_id] = exp
        return exp

    def get(self, experiment_id: str) -> RuleExperiment | None:
        return self._experiments.get(experiment_id)

    def evaluate_all(self) -> list[ExperimentResult]:
        results = []
        completed_ids = []
        for exp_id, exp in self._experiments.items():
            result = exp.evaluate()
            results.append(result)
            if result.is_conclusive:
                self._completed.append({
                    "experiment": exp.to_dict(),
                    "result": {"winner": result.winner, "confidence": result.confidence, "margin": result.margin},
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


# ═══════════════════════════════════════════════════════════════════════
# Conflict Detection (Updates/Extends/Derives relationships)
# ═══════════════════════════════════════════════════════════════════════


class RuleRelation(Enum):
    UPDATES = "updates"
    EXTENDS = "extends"
    DERIVES = "derives"
    INDEPENDENT = "independent"


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a.strip().lower() == b.strip().lower():
        return 1.0
    diff = compute_diff(a, b)
    return round(1.0 - diff.edit_distance, 4)


def _extract_keywords(text: str) -> set[str]:
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "it", "its",
        "this", "that", "and", "but", "or", "not", "no", "if", "then",
        "when", "so", "than", "too", "very", "just", "also", "all",
        "each", "every", "any", "some", "only", "i", "we", "you",
        "they", "he", "she", "my", "your", "our", "their",
    }
    words = set(re.sub(r"[^\w\s]", " ", text.lower()).split())
    return words - stopwords


def _detect_opposite_direction(a_desc: str, b_desc: str) -> bool:
    a_lower = a_desc.lower()
    b_lower = b_desc.lower()
    opposites = [
        ("use", "avoid"), ("use", "don't use"), ("use", "do not use"),
        ("include", "exclude"), ("include", "remove"), ("include", "omit"),
        ("add", "remove"), ("add", "don't add"), ("add", "do not add"),
        ("always", "never"), ("must", "must not"), ("keep", "remove"),
        ("prefer", "avoid"), ("enable", "disable"),
        ("before", "after"), ("first", "last"),
    ]
    for pos, neg in opposites:
        if (pos in a_lower and neg in b_lower) or (neg in a_lower and pos in b_lower):
            return True
    return False


def detect_rule_conflict(
    new_lesson: Lesson, existing_rules: list[Lesson], *,
    update_threshold: float = 0.80, extend_threshold: float = 0.60,
    derive_min_cluster: int = 3,
) -> tuple[RuleRelation, Lesson | None]:
    if not existing_rules:
        return (RuleRelation.INDEPENDENT, None)
    new_desc = new_lesson.description
    new_keywords = _extract_keywords(new_desc)
    best_similarity = 0.0
    best_rule: Lesson | None = None
    category_cluster: list[Lesson] = []
    for rule in existing_rules:
        if rule.state not in ELIGIBLE_STATES:
            continue
        similarity = _text_similarity(new_desc, rule.description)
        if similarity > best_similarity:
            best_similarity = similarity
            best_rule = rule
        if rule.category == new_lesson.category:
            rule_keywords = _extract_keywords(rule.description)
            if new_keywords & rule_keywords:
                category_cluster.append(rule)
    if best_rule is not None and best_similarity > update_threshold:
        if _detect_opposite_direction(new_desc, best_rule.description):
            return (RuleRelation.UPDATES, best_rule)
    if best_rule is not None and best_similarity > extend_threshold:
        if not _detect_opposite_direction(new_desc, best_rule.description):
            return (RuleRelation.EXTENDS, best_rule)
    if len(category_cluster) >= derive_min_cluster:
        return (RuleRelation.DERIVES, None)
    return (RuleRelation.INDEPENDENT, None)


def classify_all_relations(
    new_lesson: Lesson, existing_rules: list[Lesson],
) -> list[tuple[RuleRelation, Lesson, float]]:
    results: list[tuple[RuleRelation, Lesson, float]] = []
    new_desc = new_lesson.description
    for rule in existing_rules:
        similarity = _text_similarity(new_desc, rule.description)
        if similarity < 0.3:
            continue
        is_opposite = _detect_opposite_direction(new_desc, rule.description)
        if similarity > 0.80 and is_opposite:
            relation = RuleRelation.UPDATES
        elif similarity > 0.60 and not is_opposite:
            relation = RuleRelation.EXTENDS
        else:
            relation = RuleRelation.INDEPENDENT
        results.append((relation, rule, similarity))
    results.sort(key=lambda x: x[2], reverse=True)
    return results