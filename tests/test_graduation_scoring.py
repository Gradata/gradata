"""Tests for Meta-Harness C graduation scoring (opt-in alternative to
hand-tuned thresholds)."""
from __future__ import annotations

import os

from gradata._types import Lesson, LessonState
from gradata.enhancements.graduation.scoring import (
    PATTERN_SCORE_CUT,
    RULE_SCORE_CUT,
    GraduationFeatures,
    compute_graduation_score,
    scoring_enabled,
    should_graduate_lesson,
)


def test_zero_features_stays_instinct():
    score = compute_graduation_score(GraduationFeatures())
    assert score.target_state == "INSTINCT"
    assert score.score < PATTERN_SCORE_CUT


def test_strong_features_promote_to_rule():
    features = GraduationFeatures(
        confidence=0.95,
        fire_count=10,
        failure_count=0,
        sessions_since_fire=0,
        total_sessions_observed=30,
        current_state="PATTERN",
    )
    score = compute_graduation_score(features)
    assert score.score >= RULE_SCORE_CUT
    assert score.target_state == "RULE"


def test_moderate_features_promote_to_pattern():
    features = GraduationFeatures(
        confidence=0.70,
        fire_count=4,
        failure_count=0,
        sessions_since_fire=2,
        total_sessions_observed=8,
        current_state="INSTINCT",
    )
    score = compute_graduation_score(features)
    assert PATTERN_SCORE_CUT <= score.score < RULE_SCORE_CUT
    assert score.target_state == "PATTERN"


def test_high_failure_rate_blocks_promotion():
    features = GraduationFeatures(
        confidence=0.95,
        fire_count=10,
        failure_count=8,  # 80% failure
        sessions_since_fire=0,
        total_sessions_observed=30,
        current_state="PATTERN",
    )
    score = compute_graduation_score(features)
    assert score.target_state != "RULE"
    assert any("failure_rate" in r for r in score.reasons)


def test_stale_lesson_loses_recency():
    features = GraduationFeatures(
        confidence=0.95,
        fire_count=10,
        sessions_since_fire=100,
        total_sessions_observed=100,
        current_state="PATTERN",
    )
    score = compute_graduation_score(features)
    assert score.components["recency"] < 0.10
    assert any("stale" in r for r in score.reasons)


def test_components_in_unit_range():
    features = GraduationFeatures(
        confidence=1.0, fire_count=100, failure_count=0,
        sessions_since_fire=0, total_sessions_observed=1000,
    )
    score = compute_graduation_score(features)
    for name, val in score.components.items():
        assert 0.0 <= val <= 1.0, f"{name}={val} out of range"
    assert 0.0 <= score.score <= 1.0


def test_failure_rate_clamps_at_one():
    features = GraduationFeatures(fire_count=2, failure_count=99)
    assert features.failure_rate == 1.0


def test_severity_signal_nudges_confidence():
    base = compute_graduation_score(GraduationFeatures(
        confidence=0.60, fire_count=3, total_sessions_observed=5,
    ))
    boosted = compute_graduation_score(GraduationFeatures(
        confidence=0.60, fire_count=3, total_sessions_observed=5,
        severity_weighted_signal=1.0,
    ))
    assert boosted.score > base.score


def test_should_graduate_lesson_returns_transition_signal():
    lesson = Lesson(
        date="2026-01-01",
        state=LessonState.INSTINCT,
        confidence=0.85,
        category="DRAFTING",
        description="example",
        fire_count=5,
    )
    transition, target, score = should_graduate_lesson(
        lesson, total_sessions_observed=10,
    )
    assert transition is True
    assert target in ("PATTERN", "RULE")
    assert 0.0 <= score.score <= 1.0


def test_should_graduate_lesson_stays_when_weak():
    lesson = Lesson(
        date="2026-01-01",
        state=LessonState.INSTINCT,
        confidence=0.30,
        category="DRAFTING",
        description="example",
        fire_count=0,
    )
    transition, target, _ = should_graduate_lesson(lesson)
    assert transition is False
    assert target == "INSTINCT"


def test_rule_with_low_score_demotes_to_pattern():
    """RULE-state lesson whose score collapsed recommends PATTERN."""
    features = GraduationFeatures(
        confidence=0.40,
        fire_count=2,
        failure_count=1,
        sessions_since_fire=50,
        total_sessions_observed=5,
        current_state="RULE",
    )
    score = compute_graduation_score(features)
    assert score.target_state == "PATTERN"


def test_scoring_enabled_env_switch(monkeypatch):
    monkeypatch.delenv("GRADATA_AGENT_SCORING", raising=False)
    assert scoring_enabled() is False
    monkeypatch.setenv("GRADATA_AGENT_SCORING", "1")
    assert scoring_enabled() is True
    monkeypatch.setenv("GRADATA_AGENT_SCORING", "true")
    assert scoring_enabled() is True
    monkeypatch.setenv("GRADATA_AGENT_SCORING", "")
    assert scoring_enabled() is False
    # Make sure teardown clears
    monkeypatch.delenv("GRADATA_AGENT_SCORING", raising=False)
    _ = os  # keep import-time usage happy
