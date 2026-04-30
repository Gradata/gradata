"""
Rule scoring helpers — difficulty, reliability, scope weighting, transfer scope.
=================================================================================
Pure functions; no I/O, no external state.  All helpers used by the core engine
to rank and filter lessons before injection.
"""

from __future__ import annotations
import logging

import json

from gradata._scope import RuleScope, scope_matches
from gradata._types import CorrectionType, Lesson, LessonState, RuleTransferScope
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State Priority
# ---------------------------------------------------------------------------

# Higher value -> higher rank.  Only PATTERN and RULE are surfaced.
_STATE_PRIORITY: dict[LessonState, int] = {
    LessonState.RULE: 2,
    LessonState.PATTERN: 1,
    LessonState.INSTINCT: 0,
    LessonState.UNTESTABLE: -1,
}

# Preference rules get boosted relevance; domain rules slightly penalized (context-specific)
_CT_BOOST: dict[CorrectionType, float] = {
    CorrectionType.PREFERENCE: 1.3,
    CorrectionType.BEHAVIORAL: 1.1,
    CorrectionType.DOMAIN: 0.9,
}


# ---------------------------------------------------------------------------
# Task-type detection keywords (for scope-weighted matching)
# ---------------------------------------------------------------------------

_TASK_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("email", ["email", "draft", "compose", "reply", "follow-up", "followup", "subject line"]),
    ("demo_prep", ["demo", "demo prep", "presentation", "deck", "slide"]),
    ("code", ["code", "implement", "refactor", "debug", "fix bug", "test", "function"]),
    ("prospecting", ["prospect", "lead", "enrich", "icp", "outreach", "campaign"]),
    ("research", ["research", "analyze", "investigate", "compare", "evaluate"]),
    ("call", ["call", "meeting", "agenda", "talking points"]),
    ("document", ["document", "readme", "spec", "guide", "report", "write up"]),
]


# ---------------------------------------------------------------------------
# Transfer Scope Classification
# ---------------------------------------------------------------------------

# Keywords signaling universal scope (AI quality issues, not personal style)
_UNIVERSAL_SIGNALS: list[str] = [
    "em dash",
    "em dashes",
    "verify",
    "verification",
    "fabricat",
    "hallucin",
    "bold mid-paragraph",
    "rule of three",
    "promotional language",
    "never skip",
    "don't assume",
    "never assume",
    "check before",
    "verify before",
    "superficial analysis",
]

# Keywords signaling team/org scope (tool or company specific).
# Override via brain config to add your team's tooling keywords.
_TEAM_SIGNALS: list[str] = [
    "brain/",
    ".carl/",
    "domain/",
]


def classify_transfer_scope(rule_text: str) -> RuleTransferScope:
    """Auto-classify a rule's transfer scope based on content.

    Scans the rule text for known signal keywords:
      - Universal signals (AI tells, data integrity) -> UNIVERSAL
      - Team signals (tool/vendor/company specific) -> TEAM
      - Otherwise -> PERSONAL (conservative default)

    Args:
        rule_text: The rule description or principle text.

    Returns:
        The inferred :class:`RuleTransferScope`.
    """
    lower = rule_text.lower()

    # Check universal signals first (AI quality > team tooling)
    for signal in _UNIVERSAL_SIGNALS:
        if signal in lower:
            return RuleTransferScope.UNIVERSAL

    # Check team signals
    for signal in _TEAM_SIGNALS:
        if signal in lower:
            return RuleTransferScope.TEAM

    return RuleTransferScope.PERSONAL


# ---------------------------------------------------------------------------
# Difficulty Tracking
# ---------------------------------------------------------------------------


