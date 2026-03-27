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
"""

from __future__ import annotations

from dataclasses import dataclass

from gradata._scope import RuleScope, scope_matches
from gradata._types import Lesson, LessonState

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

_ELIGIBLE_STATES: frozenset[LessonState] = frozenset(
    {LessonState.RULE, LessonState.PATTERN}
)


# ---------------------------------------------------------------------------
# Rule ID
# ---------------------------------------------------------------------------


def _make_rule_id(lesson: Lesson) -> str:
    """Derive a stable, opaque rule identifier from a lesson.

    Format: ``"CATEGORY:NNNN"`` where NNNN is a 4-digit decimal derived
    from the description hash modulo 10 000.  Collisions are possible but
    rare enough for the current scale.

    Args:
        lesson: Source lesson.

    Returns:
        Rule identifier string.
    """
    return f"{lesson.category}:{hash(lesson.description) % 10000:04d}"


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
        import json as _json
        if lesson.scope_json:
            try:
                scope_dict = _json.loads(lesson.scope_json)
                lesson_scope = RuleScope(**{k: v for k, v in scope_dict.items() if k in RuleScope.__dataclass_fields__})
            except Exception:
                lesson_scope = RuleScope()
        else:
            lesson_scope = RuleScope()
        score = scope_matches(lesson_scope, scope)
        if score >= min_relevance:
            results.append((lesson, score))
    return results


def apply_rules(
    lessons: list[Lesson],
    scope: RuleScope,
    max_rules: int = 10,
) -> list[AppliedRule]:
    """Select and rank lessons relevant to the given scope.

    Pipeline:
        1. Filter to PATTERN and RULE lessons only.
        2. Score each against *scope* via :func:`~gradata._scope.scope_matches`.
        3. Drop any with relevance < 0.3.
        4. Sort descending by (state_priority, relevance, confidence).
        5. Return the top *max_rules* as :class:`AppliedRule` objects.

    Args:
        lessons: All active lessons from the self-improvement pipeline.
        scope: Current task context used for relevance scoring.
        max_rules: Maximum number of rules to return (default 10).

    Returns:
        Ordered list of :class:`AppliedRule` objects, most relevant first.
        Empty list if no lessons pass the filters.
    """
    # Step 1 — eligibility gate
    eligible = [lesson for lesson in lessons if lesson.state in _ELIGIBLE_STATES]

    # Step 2 & 3 — score and threshold
    scored: list[tuple[Lesson, float]] = []
    for lesson in eligible:
        # Use lesson's stored scope if available, otherwise wildcard
        import json as _json
        if lesson.scope_json:
            try:
                scope_dict = _json.loads(lesson.scope_json)
                lesson_scope = RuleScope(**{k: v for k, v in scope_dict.items() if k in RuleScope.__dataclass_fields__})
            except Exception:
                lesson_scope = RuleScope()
        else:
            lesson_scope = RuleScope()
        relevance = scope_matches(lesson_scope, scope)
        if relevance >= 0.3:
            scored.append((lesson, relevance))

    # Step 4 — sort: state priority DESC, relevance DESC, confidence DESC
    scored.sort(
        key=lambda t: (
            _STATE_PRIORITY[t[0].state],
            t[1],
            t[0].confidence,
        ),
        reverse=True,
    )

    # Step 5 — assemble AppliedRule objects, capped at max_rules
    applied: list[AppliedRule] = []
    for lesson, relevance in scored[:max_rules]:
        rule_id = _make_rule_id(lesson)
        instruction = (
            f"[{lesson.state.value}:{lesson.confidence:.2f}]"
            f" {lesson.category}: {lesson.description}"
        )
        applied.append(
            AppliedRule(
                rule_id=rule_id,
                lesson=lesson,
                relevance=relevance,
                instruction=instruction,
            )
        )

    return applied


def format_rules_for_prompt(rules: list[AppliedRule]) -> str:
    """Format a list of applied rules into an LLM-injectable block.

    The block uses a numbered list with a ``## Brain Rules (auto-applied)``
    header.  If *rules* is empty the function returns an empty string so
    callers can safely skip injection when there are no active rules.

    Args:
        rules: Output from :func:`apply_rules`.

    Returns:
        Formatted string block, or ``""`` if *rules* is empty.

    Example output::

        ## Brain Rules (auto-applied)
        1. [RULE:0.95] DRAFTING: Always include pricing in first email
        2. [PATTERN:0.72] TONE: Use direct language with CTOs
    """
    if not rules:
        return ""

    lines = ["## Brain Rules (auto-applied)"]
    for i, rule in enumerate(rules, start=1):
        lines.append(f"{i}. {rule.instruction}")

    return "\n".join(lines)
