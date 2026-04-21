"""
Rule engine orchestration — apply_rules, filter_by_scope, TTL demotion.
========================================================================
Wires together scoring, formatting, and model layers.  Pure logic; no I/O.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.events_bus import EventBus
    from gradata.rules.rule_graph import RuleGraph

from gradata._scope import RuleScope
from gradata._types import ELIGIBLE_STATES, Lesson, LessonState
from gradata.security.score_obfuscation import truncate_score

from ._models import AppliedRule
from ._scoring import (
    _CT_BOOST,
    _STATE_PRIORITY,
    _difficulty_from_lesson,
    compute_rule_difficulty,
    compute_scope_weight,
    detect_task_type,
    effective_confidence,
    is_rule_disabled_for_domain,
    lesson_scope,
    validate_assumptions,
)

_log = logging.getLogger(__name__)

_ELIGIBLE_STATES = ELIGIBLE_STATES

# Default TTL for graduated rules, expressed in sessions-since-last-fire.
# Red-team finding A7: obsolete rules never decay and eventually contaminate
# output. Any RULE-tier lesson idle for >= DEFAULT_TTL_SESSIONS sessions is
# demoted back to PATTERN tier with a `stale=True` flag instead of being
# deleted — preserves history for review while blocking injection dominance.
DEFAULT_TTL_SESSIONS: int = 50


def _tier_label(lesson: Lesson) -> str:
    """Return the display tier for a lesson — state name if available, else confidence bucket."""
    return lesson.state.value if lesson.state else truncate_score(lesson.confidence)


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


def demote_stale_rules(
    lessons: list[Lesson],
    ttl_sessions: int = DEFAULT_TTL_SESSIONS,
    bus: EventBus | None = None,
) -> list[Lesson]:
    """Demote RULE-tier lessons that have exceeded their injection TTL.

    Any lesson with ``state == RULE`` and ``sessions_since_fire >=
    ttl_sessions`` is mutated in place to state ``PATTERN`` with
    ``stale=True``. Demoted lessons are returned so callers can persist the
    change or surface it to the user. A ``rule_demoted_ttl`` event is emitted
    on *bus* for each demotion (if a bus is provided).

    This is the injection-time counterpart to the existing kill path in
    ``self_improvement.py`` — it runs every time ``apply_rules`` is called,
    so idle rules never reach the prompt on a stale tier.

    Args:
        lessons: Lessons to evaluate. Mutated in place when demotion fires.
        ttl_sessions: Idle-session threshold. Rules with
            ``sessions_since_fire >= ttl_sessions`` are demoted. Default:
            ``DEFAULT_TTL_SESSIONS`` (50).
        bus: Optional event bus. When provided, a ``rule_demoted_ttl``
            event is emitted per demoted rule with payload
            ``{rule_id, category, description, sessions_since_fire,
            ttl_sessions}``.

    Returns:
        Newly-demoted lessons (empty list when none tripped). Already-stale
        lessons are not re-reported.
    """
    demoted: list[Lesson] = []
    if ttl_sessions <= 0:
        return demoted
    for lesson in lessons:
        if lesson.state is not LessonState.RULE:
            continue
        if lesson.sessions_since_fire < ttl_sessions:
            continue
        lesson.state = LessonState.PATTERN
        lesson.stale = True
        demoted.append(lesson)
        if bus is not None:
            bus.emit(
                "rule_demoted_ttl",
                {
                    "rule_id": _make_rule_id(lesson),
                    "category": lesson.category,
                    "description": lesson.description[:120],
                    "sessions_since_fire": lesson.sessions_since_fire,
                    "ttl_sessions": ttl_sessions,
                },
            )
    return demoted


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
        score = compute_scope_weight(lesson_scope(lesson), scope)
        if score >= min_relevance:
            results.append((lesson, score))
    return results


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
    ttl_sessions: int = DEFAULT_TTL_SESSIONS,
) -> list[AppliedRule]:
    """Select and rank lessons relevant to the given scope.

    Pipeline:
        0. Demote RULE-tier lessons idle for ``ttl_sessions`` sessions back
           to PATTERN with ``stale=True`` (zombie-rule mitigation).
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
        ttl_sessions: Idle-session TTL for RULE-tier lessons. Lessons with
            ``sessions_since_fire >= ttl_sessions`` are demoted to PATTERN
            with ``stale=True`` before scoring. Pass ``0`` to disable TTL.
            Default: :data:`DEFAULT_TTL_SESSIONS`.

    Returns:
        Ordered list of :class:`AppliedRule` objects, most relevant first.
        Empty list if no lessons pass the filters.
    """
    events = events or []

    # Step 0 — TTL demotion: demote RULE-tier lessons idle for >= ttl_sessions
    # back to PATTERN with stale=True. Blocks zombie-rule accumulation
    # (red-team finding A7). Runs before eligibility/scoring so stale rules
    # only survive on their demoted tier.
    if ttl_sessions > 0:
        demote_stale_rules(lessons, ttl_sessions=ttl_sessions, bus=bus)

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
        # Use weighted scope matching (exact > partial > wildcard)
        relevance = compute_scope_weight(lesson_scope(lesson), scope)
        relevance *= _CT_BOOST.get(lesson.correction_type, 1.0)
        if relevance >= 0.4:
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

    # Pre-compute difficulty per category once: compute_rule_difficulty is
    # O(E) per call, and calling it inside sort key was O(N × E). Collapse
    # to O(E + N) by bucketing events per category first.
    if events:
        difficulty_by_cat: dict[str, float] = {}
        unique_cats = {t[0].category.upper() for t in scored}
        for cat in unique_cats:
            difficulty_by_cat[cat] = compute_rule_difficulty(cat, events)

        def _difficulty(lesson: Lesson) -> float:
            return difficulty_by_cat.get(lesson.category.upper(), 0.5)
    else:

        def _difficulty(lesson: Lesson) -> float:
            return _difficulty_from_lesson(lesson)

    scored.sort(
        key=lambda t: (
            _STATE_PRIORITY[t[0].state],
            _difficulty(t[0]),
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


def apply_rules_with_tree(
    lessons: list[Lesson],
    scope: RuleScope,
    *,
    max_rules: int = 5,
    event_bus: EventBus | None = None,
    rule_graph: RuleGraph | None = None,
) -> list[AppliedRule]:
    """Apply rules using hierarchical tree retrieval.

    Falls back to flat scoring if no lessons have paths.
    """
    from gradata.rules.rule_tree import RuleTree

    # Check if any lessons have paths
    has_paths = any(l.path for l in lessons)
    if not has_paths:
        # Fallback: use existing flat apply_rules
        return apply_rules(lessons, scope, max_rules=max_rules, bus=event_bus, graph=rule_graph)

    tree = RuleTree(lessons)
    candidates = tree.get_rules_for_context(
        task_type=scope.task_type,
        domain=scope.domain,
        max_rules=max_rules * 2,  # get extra, let formatting trim
    )

    # Format as AppliedRule objects
    applied = []
    for lesson in candidates[:max_rules]:
        # Stable, deterministic ID — Python's built-in hash() is randomized
        # per-process (PYTHONHASHSEED), which broke RuleCache/RuleGraph lookups
        # keyed on rule_id across runs.
        rule_id = _make_rule_id(lesson)
        instruction = (
            f'<rule confidence="{lesson.confidence:.2f}">'
            f"{lesson.category}: {lesson.description}</rule>"
        )
        applied.append(
            AppliedRule(
                rule_id=rule_id,
                lesson=lesson,
                relevance=1.0,  # tree already filtered for relevance
                instruction=instruction,
            )
        )
    return applied
