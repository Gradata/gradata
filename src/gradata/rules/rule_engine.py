"""
Rule Engine — selects and formats learned rules for prompt injection.
=====================================================================
SDK LAYER: Pure logic, no file I/O.  The caller is responsible for
loading lessons and passing them in; this module only transforms data.

The engine filters a list of :class:`~gradata._types.Lesson`
objects against a :class:`~gradata._scope.RuleScope`, ranks the
survivors by state priority + relevance + confidence, and returns
:class:`AppliedRule` objects ready for prompt injection.

Maturity filter:
  - RULE    -> included (confidence 0.90+, fully trusted)
  - PATTERN -> included (confidence 0.60-0.89, useful signal)
  - INSTINCT  -> excluded (too weak to impose on the LLM)
  - UNTESTABLE -> excluded (can't verify applicability)

Enhancements:
  - Per-rule difficulty tracking via ``compute_rule_difficulty``
  - Primacy/recency positioning in ``format_rules_for_prompt``
  - Task-type detection and weighted scope matching via ``detect_task_type``
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import secrets
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.events_bus import EventBus
    from gradata.rules.rule_graph import RuleGraph

from gradata._scope import RuleScope, scope_matches
from gradata._types import ELIGIBLE_STATES, CorrectionType, Lesson, LessonState, RuleTransferScope
from gradata.security.score_obfuscation import truncate_score

# evaluate_conditions lives in meta_rules.py — not re-exported here
# to avoid circular dependency. Callers should import from meta_rules directly.

_log = logging.getLogger(__name__)


def _tier_label(lesson: Lesson) -> str:
    """Return the display tier for a lesson — state name if available, else confidence bucket."""
    return lesson.state.value if lesson.state else truncate_score(lesson.confidence)


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class AppliedRule:
    """A lesson that has been scored and formatted for prompt injection.

    Attributes:
        rule_id: Stable opaque identifier derived from category and
            description hash, e.g. ``"DRAFTING:0042"``.
        lesson: The source :class:`~gradata._self_improvement.Lesson`.
        relevance: Scope match score in [0.0, 1.0] from
            :func:`~gradata._scope.scope_matches`.
        instruction: Human-readable rule text for direct injection into an
            LLM prompt, e.g.
            ``"[RULE:0.95] DRAFTING: Always include pricing in first email"``.
    """

    rule_id: str
    lesson: Lesson
    relevance: float
    instruction: str


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

_ELIGIBLE_STATES = ELIGIBLE_STATES

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
# Rule ID
# ---------------------------------------------------------------------------


def _make_rule_id(lesson: Lesson) -> str:
    """Derive a stable, opaque rule identifier from a lesson.

    Format: ``"CATEGORY:HHHHHHHH"`` where HHHHHHHH is an 8-char hex
    digest of category+description for global uniqueness.

    Args:
        lesson: Source lesson.

    Returns:
        Rule identifier string.
    """
    digest = hashlib.sha256(f"{lesson.category}:{lesson.description}".encode()).hexdigest()[:8]
    return f"{lesson.category}:{digest}"


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
            pass  # malformed scope_json — don't block on it

    return (True, "")


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------


def filter_by_scope(
    lessons: list[Lesson],
    scope: RuleScope,
    min_relevance: float = 0.3,
) -> list[tuple[Lesson, float]]:
    """Return (lesson, relevance_score) pairs for lessons that pass the scope threshold.

    This is a lower-level function useful for debugging which rules match a
    given context without applying any state filtering or ranking.

    Args:
        lessons: All lessons to evaluate.
        scope: The current task/context scope.
        min_relevance: Minimum score required to include a lesson (default 0.3).

    Returns:
        List of (lesson, relevance) tuples, unordered.  Lessons with a
        relevance score below *min_relevance* are excluded.
    """
    results: list[tuple[Lesson, float]] = []
    for lesson in lessons:
        # RuleScope for the lesson uses None (wildcard) for all fields since
        # Lesson objects don't carry explicit scope metadata yet.  The engine
        # therefore scores every lesson against the query scope using a generic
        # wildcard scope, which returns a score driven purely by what the query
        # provides.  When lessons gain explicit scope metadata in a future
        # iteration, this derivation logic should be updated.
        # Use lesson's stored scope if available, otherwise wildcard
        if lesson.scope_json:
            try:
                scope_dict = json.loads(lesson.scope_json)
                lesson_scope = RuleScope(
                    **{k: v for k, v in scope_dict.items() if k in RuleScope.__dataclass_fields__}
                )
            except Exception:
                lesson_scope = RuleScope()
        else:
            lesson_scope = RuleScope()
        score = scope_matches(lesson_scope, scope)
        if score >= min_relevance:
            results.append((lesson, score))
    return results


def _beta_ppf_05(alpha: float, beta_param: float) -> float:
    """Approximate 5th percentile of Beta(alpha, beta) distribution.

    Uses normal approximation. For tiny samples, returns conservative estimate.
    """
    import math

    if alpha <= 0 or beta_param <= 0:
        return 0.0
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


def apply_rules(
    lessons: list[Lesson],
    scope: RuleScope,
    max_rules: int = 5,
    events: list[dict[str, str]] | None = None,
    user_message: str = "",
    _context: str = "",
    bus: EventBus | None = None,
    graph: RuleGraph | None = None,
    _ctx=None,
) -> list[AppliedRule]:
    """Select and rank lessons relevant to the given scope.

    Pipeline:
        1. Filter to PATTERN and RULE lessons only.
        2. Score each against *scope* via weighted scope matching
           (exact task_type > partial > wildcard).
        3. Drop any with relevance < 0.3.
        4. Compute per-rule difficulty from events or lesson counters.
        5. Sort descending by (state_priority, difficulty, relevance, confidence).
           Harder rules get priority so the LLM focuses on its weak spots.
        6. Return the top *max_rules* as :class:`AppliedRule` objects.

    Args:
        lessons: All active lessons from the self-improvement pipeline.
        scope: Current task context used for relevance scoring.
        max_rules: Maximum number of rules to return (default 10).
        events: Optional event history for difficulty computation. Each
            event should have ``"category"`` and ``"type"`` keys.
        user_message: Optional raw user message for task-type detection.
            When provided, enriches the scope's task_type if not already set.
        context: Optional task-context label (e.g. ``"drafting"``,
            ``"code"``). Reserved for future use with context-dependent
            weighting of meta-rules (see
            :func:`~gradata.enhancements.meta_rules.rank_meta_rules_by_context`).

    Returns:
        Ordered list of :class:`AppliedRule` objects, most relevant first.
        Empty list if no lessons pass the filters.
    """
    events = events or []

    # Enrich scope with detected task type if not already set
    if user_message and not scope.task_type:
        detected_tt = detect_task_type(user_message)
        if detected_tt:
            # RuleScope is frozen, so create a new one with the detected type
            scope = RuleScope(
                domain=scope.domain,
                task_type=detected_tt,
                audience=scope.audience,
                channel=scope.channel,
                stakes=scope.stakes,
            )

    # Step 1 — eligibility gate: prefer RULEs, only include PATTERNs if needed
    rules_only = [lesson for lesson in lessons if lesson.state == LessonState.RULE]
    if len(rules_only) >= max_rules:
        eligible = rules_only
    else:
        eligible = [lesson for lesson in lessons if lesson.state in _ELIGIBLE_STATES]

    # Step 1.5 — domain scoping: filter out rules disabled for current domain
    current_domain = scope.domain.upper() if scope.domain else ""
    if current_domain:
        filtered = []
        for lesson in eligible:
            if is_rule_disabled_for_domain(lesson, current_domain):
                if bus:
                    scores = lesson.domain_scores.get(current_domain, {})
                    bus.emit(
                        "rule_scoped_out",
                        {
                            "lesson_category": lesson.category,
                            "lesson_description": lesson.description[:80],
                            "domain": current_domain,
                            "misfire_rate": scores.get("misfires", 0)
                            / max(1, scores.get("fires", 1)),
                        },
                    )
                from gradata.rules.rule_tracker import log_suppression

                log_suppression(
                    rule_id=_make_rule_id(lesson),
                    reason="domain_disabled",
                    relevance=0.0,
                    ctx=_ctx,
                )
            else:
                filtered.append(lesson)
        eligible = filtered

    # Step 2 & 3 — score with weighted scope matching and threshold
    scored: list[tuple[Lesson, float]] = []
    for lesson in eligible:
        # Use lesson's stored scope if available, otherwise wildcard
        if lesson.scope_json:
            try:
                scope_dict = json.loads(lesson.scope_json)
                lesson_scope = RuleScope(
                    **{k: v for k, v in scope_dict.items() if k in RuleScope.__dataclass_fields__}
                )
            except Exception:
                lesson_scope = RuleScope()
        else:
            lesson_scope = RuleScope()
        # Use weighted scope matching (exact > partial > wildcard)
        relevance = compute_scope_weight(lesson_scope, scope)
        relevance *= _CT_BOOST.get(lesson.correction_type, 1.0)
        if relevance >= 0.3:
            scored.append((lesson, relevance))
        elif _ctx:
            from gradata.rules.rule_tracker import log_suppression

            log_suppression(
                rule_id=_make_rule_id(lesson),
                reason="relevance_threshold",
                relevance=relevance,
                ctx=_ctx,
            )

    # Step 3.5 — assumption invalidation (dynamic runtime checks)
    if _context:
        runtime_ctx = {"current_task_type": scope.task_type}
        # Allow caller to pass contradicted categories via _context as JSON
        try:
            ctx_data = json.loads(_context) if _context.startswith("{") else {}
        except (json.JSONDecodeError, AttributeError):
            ctx_data = {}
        if "contradicted_categories" in ctx_data:
            runtime_ctx["contradicted_categories"] = ctx_data["contradicted_categories"]

        validated: list[tuple[Lesson, float]] = []
        for lesson, relevance in scored:
            valid, reason = validate_assumptions(lesson, runtime_ctx)
            if valid:
                validated.append((lesson, relevance))
            else:
                _log.debug(
                    "Skipping rule %s: assumption invalid — %s",
                    lesson.category,
                    reason,
                )
                if _ctx:
                    from gradata.rules.rule_tracker import log_suppression

                    log_suppression(
                        rule_id=_make_rule_id(lesson),
                        reason="assumption_invalid",
                        relevance=relevance,
                        ctx=_ctx,
                    )
        scored = validated

    # Step 4 — compute difficulty per rule
    # Step 5 — sort: state priority DESC, difficulty DESC, relevance DESC, confidence DESC
    def _effective_conf(lesson: Lesson, domain: str) -> float:
        if not domain:
            return lesson.confidence
        scores = lesson.domain_scores.get(domain, {})
        return effective_confidence(
            lesson.confidence,
            scores.get("fires", 0),
            scores.get("misfires", 0),
        )

    scored.sort(
        key=lambda t: (
            _STATE_PRIORITY[t[0].state],
            # Difficulty: use event history if available, else lesson counters
            compute_rule_difficulty(t[0].category, events)
            if events
            else _difficulty_from_lesson(t[0]),
            t[1],
            _effective_conf(t[0], current_domain),
        ),
        reverse=True,
    )

    # Step 5.5 — conflict filtering: avoid injecting rules with high conflict history
    if graph:
        filtered_scored: list[tuple[Lesson, float]] = []
        selected_ids: set[str] = set()
        for lesson, relevance in scored:
            rule_id = _make_rule_id(lesson)
            # Check if this rule conflicts with any already-selected rule
            dominated = False
            for sel_id in selected_ids:
                if graph.conflict_count(rule_id, sel_id) >= 3:
                    dominated = True
                    break
            if not dominated:
                filtered_scored.append((lesson, relevance))
                selected_ids.add(rule_id)
            elif _ctx:
                from gradata.rules.rule_tracker import log_suppression

                log_suppression(
                    rule_id=rule_id,
                    reason="conflict",
                    relevance=relevance,
                    competing_rule_ids=list(selected_ids),
                    ctx=_ctx,
                )
        scored = filtered_scored

    # Step 6 — assemble AppliedRule objects, capped at max_rules
    applied: list[AppliedRule] = []
    for lesson, relevance in scored[:max_rules]:
        rule_id = _make_rule_id(lesson)
        tier_label = _tier_label(lesson)
        instruction = f"{lesson.category}: {lesson.description}"
        applied.append(
            AppliedRule(
                rule_id=rule_id,
                lesson=lesson,
                relevance=relevance,
                instruction=instruction,
            )
        )

    # Track rule co-occurrence
    if graph and len(applied) > 1:
        rule_ids = [r.rule_id for r in applied]
        graph.add_co_occurrence(rule_ids)

    return applied


def merge_related_rules(rules: list[AppliedRule], min_group_size: int = 2) -> list[AppliedRule]:
    """Merge rules sharing a category into compressed blocks.

    Groups with fewer than *min_group_size* rules stay individual.
    Merged rules use the highest confidence from the group and combine
    descriptions into one compressed instruction, saving tokens.
    """
    by_cat: dict[str, list[AppliedRule]] = defaultdict(list)
    for rule in rules:
        by_cat[rule.lesson.category].append(rule)

    result: list[AppliedRule] = []
    for cat, group in by_cat.items():
        if len(group) < min_group_size:
            result.extend(group)
            continue
        # Merge: combine descriptions, take highest confidence
        best = max(group, key=lambda r: r.lesson.confidence)
        descriptions = [r.lesson.description for r in group]
        merged_desc = ". ".join(d.rstrip(".") for d in descriptions) + "."
        merged_instruction = f"{cat}: {merged_desc}"
        merged_rule = AppliedRule(
            rule_id=f"merged_{cat.lower()}",
            lesson=best.lesson,
            relevance=max(r.relevance for r in group),
            instruction=merged_instruction,
        )
        result.append(merged_rule)
    return result


def format_rules_for_prompt(
    rules: list[AppliedRule],
    merge: bool = True,
    scope_filter: RuleTransferScope | None = None,
    shuffle_seed: int | None = None,
) -> str:
    """Format applied rules into an XML-tagged LLM-injectable block.

    Uses XML tags for unambiguous constraint signaling (Claude best practice).
    Applies primacy/recency positioning: highest-priority rules first,
    brief reminder of the #1 rule at the end.

    If *merge* is True, related rules in the same category are compressed
    into single blocks to save tokens.

    When *scope_filter* is provided, only rules whose lesson's
    ``transfer_scope`` matches are included. This lets the SDK demo
    surface only universal rules.

    Args:
        rules: Output from :func:`apply_rules`.
        merge: Whether to merge same-category rules (default True).
        scope_filter: When set, only include rules with this transfer scope.

    Returns:
        Formatted XML block, or ``""`` if *rules* is empty.
    """
    if scope_filter is not None:
        rules = [r for r in rules if r.lesson.transfer_scope == scope_filter]

    if not rules:
        return ""

    # Merge related rules to save tokens
    if merge:
        rules = merge_related_rules(rules)

    # Bucketed shuffle: group by tier, shuffle within each tier, concatenate
    # in tier order (RULE first). Prevents adversaries from inferring
    # confidence rankings via injection order.
    tier_order = [LessonState.RULE, LessonState.PATTERN, LessonState.INSTINCT]
    buckets: dict[LessonState, list[AppliedRule]] = {t: [] for t in tier_order}
    for r in rules:
        bucket = buckets.get(r.lesson.state)
        if bucket is not None:
            bucket.append(r)
    # Shuffle within each tier
    if shuffle_seed is not None:
        rng = random.Random(shuffle_seed)
        for tier in tier_order:
            rng.shuffle(buckets[tier])
    else:
        for tier in tier_order:
            # Production: use secrets for non-deterministic shuffle
            bucket = buckets[tier]
            for i in range(len(bucket) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                bucket[i], bucket[j] = bucket[j], bucket[i]
    rules = []
    for tier in tier_order:
        rules.extend(buckets[tier])

    lines = [
        "<brain-rules>",
    ]

    for rule in rules:
        lines.append(f"- {rule.instruction}")

        # Include few-shot examples only for low-confidence rules with misfires
        lesson = rule.lesson
        needs_reinforcement = lesson.confidence < 0.70 and getattr(lesson, "misfire_count", 0) > 1
        if (
            needs_reinforcement
            and getattr(lesson, "example_draft", None) is not None
            and getattr(lesson, "example_corrected", None) is not None
        ):
            lines.append(
                f'   e.g. "{lesson.example_draft[:80]}" -> "{lesson.example_corrected[:80]}"'
            )

    lines.append("</brain-rules>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Example Capture
# ---------------------------------------------------------------------------

_EXAMPLE_MAX_CHARS = 200


def capture_example_from_correction(
    lesson: Lesson,
    draft: str,
    corrected: str,
) -> Lesson:
    """Attach a draft/corrected pair as a few-shot example on a lesson.

    When a correction matches an existing lesson's category, the caller
    should invoke this to store the pair on the lesson so that
    :func:`format_rules_for_prompt` can include it for reinforcement.

    Only the first ``_EXAMPLE_MAX_CHARS`` characters of each string are
    stored to keep token cost low.  If the lesson already has an example
    the new one overwrites it (most recent correction is most relevant).

    Args:
        lesson: The lesson to attach the example to.
        draft: The AI-generated text before correction.
        corrected: The human-edited text after correction.

    Returns:
        The same lesson instance, mutated with the new example fields.
    """
    lesson.example_draft = draft[:_EXAMPLE_MAX_CHARS]
    lesson.example_corrected = corrected[:_EXAMPLE_MAX_CHARS]
    return lesson
