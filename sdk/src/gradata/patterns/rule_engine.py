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
# Task-type detection keywords (for scope-weighted matching)
# ---------------------------------------------------------------------------

_TASK_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("email", ["email", "draft", "compose", "reply", "follow-up", "followup", "subject line"]),
    ("demo_prep", ["demo", "prep", "presentation", "deck", "slide"]),
    ("code", ["code", "implement", "refactor", "debug", "fix bug", "test", "function"]),
    ("prospecting", ["prospect", "lead", "enrich", "icp", "outreach", "campaign"]),
    ("research", ["research", "analyze", "investigate", "compare", "evaluate"]),
    ("call", ["call", "meeting", "agenda", "talking points"]),
    ("document", ["document", "readme", "spec", "guide", "report", "write up"]),
]


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
    events: list[dict[str, str]] | None = None,
    user_message: str = "",
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

    # Step 1 — eligibility gate
    eligible = [lesson for lesson in lessons if lesson.state in _ELIGIBLE_STATES]

    # Step 2 & 3 — score with weighted scope matching and threshold
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
        # Use weighted scope matching (exact > partial > wildcard)
        relevance = compute_scope_weight(lesson_scope, scope)
        if relevance >= 0.3:
            scored.append((lesson, relevance))

    # Step 4 — compute difficulty per rule
    # Step 5 — sort: state priority DESC, difficulty DESC, relevance DESC, confidence DESC
    scored.sort(
        key=lambda t: (
            _STATE_PRIORITY[t[0].state],
            # Difficulty: use event history if available, else lesson counters
            compute_rule_difficulty(t[0].category, events) if events else _difficulty_from_lesson(t[0]),
            t[1],
            t[0].confidence,
        ),
        reverse=True,
    )

    # Step 6 — assemble AppliedRule objects, capped at max_rules
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


def merge_related_rules(rules: list[AppliedRule], min_group_size: int = 2) -> list[AppliedRule]:
    """Merge rules sharing a category into compressed blocks.

    Groups with fewer than *min_group_size* rules stay individual.
    Merged rules use the highest confidence from the group and combine
    descriptions into one compressed instruction, saving tokens.
    """
    from collections import defaultdict

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
        merged_instruction = f"{cat}: {merged_desc} [{best.lesson.confidence:.2f}]"
        merged_rule = AppliedRule(
            rule_id=f"merged_{cat.lower()}",
            lesson=best.lesson,
            relevance=max(r.relevance for r in group),
            instruction=merged_instruction,
        )
        result.append(merged_rule)
    return result


def format_rules_for_prompt(rules: list[AppliedRule], merge: bool = True) -> str:
    """Format applied rules into an XML-tagged LLM-injectable block.

    Uses XML tags for unambiguous constraint signaling (Claude best practice).
    Applies primacy/recency positioning: highest-priority rules first,
    brief reminder of the #1 rule at the end.

    If *merge* is True, related rules in the same category are compressed
    into single blocks to save tokens.

    Args:
        rules: Output from :func:`apply_rules`.
        merge: Whether to merge same-category rules (default True).

    Returns:
        Formatted XML block, or ``""`` if *rules* is empty.
    """
    if not rules:
        return ""

    # Merge related rules to save tokens
    if merge:
        rules = merge_related_rules(rules)

    # Sort by priority: RULE state first, then difficulty (harder rules up),
    # then confidence descending. Primacy positioning: best rules at top
    # where LLMs attend most strongly.
    rules.sort(
        key=lambda r: (
            1 if r.lesson.state.value == "RULE" else 0,
            _difficulty_from_lesson(r.lesson),
            r.lesson.confidence,
        ),
        reverse=True,
    )

    lines = [
        "<brain-rules>",
        "Follow these learned behavioral rules exactly. They are derived from past corrections.",
        "",
    ]

    for i, rule in enumerate(rules, start=1):
        # Use positive framing: describe what TO do, not what not to do
        lines.append(f"{i}. {rule.instruction}")

        # Include few-shot examples for rules that need reinforcement
        lesson = rule.lesson
        needs_reinforcement = (
            lesson.confidence < 0.80
            or getattr(lesson, "misfire_count", 0) > 0
        )
        if (
            needs_reinforcement
            and getattr(lesson, "example_draft", None) is not None
            and getattr(lesson, "example_corrected", None) is not None
        ):
            lines.append("   <example>")
            lines.append(f'   DRAFT: "{lesson.example_draft}"')
            lines.append(f'   CORRECTED: "{lesson.example_corrected}"')
            lines.append("   </example>")

    # Recency reminder: repeat the #1 rule briefly at the end
    if rules:
        top = rules[0]
        lines.append("")
        lines.append(f"REMINDER: {top.lesson.category}: {top.lesson.description}")

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
