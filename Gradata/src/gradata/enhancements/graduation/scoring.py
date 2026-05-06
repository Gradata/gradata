"""Opt-in alternate graduation scoring engine.

This module is not the canonical production ``graduate()`` pipeline. The live
lesson engine remains ``gradata.enhancements.self_improvement.graduate``; this
file exists for direct callers and explicit opt-in scoring experiments.

Meta-Harness C — agent-rewritten graduation scoring.

Replaces the hand-tuned three-way guard in the graduation pipeline
(``confidence >= THRESHOLD and fire_count >= MIN_APPLICATIONS``) with a
single blended score that also factors in failure rate, recency, maturity,
and severity-weighted correction signal.

The existing hand-tuned guard is preserved as a fall-back; this module is
opt-in via the ``GRADATA_AGENT_SCORING`` environment variable or by direct
import from application code. Tests cover both paths so the switch can be
flipped per-brain without touching call sites.

Design
------
Score lives on [0, 1]. Composition (weights sum to 1.0)::

    score =  0.35 * confidence_component
           + 0.25 * fire_component          # diminishing-returns sqrt
           + 0.20 * reliability_component   # 1 - clamp(failure_rate)
           + 0.10 * recency_component       # exp decay on sessions_since_fire
           + 0.10 * maturity_component      # saturating curve on total fires

Target state is derived from the score: ``< 0.45`` → stay, ``>= 0.45`` →
PATTERN, ``>= 0.80`` → RULE. Those thresholds are deliberately broader than
the hand-tuned constants so the score's *shape* — not a single ratchet —
controls promotion.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field


@dataclass
class GraduationFeatures:
    """Inputs to the scoring function. All fields have sane defaults."""

    confidence: float = 0.0
    fire_count: int = 0
    failure_count: int = 0
    sessions_since_fire: int = 0
    total_sessions_observed: int = 0
    severity_weighted_signal: float = 0.0  # 0..1 — from correction severity
    current_state: str = "INSTINCT"  # INSTINCT | PATTERN | RULE

    @property
    def failure_rate(self) -> float:
        denom = max(self.fire_count, 1)
        return min(1.0, self.failure_count / denom)


@dataclass
class GraduationScore:
    """Output. Score + recommended target state + component breakdown."""

    score: float
    target_state: str
    components: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


# ── Component weights (sum = 1.0) ────────────────────────────────────────────

_W_CONFIDENCE = 0.35
_W_FIRE = 0.25
_W_RELIABILITY = 0.20
_W_RECENCY = 0.10
_W_MATURITY = 0.10

# Target-state cut-points on the blended score.
PATTERN_SCORE_CUT = 0.45
RULE_SCORE_CUT = 0.80

# Shape parameters.
_FIRE_SATURATION = 8.0  # fire_count at which fire_component ≈ 0.9
_RECENCY_HALF_LIFE = 10.0  # sessions_since_fire for 50% recency weight
_MATURITY_SATURATION = 20.0  # total_sessions_observed for 0.9 maturity


def _fire_component(fire_count: int) -> float:
    if fire_count <= 0:
        return 0.0
    return min(1.0, math.sqrt(fire_count / _FIRE_SATURATION))


def _reliability_component(failure_rate: float) -> float:
    return max(0.0, 1.0 - failure_rate)


def _recency_component(sessions_since_fire: int) -> float:
    if sessions_since_fire <= 0:
        return 1.0
    return math.exp(-math.log(2) * sessions_since_fire / _RECENCY_HALF_LIFE)


def _maturity_component(total_sessions: int) -> float:
    if total_sessions <= 0:
        return 0.0
    return 1.0 - math.exp(-total_sessions / _MATURITY_SATURATION)


def compute_graduation_score(features: GraduationFeatures) -> GraduationScore:
    """Pure function: features → blended score and target state.

    All inputs default to zero, so a never-observed lesson scores 0 and stays
    at INSTINCT.
    """
    confidence = max(0.0, min(1.0, features.confidence))
    c_confidence = confidence
    c_fire = _fire_component(features.fire_count)
    c_reliability = _reliability_component(features.failure_rate)
    c_recency = _recency_component(features.sessions_since_fire)
    c_maturity = _maturity_component(features.total_sessions_observed)

    # Severity signal nudges the confidence component up within its weight.
    severity = max(0.0, min(1.0, features.severity_weighted_signal))
    c_confidence = min(1.0, c_confidence + 0.10 * severity)

    raw_score = (
        _W_CONFIDENCE * c_confidence
        + _W_FIRE * c_fire
        + _W_RELIABILITY * c_reliability
        + _W_RECENCY * c_recency
        + _W_MATURITY * c_maturity
    )
    # Reliability also acts as a multiplicative veto: a rule failing 80%
    # of the time shouldn't promote even when every other signal is strong.
    # sqrt keeps the penalty gentle at small failure rates.
    score = raw_score * math.sqrt(c_reliability)
    score = round(max(0.0, min(1.0, score)), 4)

    if score >= RULE_SCORE_CUT:
        target = "RULE"
    elif score >= PATTERN_SCORE_CUT:
        target = "PATTERN"
    else:
        target = features.current_state if features.current_state != "INSTINCT" else "INSTINCT"
        # If current is PATTERN and score fell below cut, recommend staying
        # at PATTERN (demotion is a separate concern handled by judgment_decay).
        if features.current_state == "RULE" and score < PATTERN_SCORE_CUT:
            target = "PATTERN"

    reasons: list[str] = []
    if c_reliability < 0.70:
        reasons.append(f"high failure_rate={features.failure_rate:.2f}")
    if c_recency < 0.50:
        reasons.append(f"stale (sessions_since_fire={features.sessions_since_fire})")
    if features.fire_count < 2:
        reasons.append(f"low fire_count={features.fire_count}")

    return GraduationScore(
        score=score,
        target_state=target,
        components={
            "confidence": round(c_confidence, 4),
            "fire": round(c_fire, 4),
            "reliability": round(c_reliability, 4),
            "recency": round(c_recency, 4),
            "maturity": round(c_maturity, 4),
        },
        reasons=reasons,
    )


def should_graduate_lesson(
    lesson,
    *,
    failure_count: int = 0,
    sessions_since_fire: int = 0,
    total_sessions_observed: int = 0,
    severity_weighted_signal: float = 0.0,
) -> tuple[bool, str, GraduationScore]:
    """Convenience wrapper for the pipeline.

    Returns ``(should_transition, target_state, score)`` where
    ``should_transition`` is True iff the target state differs from the
    lesson's current state. Callers retain control over whether to actually
    apply the transition.
    """
    state_name = getattr(getattr(lesson, "state", None), "name", "INSTINCT")
    features = GraduationFeatures(
        confidence=float(getattr(lesson, "confidence", 0.0) or 0.0),
        fire_count=int(getattr(lesson, "fire_count", 0) or 0),
        failure_count=failure_count,
        sessions_since_fire=sessions_since_fire,
        total_sessions_observed=total_sessions_observed,
        severity_weighted_signal=severity_weighted_signal,
        current_state=state_name,
    )
    score = compute_graduation_score(features)
    return (score.target_state != state_name, score.target_state, score)


def scoring_enabled() -> bool:
    """Opt-in switch: truthy ``GRADATA_AGENT_SCORING`` env var activates."""
    return os.environ.get("GRADATA_AGENT_SCORING", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