def compute_rule_difficulty(
    rule_category: str,
    events: list[dict[str, str]],
) -> float:
    """Compute difficulty score for a rule category from event history.

    Difficulty = violations / (violations + successes). A higher score means
    the rule is harder to follow and should get priority during selection.

    Args:
        rule_category: The lesson category to evaluate (e.g. "DRAFTING").
        events: List of event dicts, each with at least ``"category"`` and
            ``"type"`` keys. Type should be ``"violation"`` or ``"success"``.

    Returns:
        Float in [0.0, 1.0]. Returns 0.5 (neutral) when there are no
        matching events, to avoid penalizing rules with no history.
    """
    violations = 0
    successes = 0
    for event in events:
        if event.get("category", "").upper() != rule_category.upper():
            continue
        event_type = event.get("type", "").lower()
        if event_type == "violation":
            violations += 1
        elif event_type == "success":
            successes += 1

    total = violations + successes
    if total == 0:
        return 0.5  # neutral prior when no data
    return violations / total


def _difficulty_from_lesson(lesson: Lesson) -> float:
    """Derive a difficulty proxy from a lesson's own counters.

    Uses misfire_count as a proxy for violations and fire_count as total
    applications. Higher misfire ratio means the rule is harder.

    Returns:
        Float in [0.0, 1.0]. 0.5 if no application history.
    """
    total = lesson.fire_count + lesson.misfire_count
    if total == 0:
        return 0.5
    return lesson.misfire_count / total


# ---------------------------------------------------------------------------
# Task-type Detection
# ---------------------------------------------------------------------------


def detect_task_type(user_message: str) -> str:
    """Detect the task type from a user message using keyword matching.

    Scans the message for known task-type keywords and returns the first
    match. Used to build a more precise RuleScope for rule selection.

    Args:
        user_message: The raw user prompt or message text.

    Returns:
        Detected task type string (e.g. "email", "code", "demo_prep"),
        or empty string if no match.
    """
    normalised = user_message.lower()
    for task_type, keywords in _TASK_TYPE_PATTERNS:
        if any(kw in normalised for kw in keywords):
            return task_type
    return ""


def compute_scope_weight(
    rule_scope: RuleScope,
    query_scope: RuleScope,
) -> float:
    """Weight a scope match with bonus for exact task_type alignment.

    Scoring tiers:
      - Exact task_type match: base score * 1.5 (capped at 1.0)
      - Partial match (same domain but different task_type): base score * 1.0
      - Wildcard rule (no task_type set): base score * 0.8

    This ensures rules scoped to the exact task type beat generic rules,
    which in turn beat mismatched rules.

    Args:
        rule_scope: The scope attached to a stored rule.
        query_scope: The scope inferred from the current session context.

    Returns:
        Weighted float in [0.0, 1.0].
    """
    base = scope_matches(rule_scope, query_scope)
    if base <= 0.0:
        return 0.0

    rule_tt = rule_scope.task_type
    query_tt = query_scope.task_type

    if rule_tt and query_tt and rule_tt == query_tt:
        # Exact match bonus
        return min(1.0, base * 1.5)
    elif not rule_tt:
        # Wildcard: slightly penalise generic rules
        return base * 0.8
    else:
        # Partial or mismatch: use base score
        return base


# ---------------------------------------------------------------------------
# Beta Distribution / Domain Reliability
# ---------------------------------------------------------------------------


def _beta_ppf_05(alpha: float, beta_param: float) -> float:
    """5th percentile of Beta(alpha, beta) distribution.

    Uses scipy.stats.beta.ppf when available (exact). Falls back to the
    normal approximation otherwise. The normal approx is biased for
    small samples (α+β < 10), precisely the regime ~40% of PATTERN-tier
    rules sit in — prefer scipy when present.
    """
    if alpha <= 0 or beta_param <= 0:
        return 0.0

    try:
        from scipy.stats import beta as _scipy_beta

        return max(0.0, min(1.0, float(_scipy_beta.ppf(0.05, alpha, beta_param))))
    except ImportError:
        pass

    import math

    total = alpha + beta_param
    mean = alpha / total
    if total <= 2:
        return max(0.0, mean - 0.3)
    variance = (alpha * beta_param) / (total * total * (total + 1))
    std = math.sqrt(variance)
    return max(0.0, min(1.0, mean - 1.645 * std))


