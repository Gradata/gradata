"""Tests for Bayesian Beta domain scoring — unified with FSRS."""
from __future__ import annotations

from gradata._types import Lesson, LessonState
from gradata.rules.rule_engine import (
    beta_domain_reliability,
    is_rule_disabled_for_domain,
    effective_confidence,
)


def test_beta_reliability_high_success():
    # Beta(20, 2) exact 5th percentile ≈ 0.793. The previous assertion
    # of > 0.8 measured the bias of the normal approximation, not the
    # statistic itself. Scipy-backed PPF closes that bias.
    score = beta_domain_reliability(fires=20, misfires=1)
    assert score > 0.75


def test_beta_reliability_uncertain_with_few_observations():
    score = beta_domain_reliability(fires=2, misfires=1)
    assert score < 0.5


def test_beta_reliability_no_data():
    score = beta_domain_reliability(fires=0, misfires=0)
    assert score == 1.0


def test_beta_reliability_all_misfires():
    score = beta_domain_reliability(fires=10, misfires=10)
    assert score < 0.15


def test_disabled_uses_beta_not_naive_ratio():
    """2 fires, 1 misfire (50% ratio) should NOT disable — too few observations."""
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 2, "misfires": 1}},
    )
    assert is_rule_disabled_for_domain(lesson, "CODE") is False


def test_disabled_with_strong_evidence():
    """20 fires, 10 misfires (50%) — enough evidence, should disable."""
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 20, "misfires": 10}},
    )
    assert is_rule_disabled_for_domain(lesson, "CODE") is True


def test_effective_confidence_multiplies():
    score = effective_confidence(fsrs_confidence=0.92, domain_fires=20, domain_misfires=1)
    assert 0.7 < score < 0.95


def test_effective_confidence_bad_domain():
    score = effective_confidence(fsrs_confidence=0.92, domain_fires=10, domain_misfires=5)
    assert score < 0.6


def test_effective_confidence_no_domain_data():
    score = effective_confidence(fsrs_confidence=0.92, domain_fires=0, domain_misfires=0)
    assert score == 0.92