def beta_domain_reliability(fires: int, misfires: int) -> float:
    """Domain reliability via Beta distribution lower bound.

    fires = total activations in this domain (includes misfires).
    misfires = activations that made output worse (subset of fires).
    successes = fires - misfires = activations that helped or were neutral.

    Returns 5th percentile of Beta(successes+1, misfires+1).
    No data (0,0) returns 1.0 (neutral — no penalty).
    """
    if fires == 0 and misfires == 0:
        return 1.0
    misfires = min(misfires, fires)  # enforce invariant: misfires <= fires
    successes = fires - misfires
    alpha = max(1, successes + 1)
    beta_param = misfires + 1
    return round(_beta_ppf_05(alpha, beta_param), 4)


def effective_confidence(
    fsrs_confidence: float,
    domain_fires: int,
    domain_misfires: int,
) -> float:
    """Unified confidence = FSRS global * Beta domain reliability.

    FSRS handles global graduation curve. Beta handles per-domain
    reliability. No double-counting.
    """
    reliability = beta_domain_reliability(domain_fires, domain_misfires)
    return round(fsrs_confidence * reliability, 4)


def is_rule_disabled_for_domain(lesson: Lesson, domain: str) -> bool:
    """Check if a rule should be suppressed in a specific domain.

    Uses Beta distribution 5th-percentile lower bound on the success rate.
    Disabled when the lower bound falls below 0.5 — i.e., we're 95%
    confident the success rate is below 50% (misfire rate above 50%).
    """
    scores = lesson.domain_scores.get(domain, {})
    fires = scores.get("fires", 0)
    misfires = scores.get("misfires", 0)
    if fires < 3:
        return False
    reliability = beta_domain_reliability(fires, misfires)
    return reliability < 0.5


# ---------------------------------------------------------------------------
# Assumption Invalidation
# ---------------------------------------------------------------------------


def validate_assumptions(
    lesson: Lesson,
    context: dict,
) -> tuple[bool, str]:
    """Check if a rule's dynamic runtime assumptions still hold.

    Unlike :func:`~gradata.enhancements.meta_rules.evaluate_conditions`
    (which checks static preconditions on meta-rules), this validates
    *runtime* state that can change mid-session:

    (a) Confidence hasn't decayed below the eligibility threshold for
        the lesson's current state.
    (b) The lesson's category hasn't been contradicted this session
        (indicated by ``"contradicted_categories"`` in *context*).
    (c) The lesson's scope matches the current task type (if one is
        active in *context*).

    Args:
        lesson: The lesson to validate.
        context: Runtime context dict. Recognised keys:

            - ``"contradicted_categories"`` — set or list of category
              strings that received contradicting corrections this session.
            - ``"current_task_type"`` — the active task type string
              (e.g. ``"email"``, ``"code"``).

    Returns:
        ``(True, "")`` if all assumptions hold, otherwise
        ``(False, reason)`` explaining which check failed.
    """
    # (a) Confidence floor: PATTERN >= 0.60, RULE >= 0.90
    min_conf = {LessonState.RULE: 0.90, LessonState.PATTERN: 0.60}
    floor = min_conf.get(lesson.state, 0.0)
    if lesson.confidence < floor:
        return (
            False,
            f"confidence {lesson.confidence:.2f} below {lesson.state.value} floor {floor:.2f}",
        )

    # (b) Category contradiction
    contradicted = context.get("contradicted_categories", set())
    if lesson.category.upper() in {c.upper() for c in contradicted}:
        return (
            False,
            f"category {lesson.category} contradicted this session",
        )

    # (c) Scope / task-type mismatch
    current_tt = context.get("current_task_type", "")
    if current_tt and lesson.scope_json:
        try:
            scope_dict = json.loads(lesson.scope_json)
            rule_tt = scope_dict.get("task_type", "")
            if rule_tt and rule_tt != current_tt:
                return (
                    False,
                    f"rule scoped to '{rule_tt}' but current task is '{current_tt}'",
                )
        except Exception:
            logger.warning('Suppressed exception in validate_assumptions', exc_info=True)

    return (True, "")
