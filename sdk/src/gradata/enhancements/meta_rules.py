"""
Meta-Rule Emergence — compound learning through principle discovery.
====================================================================
SDK LAYER: Layer 1 (enhancements). Imports from patterns/ and _types.

When multiple individual corrections share an underlying pattern, a
meta-rule automatically emerges.  Meta-rules capture the PRINCIPLE
behind corrections, enabling the AI to generalise to new situations
it hasn't been corrected on yet.

Example:
    "Use colons not dashes" + "No em dashes in emails" + "No bold
    mid-paragraph" + "Tight prose"
    ->  META-RULE: "Oliver values minimal, clean formatting: no
        decorative punctuation, no inline emphasis, direct sentences"

Integration points:
    - ``discover_meta_rules()`` runs at session close (wrap-up)
    - ``refresh_meta_rules()`` runs at session start
    - The rule engine prefers meta-rules over individual rules
    - Each meta-rule counts as 1 toward the 10-rule cap but
      represents 3-5 underlying corrections

OPEN SOURCE: The discovery algorithm is open.  Meta-rule optimisation
(injection weighting, audience-aware selection) is proprietary cloud-side.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from gradata._types import ELIGIBLE_STATES, Lesson, LessonState, RuleTransferScope

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

_ELIGIBLE_STATES = ELIGIBLE_STATES

# Tier constants (Rosch 1978: subordinate / basic / superordinate)
TIER_META = 1           # Meta-rule: emerges from 3+ graduated lessons
TIER_SUPER_META = 2     # Super-meta-rule: emerges from 3+ meta-rules
TIER_UNIVERSAL = 3      # Universal principle: emerges from 3+ super-meta-rules


@dataclass
class MetaRule:
    """An emergent principle synthesised from 3+ related corrections.

    Attributes:
        id: Deterministic hash of source lesson IDs (stable across runs).
        principle: The emergent principle in 1-2 sentences.
        source_categories: Which lesson categories contributed.
        source_lesson_ids: Opaque IDs of the contributing lessons.
        confidence: Average confidence of source rules.
        created_session: Session number when first discovered.
        last_validated_session: Last session where the meta-rule was
            confirmed still valid (no contradicting corrections).
        scope: Task/domain/audience constraints (JSON-serialisable).
        examples: 1-2 concrete examples illustrating the principle.
        context_weights: Maps context labels (e.g. ``"drafting"``,
            ``"code"``) to float multipliers applied to base confidence
            during context-dependent ranking. Defaults to
            ``{"default": 1.0}`` (neutral).
    """

    id: str
    principle: str
    source_categories: list[str]
    source_lesson_ids: list[str]
    confidence: float
    created_session: int
    last_validated_session: int
    scope: dict = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    context_weights: dict[str, float] = field(default_factory=lambda: {"default": 1.0})
    applies_when: list[str] = field(default_factory=list)
    never_when: list[str] = field(default_factory=list)
    transfer_scope: RuleTransferScope = RuleTransferScope.PERSONAL


@dataclass
class SuperMetaRule:
    """A higher-order principle synthesised from 3+ related meta-rules.

    Implements Rosch 1978 three-level categorisation:
        Tier 1 (basic/meta): MetaRule — emerges from lessons.
        Tier 2 (superordinate/super-meta): SuperMetaRule — emerges from meta-rules.
        Tier 3 (universal): SuperMetaRule with tier=3 — emerges from super-meta-rules.

    Follows AGM belief revision: new evidence can contract or expand the
    principle set while maintaining consistency.

    Attributes:
        id: Deterministic hash of source meta-rule IDs.
        abstraction: The generalised principle in 1-2 sentences.
        source_meta_rule_ids: IDs of the contributing meta-rules (or
            super-meta-rule IDs for tier-3).
        tier: Abstraction level (2=super-meta, 3=universal).
        confidence: Weighted average of source confidences.
        context_weights: Merged context weights from all sources.
        source_categories: Union of categories from source meta-rules.
        created_session: Session number when first discovered.
        last_validated_session: Last session where still valid.
        scope: Inherited scope constraints (intersection of sources).
        examples: Representative examples from sources.
    """

    id: str
    abstraction: str
    source_meta_rule_ids: list[str]
    tier: int
    confidence: float
    context_weights: dict[str, float] = field(default_factory=lambda: {"default": 1.0})
    source_categories: list[str] = field(default_factory=list)
    created_session: int = 0
    last_validated_session: int = 0
    scope: dict = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    applies_when: list[str] = field(default_factory=list)
    never_when: list[str] = field(default_factory=list)
    transfer_scope: RuleTransferScope = RuleTransferScope.PERSONAL


# ---------------------------------------------------------------------------
# Condition Evaluation
# ---------------------------------------------------------------------------


def evaluate_conditions(
    rule: MetaRule | SuperMetaRule,
    context: dict,
) -> bool:
    """Check if a rule should apply given the current context.

    Returns ``True`` if **all** ``applies_when`` conditions match **and**
    **no** ``never_when`` conditions match.  Empty lists are permissive:
    empty ``applies_when`` means "always applies", empty ``never_when``
    means "never blocked".

    Condition format:
        - ``"key=value"`` — exact string match
        - ``"key!=value"`` — string inequality
        - ``"key>=N"`` / ``"key<=N"`` — numeric comparison

    Args:
        rule: A :class:`MetaRule` or :class:`SuperMetaRule` with
            ``applies_when`` and ``never_when`` fields.
        context: Dict with keys like ``session_type``, ``task``,
            ``severity``, ``domain``, etc.

    Returns:
        ``True`` if the rule should be injected, ``False`` otherwise.
    """
    # Check all applies_when (AND logic — all must pass)
    for cond in rule.applies_when:
        if not _eval_single_condition(cond, context):
            return False

    # Check all never_when (any match blocks the rule)
    for cond in rule.never_when:
        if _eval_single_condition(cond, context):
            return False

    return True


def _eval_single_condition(condition: str, context: dict) -> bool:
    """Evaluate a single condition string against a context dict.

    Supports: ``=``, ``!=``, ``>=``, ``<=`` operators.
    Missing context keys cause the condition to fail (return False).
    """
    # Try operators in order of specificity (longest first)
    for op in (">=", "<=", "!=", "="):
        if op in condition:
            parts = condition.split(op, 1)
            if len(parts) != 2:
                return False
            key, expected = parts[0].strip(), parts[1].strip()
            actual = context.get(key)
            if actual is None:
                return False

            if op == "=":
                return str(actual) == expected
            elif op == "!=":
                return str(actual) != expected
            elif op in (">=", "<="):
                try:
                    actual_num = float(actual)
                    expected_num = float(expected)
                except (ValueError, TypeError):
                    return False
                if op == ">=":
                    return actual_num >= expected_num
                else:
                    return actual_num <= expected_num
    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lesson_id(lesson: Lesson) -> str:
    """Derive a stable ID from a lesson's category + description."""
    raw = f"{lesson.category}:{lesson.description}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _meta_id(lesson_ids: list[str]) -> str:
    """Deterministic meta-rule ID from sorted source lesson IDs."""
    canonical = "|".join(sorted(lesson_ids))
    return "META-" + hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _tokenise(text: str) -> set[str]:
    """Split text into lowercase word tokens, stripping punctuation."""
    return set(re.findall(r"[a-z]{3,}", text.lower()))


# Semantic theme clusters: words that indicate the same underlying theme.
# Each key is a theme label; values are words that signal that theme.
_THEME_CLUSTERS: dict[str, set[str]] = {
    "formatting": {
        "format", "formatting", "bold", "dash", "dashes", "colon",
        "colons", "emphasis", "punctuation", "bullet", "bullets",
        "paragraph", "prose", "style", "numbered", "list", "lists",
        "subject", "lines", "decorative", "inline",
    },
    "pricing": {
        "pricing", "price", "cost", "costs", "subscription", "monthly",
        "annual", "tier", "tiers", "starter", "standard", "budget",
        "value", "deal", "revenue", "paid", "free",
    },
    "accuracy": {
        "verify", "verified", "check", "confirm", "accurate", "accuracy",
        "never", "guess", "assume", "assumption", "verify", "validate",
        "validated", "source", "evidence", "facts", "factual",
    },
    "research_first": {
        "research", "linkedin", "apollo", "investigate", "before",
        "prior", "lookup", "enrich", "enrichment", "profile", "scrape",
    },
    "prospect_handling": {
        "prospect", "lead", "leads", "campaign", "demo", "followup",
        "follow", "outreach", "email", "emails", "draft", "drafting",
        "subject", "thread", "reply", "calendly",
    },
    "process_discipline": {
        "skip", "skipping", "never", "always", "mandatory", "gate",
        "gates", "checklist", "step", "steps", "wrap", "startup",
        "audit", "verify", "verification", "done", "ready", "complete",
    },
    "tool_usage": {
        "tool", "tools", "api", "apify", "scraper", "notebooklm",
        "pipedrive", "apollo", "gmail", "instantly", "opencli",
        "fireflies", "playwright",
    },
    "communication_tone": {
        "tone", "empathy", "condescending", "casual", "direct",
        "agency", "positioning", "framing", "pitch", "sell",
        "feature", "outcome", "pain", "acknowledge",
    },
    "data_integrity": {
        "filter", "owner", "oliver", "anna", "shared", "blended",
        "metrics", "measurement", "dedup", "duplicate", "integrity",
    },
    "ip_protection": {
        "public", "docs", "documentation", "expose", "mechanism",
        "competitor", "architecture", "internal", "proprietary",
        "open", "source",
    },
}


def _detect_themes(text: str) -> dict[str, int]:
    """Return {theme: overlap_count} for a piece of text."""
    tokens = _tokenise(text)
    hits: dict[str, int] = {}
    for theme, keywords in _THEME_CLUSTERS.items():
        overlap = len(tokens & keywords)
        if overlap >= 2:
            hits[theme] = overlap
    return hits


def _synthesise_principle(lessons: list[Lesson], theme: str) -> str:
    """Generate a principle statement from a group of related lessons.

    Uses template-based synthesis: extract the common theme, summarise
    the specific behaviours, and frame as a user preference.
    """
    # Collect the action verbs and key constraints from descriptions
    behaviours: list[str] = []
    for lesson in lessons:
        desc = lesson.description
        # Grab the actionable part (after the arrow if present)
        if "→" in desc:
            desc = desc.split("→", 1)[1].strip()
        # Truncate long descriptions to the first sentence
        first_sentence = re.split(r"[.!]", desc)[0].strip()
        if first_sentence and len(first_sentence) < 120:
            behaviours.append(first_sentence)

    # If we got no behaviours from the arrow split, use raw descriptions
    if not behaviours:
        for lesson in lessons:
            first_sentence = re.split(r"[.!]", lesson.description)[0].strip()
            if first_sentence and len(first_sentence) < 120:
                behaviours.append(first_sentence)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for b in behaviours:
        key = b.lower()
        if key not in seen:
            seen.add(key)
            unique.append(b)

    # Theme-specific principle templates
    _TEMPLATES: dict[str, str] = {
        "formatting": "Clean, minimal formatting: {behaviours}",
        "pricing": "Pricing is verbal-only and precise: {behaviours}",
        "accuracy": "Verify before stating: {behaviours}",
        "research_first": "Research must complete before action: {behaviours}",
        "prospect_handling": "Prospect communications follow strict protocols: {behaviours}",
        "process_discipline": "Never skip process steps: {behaviours}",
        "tool_usage": "Use the right tool correctly: {behaviours}",
        "communication_tone": "Communication matches context and audience: {behaviours}",
        "data_integrity": "All data must be owner-filtered and deduplicated: {behaviours}",
        "ip_protection": "Public docs sell outcomes, never expose internals: {behaviours}",
    }

    template = _TEMPLATES.get(theme, "Learned principle: {behaviours}")

    # Join up to 4 behaviours into a semicolon-separated list
    summary = "; ".join(unique[:4])
    if len(unique) > 4:
        summary += f" (+{len(unique) - 4} more)"

    return template.format(behaviours=summary.lower() if summary else "multiple related corrections")


# ---------------------------------------------------------------------------
# Transfer Scope Classification (mirrors rule_engine.classify_transfer_scope)
# ---------------------------------------------------------------------------

_UNIVERSAL_SIGNALS: list[str] = [
    "em dash", "em dashes",
    "verify", "verification",
    "fabricat", "hallucin",
    "bold mid-paragraph",
    "rule of three",
    "promotional language",
    "never skip",
    "don't assume", "never assume",
    "check before", "verify before",
    "superficial analysis",
]

_TEAM_SIGNALS: list[str] = [
    "pipedrive", "instantly", "calendly", "sprites",
    "apollo", "zerobounce", "prospeo",
    "brain/", ".carl/", "domain/",
    "notebooklm", "apify", "opencli",
    "gmail", "fireflies",
]


def _classify_meta_transfer_scope(text: str) -> RuleTransferScope:
    """Auto-classify transfer scope for a meta-rule or super-meta-rule.

    Uses the same signal lists as rule_engine.classify_transfer_scope.
    """
    lower = text.lower()
    for signal in _UNIVERSAL_SIGNALS:
        if signal in lower:
            return RuleTransferScope.UNIVERSAL
    for signal in _TEAM_SIGNALS:
        if signal in lower:
            return RuleTransferScope.TEAM
    return RuleTransferScope.PERSONAL


def _pick_examples(lessons: list[Lesson], max_examples: int = 2) -> list[str]:
    """Pick the most concrete example descriptions from a lesson group."""
    # Prefer lessons with arrows (explicit correction format)
    with_arrow = [l for l in lessons if "→" in l.description]
    source = with_arrow if with_arrow else lessons

    examples: list[str] = []
    for lesson in source[:max_examples]:
        desc = lesson.description
        if len(desc) > 150:
            desc = desc[:147] + "..."
        examples.append(f"[{lesson.category}] {desc}")
    return examples


# ---------------------------------------------------------------------------
# Core: Grouping
# ---------------------------------------------------------------------------

def _group_by_category(lessons: list[Lesson]) -> dict[str, list[Lesson]]:
    """Group graduated lessons by their category."""
    groups: dict[str, list[Lesson]] = defaultdict(list)
    for lesson in lessons:
        if lesson.state in _ELIGIBLE_STATES:
            groups[lesson.category].append(lesson)
    return dict(groups)


def _group_by_theme(lessons: list[Lesson]) -> dict[str, list[Lesson]]:
    """Group lessons across categories by semantic theme overlap."""
    eligible = [l for l in lessons if l.state in _ELIGIBLE_STATES]
    theme_groups: dict[str, list[Lesson]] = defaultdict(list)

    for lesson in eligible:
        themes = _detect_themes(lesson.description)
        if themes:
            # Assign to the strongest theme
            best_theme = max(themes, key=themes.get)  # type: ignore[arg-type]
            theme_groups[best_theme].append(lesson)

    return dict(theme_groups)


# ---------------------------------------------------------------------------
# Core: Discovery
# ---------------------------------------------------------------------------

def discover_meta_rules(
    lessons: list[Lesson],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[MetaRule]:
    """Scan graduated lessons for emergent meta-rules.

    Two grouping strategies run in parallel:
        1. Group by category (same-category clusters)
        2. Group by semantic theme (cross-category clusters)

    Any group with ``min_group_size`` or more lessons becomes a
    candidate meta-rule.  Duplicate lessons across strategies are
    deduplicated by meta-rule ID (which is derived from source
    lesson IDs).

    Args:
        lessons: All lessons (active + archived). Only PATTERN and
            RULE state lessons are considered.
        min_group_size: Minimum group size to form a meta-rule.
        current_session: Current session number for timestamping.

    Returns:
        List of discovered :class:`MetaRule` objects, sorted by
        confidence descending.
    """
    seen_ids: set[str] = set()
    metas: list[MetaRule] = []

    # Strategy 1: category-based grouping
    for category, group in _group_by_category(lessons).items():
        if len(group) >= min_group_size:
            meta = merge_into_meta(group, theme_override=category.lower(), session=current_session)
            if meta.id not in seen_ids:
                seen_ids.add(meta.id)
                metas.append(meta)

    # Strategy 2: theme-based grouping (cross-category)
    for theme, group in _group_by_theme(lessons).items():
        if len(group) >= min_group_size:
            meta = merge_into_meta(group, theme_override=theme, session=current_session)
            if meta.id not in seen_ids:
                seen_ids.add(meta.id)
                metas.append(meta)

    metas.sort(key=lambda m: m.confidence, reverse=True)
    return metas


def merge_into_meta(
    rules: list[Lesson],
    theme_override: str = "",
    session: int = 0,
) -> MetaRule:
    """Synthesise a group of related rules into one meta-rule.

    Args:
        rules: The grouped lessons (all should be PATTERN or RULE).
        theme_override: If provided, use this as the theme label
            instead of auto-detecting.
        session: Current session number.

    Returns:
        A :class:`MetaRule` instance.
    """
    lesson_ids = [_lesson_id(l) for l in rules]
    meta_id = _meta_id(lesson_ids)

    # Detect theme if not overridden
    if theme_override:
        theme = theme_override
    else:
        # Combine all descriptions and pick the dominant theme
        combined = " ".join(l.description for l in rules)
        themes = _detect_themes(combined)
        theme = max(themes, key=themes.get) if themes else "general"  # type: ignore[arg-type]

    principle = _synthesise_principle(rules, theme)
    categories = sorted(set(l.category for l in rules))
    avg_confidence = round(sum(l.confidence for l in rules) / len(rules), 2) if rules else 0.0

    # Infer scope from majority of source rules
    scope: dict = {}
    if all("email" in l.description.lower() or "draft" in l.description.lower() for l in rules):
        scope["task_type"] = "email_draft"
    if all("demo" in l.description.lower() for l in rules):
        scope["task_type"] = "demo_prep"

    examples = _pick_examples(rules)

    # Auto-classify transfer scope from principle text
    transfer_scope = _classify_meta_transfer_scope(principle)

    return MetaRule(
        id=meta_id,
        principle=principle,
        source_categories=categories,
        source_lesson_ids=lesson_ids,
        confidence=avg_confidence,
        created_session=session,
        last_validated_session=session,
        scope=scope,
        examples=examples,
        transfer_scope=transfer_scope,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_meta_rule(
    meta: MetaRule,
    recent_corrections: list[dict],
) -> bool:
    """Check if a meta-rule is still valid (no contradicting corrections).

    A meta-rule is invalidated when a recent correction directly
    contradicts its principle.  Detection uses keyword overlap between
    the correction description and the meta-rule principle.

    Args:
        meta: The meta-rule to validate.
        recent_corrections: List of dicts with at least a
            ``"description"`` key.

    Returns:
        ``True`` if the meta-rule is still valid, ``False`` if a
        contradiction was detected.
    """
    if not recent_corrections:
        return True

    principle_tokens = _tokenise(meta.principle)

    # Contradiction signals: if a correction shares significant overlap
    # with the principle AND contains negation/reversal language
    _REVERSAL_WORDS = {"actually", "instead", "wrong", "incorrect", "stop", "dont", "not"}

    for correction in recent_corrections:
        desc = correction.get("description", "")
        desc_tokens = _tokenise(desc)

        overlap = len(principle_tokens & desc_tokens)
        has_reversal = bool(desc_tokens & _REVERSAL_WORDS)

        # High overlap + reversal language = likely contradiction
        if overlap >= 4 and has_reversal:
            return False

    return True


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_meta_rules_for_prompt(
    metas: list[MetaRule],
    context: str = "",
    condition_context: dict | None = None,
    scope_filter: RuleTransferScope | None = None,
) -> str:
    """Format meta-rules for injection into LLM context.

    Each meta-rule is rendered as a numbered principle with its
    confidence score and source count.  This replaces the individual
    rule injection when meta-rules are available.

    When *context* is provided, meta-rules are re-ranked by their
    context-dependent weight before formatting, so the most relevant
    rules for the current task appear first.

    When *condition_context* is provided, rules are filtered through
    :func:`evaluate_conditions` before formatting.

    When *scope_filter* is provided, only meta-rules with the matching
    ``transfer_scope`` are included.

    Args:
        metas: Meta-rules to format.
        context: Optional task-context label (e.g. ``"drafting"``,
            ``"code"``). When provided, rules are re-ranked by
            context weight. When empty, original order is preserved.
        condition_context: Optional dict for precondition/anti-condition
            filtering. When provided, only rules passing
            :func:`evaluate_conditions` are included.
        scope_filter: When set, only include meta-rules with this
            transfer scope.

    Returns:
        Formatted string block, or ``""`` if *metas* is empty.
    """
    if scope_filter is not None:
        metas = [m for m in metas if m.transfer_scope == scope_filter]

    if not metas:
        return ""

    # Filter by preconditions/anti-conditions
    if condition_context is not None:
        metas = [m for m in metas if evaluate_conditions(m, condition_context)]

    if not metas:
        return ""

    # Re-rank by context weight when a context is provided
    if context:
        metas = rank_meta_rules_by_context(metas, context)

    lines = ["## Brain Meta-Rules (compound principles)"]
    for i, meta in enumerate(metas, start=1):
        n = len(meta.source_lesson_ids)
        categories = ", ".join(meta.source_categories)
        lines.append(
            f"{i}. [META:{meta.confidence:.2f}|{n} rules|{categories}] "
            f"{meta.principle}"
        )
        if meta.examples:
            for ex in meta.examples:
                lines.append(f"   - {ex}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Context-Dependent Weighting
# ---------------------------------------------------------------------------


def get_context_weight(meta: MetaRule, context: str) -> float:
    """Look up the weight multiplier for a meta-rule in a given context.

    The meta-rule's ``context_weights`` dict maps context labels (e.g.
    ``"drafting"``, ``"code"``, ``"prospecting"``) to float multipliers.
    If *context* is not found, falls back to the ``"default"`` key, then
    to 1.0 (neutral weight).

    Args:
        meta: The meta-rule to query.
        context: A task-context label (e.g. from ``detect_task_type``).

    Returns:
        Float multiplier in (0, +inf). Typical range: 0.1 to 2.0.
    """
    weights = meta.context_weights or {}
    return weights.get(context, weights.get("default", 1.0))


def rank_meta_rules_by_context(
    metas: list[MetaRule],
    context: str = "",
    max_rules: int = 10,
) -> list[MetaRule]:
    """Re-rank meta-rules by context-weighted confidence.

    Each meta-rule's base confidence is multiplied by its context weight
    for the given *context*.  Rules are then sorted by weighted confidence
    descending and capped at *max_rules*.

    This allows the same meta-rule to be critical in one context (weight
    1.5 during email drafting) and low-priority in another (weight 0.3
    during code review), without changing the underlying confidence.

    Args:
        metas: Meta-rules to rank (not mutated).
        context: Task-context label. Empty string uses ``"default"`` weight.
        max_rules: Maximum rules to return.

    Returns:
        Sorted list of meta-rules, most relevant to *context* first.
    """
    ctx = context or "default"

    weighted: list[tuple[MetaRule, float]] = []
    for meta in metas:
        weight = get_context_weight(meta, ctx)
        weighted_confidence = meta.confidence * weight
        weighted.append((meta, weighted_confidence))

    weighted.sort(key=lambda t: t[1], reverse=True)
    return [meta for meta, _ in weighted[:max_rules]]


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

def refresh_meta_rules(
    lessons: list[Lesson],
    existing_metas: list[MetaRule],
    recent_corrections: list[dict] | None = None,
    current_session: int = 0,
    min_group_size: int = 3,
) -> list[MetaRule]:
    """Re-discover meta-rules, keeping valid existing ones.

    Pipeline:
        1. Validate each existing meta-rule against recent corrections.
        2. Drop invalidated meta-rules.
        3. Re-run discovery on the full lesson set.
        4. Merge: keep existing valid meta-rules (preserving their
           ``created_session``), add newly discovered ones.

    Args:
        lessons: All lessons (active + archived).
        existing_metas: Previously discovered meta-rules.
        recent_corrections: Corrections from the latest session(s).
        current_session: Current session number.
        min_group_size: Minimum group size for meta-rule discovery.

    Returns:
        Updated list of :class:`MetaRule` objects.
    """
    corrections = recent_corrections or []

    # Step 1-2: validate existing
    valid_existing: dict[str, MetaRule] = {}
    for meta in existing_metas:
        if validate_meta_rule(meta, corrections):
            meta.last_validated_session = current_session
            valid_existing[meta.id] = meta

    # Step 3: re-discover
    discovered = discover_meta_rules(lessons, min_group_size, current_session)

    # Step 4: merge (existing take priority to preserve created_session)
    merged: dict[str, MetaRule] = {}
    for meta in discovered:
        if meta.id in valid_existing:
            merged[meta.id] = valid_existing[meta.id]
        else:
            merged[meta.id] = meta

    # Also keep existing valid ones that weren't re-discovered
    # (source lessons may have been archived but meta-rule is still valid)
    for mid, meta in valid_existing.items():
        if mid not in merged:
            merged[mid] = meta

    result = sorted(merged.values(), key=lambda m: m.confidence, reverse=True)
    return result


# ---------------------------------------------------------------------------
# Super-Meta-Rule Helpers
# ---------------------------------------------------------------------------

def _super_meta_id(meta_rule_ids: list[str]) -> str:
    """Deterministic super-meta-rule ID from sorted source meta-rule IDs."""
    canonical = "|".join(sorted(meta_rule_ids))
    return "SMETA-" + hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _merge_context_weights(metas: "list[MetaRule] | list[SuperMetaRule] | list[MetaRule | SuperMetaRule]") -> dict[str, float]:
    """Merge context weights from multiple rules by averaging per key."""
    all_keys: set[str] = set()
    for m in metas:
        all_keys.update(m.context_weights.keys())

    merged: dict[str, float] = {}
    for key in all_keys:
        values = [m.context_weights.get(key, m.context_weights.get("default", 1.0))
                  for m in metas]
        merged[key] = round(sum(values) / len(values), 2)
    return merged


def _group_meta_rules_by_category_overlap(
    metas: list[MetaRule],
) -> dict[str, list[MetaRule]]:
    """Group meta-rules that share overlapping source categories.

    Two meta-rules are grouped together if they share at least one
    source category.  Uses union-find semantics: if A overlaps B and
    B overlaps C, all three land in the same group.
    """
    # Build adjacency: meta-rule index -> set of category strings
    cat_to_metas: dict[str, list[int]] = defaultdict(list)
    for i, meta in enumerate(metas):
        for cat in meta.source_categories:
            cat_to_metas[cat].append(i)

    # Union-find
    parent = list(range(len(metas)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for indices in cat_to_metas.values():
        for j in range(1, len(indices)):
            union(indices[0], indices[j])

    # Collect groups
    groups: dict[int, list[MetaRule]] = defaultdict(list)
    for i, meta in enumerate(metas):
        groups[find(i)].append(meta)

    # Label each group by its most common category
    labelled: dict[str, list[MetaRule]] = {}
    for group in groups.values():
        all_cats: list[str] = []
        for m in group:
            all_cats.extend(m.source_categories)
        label = max(set(all_cats), key=all_cats.count) if all_cats else "general"
        labelled[label] = group

    return labelled


def _group_meta_rules_by_theme(metas: list[MetaRule]) -> dict[str, list[MetaRule]]:
    """Group meta-rules by semantic theme overlap in their principles."""
    theme_groups: dict[str, list[MetaRule]] = defaultdict(list)
    for meta in metas:
        themes = _detect_themes(meta.principle)
        if themes:
            best = max(themes, key=themes.get)  # type: ignore[arg-type]
            theme_groups[best].append(meta)
    return dict(theme_groups)


def _synthesise_super_principle(metas: "list[MetaRule] | list[SuperMetaRule] | list[MetaRule | SuperMetaRule]", tier: int) -> str:
    """Generate an abstraction statement from a group of meta-rules.

    Higher tiers produce more abstract, principle-level statements.
    """
    # Collect all principles/abstractions from sources
    principles: list[str] = []
    for m in metas:
        text = m.abstraction if isinstance(m, SuperMetaRule) else m.principle
        # Take the first clause (before semicolons)
        first = text.split(";")[0].strip()
        if first and len(first) < 120:
            principles.append(first)

    if not principles:
        principles = ["multiple related principles"]

    summary = "; ".join(principles[:3])
    if len(principles) > 3:
        summary += f" (+{len(principles) - 3} more)"

    if tier >= TIER_UNIVERSAL:
        return f"Universal principle: {summary.lower()}"
    return f"Super-principle: {summary.lower()}"


# ---------------------------------------------------------------------------
# Super-Meta-Rule Discovery
# ---------------------------------------------------------------------------

def detect_super_meta_rules(
    meta_rules: list[MetaRule],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[SuperMetaRule]:
    """Discover super-meta-rules from groups of related meta-rules.

    Two grouping strategies (mirroring ``discover_meta_rules``):
        1. Category overlap: meta-rules sharing source categories.
        2. Theme overlap: meta-rules whose principles share themes.

    Any group with ``min_group_size`` or more meta-rules yields a
    super-meta-rule (tier 2).

    Args:
        meta_rules: All current meta-rules.
        min_group_size: Minimum group size to form a super-meta-rule.
        current_session: Current session number.

    Returns:
        List of :class:`SuperMetaRule` objects, sorted by confidence
        descending.
    """
    seen_ids: set[str] = set()
    supers: list[SuperMetaRule] = []

    # Strategy 1: category-overlap grouping
    for _label, group in _group_meta_rules_by_category_overlap(meta_rules).items():
        if len(group) >= min_group_size:
            smeta = _build_super_meta(group, tier=TIER_SUPER_META, session=current_session)
            if smeta.id not in seen_ids:
                seen_ids.add(smeta.id)
                supers.append(smeta)

    # Strategy 2: theme-based grouping
    for _theme, group in _group_meta_rules_by_theme(meta_rules).items():
        if len(group) >= min_group_size:
            smeta = _build_super_meta(group, tier=TIER_SUPER_META, session=current_session)
            if smeta.id not in seen_ids:
                seen_ids.add(smeta.id)
                supers.append(smeta)

    supers.sort(key=lambda s: s.confidence, reverse=True)
    return supers


def detect_universal_rules(
    super_metas: list[SuperMetaRule],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[SuperMetaRule]:
    """Discover tier-3 universal principles from super-meta-rules.

    Groups super-meta-rules by overlapping categories; any group of
    ``min_group_size`` or more yields a universal principle (tier 3).

    Args:
        super_metas: All current tier-2 super-meta-rules.
        min_group_size: Minimum group size.
        current_session: Current session number.

    Returns:
        List of tier-3 :class:`SuperMetaRule` objects.
    """
    if len(super_metas) < min_group_size:
        return []

    # Group by category overlap (reuse theme detection on abstractions)
    theme_groups: dict[str, list[SuperMetaRule]] = defaultdict(list)
    for smeta in super_metas:
        themes = _detect_themes(smeta.abstraction)
        if themes:
            best = max(themes, key=themes.get)  # type: ignore[arg-type]
            theme_groups[best].append(smeta)

    universals: list[SuperMetaRule] = []
    seen_ids: set[str] = set()
    for _theme, group in theme_groups.items():
        if len(group) >= min_group_size:
            source_ids = [s.id for s in group]
            uid = "UNIV-" + hashlib.sha256(
                "|".join(sorted(source_ids)).encode()
            ).hexdigest()[:10]
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            all_cats = sorted(set(c for s in group for c in s.source_categories))
            avg_conf = round(sum(s.confidence for s in group) / len(group), 2)
            merged_weights = _merge_context_weights(group)
            examples = [s.abstraction[:100] for s in group[:2]]

            abstraction = _synthesise_super_principle(group, TIER_UNIVERSAL)
            transfer_scope = _classify_meta_transfer_scope(abstraction)

            universals.append(SuperMetaRule(
                id=uid,
                abstraction=abstraction,
                source_meta_rule_ids=source_ids,
                tier=TIER_UNIVERSAL,
                confidence=avg_conf,
                context_weights=merged_weights,
                source_categories=all_cats,
                created_session=current_session,
                last_validated_session=current_session,
                examples=examples,
                transfer_scope=transfer_scope,
            ))

    universals.sort(key=lambda u: u.confidence, reverse=True)
    return universals


def _build_super_meta(
    metas: list[MetaRule],
    tier: int = TIER_SUPER_META,
    session: int = 0,
) -> SuperMetaRule:
    """Synthesise a group of meta-rules into a super-meta-rule."""
    source_ids = [m.id for m in metas]
    sid = _super_meta_id(source_ids)

    all_cats = sorted(set(c for m in metas for c in m.source_categories))
    avg_conf = round(sum(m.confidence for m in metas) / len(metas), 2) if metas else 0.0
    merged_weights = _merge_context_weights(metas)

    # Scope: intersection (only constraints shared by ALL sources)
    scope: dict = {}
    if metas:
        scope_keys = set(metas[0].scope.keys())
        for m in metas[1:]:
            scope_keys &= set(m.scope.keys())
        for key in scope_keys:
            values = [m.scope[key] for m in metas]
            if len(set(str(v) for v in values)) == 1:
                scope[key] = values[0]

    examples = [m.principle[:100] for m in metas[:2]]

    abstraction = _synthesise_super_principle(metas, tier)
    transfer_scope = _classify_meta_transfer_scope(abstraction)

    return SuperMetaRule(
        id=sid,
        abstraction=abstraction,
        source_meta_rule_ids=source_ids,
        tier=tier,
        confidence=avg_conf,
        context_weights=merged_weights,
        source_categories=all_cats,
        created_session=session,
        last_validated_session=session,
        scope=scope,
        examples=examples,
        transfer_scope=transfer_scope,
    )


# ---------------------------------------------------------------------------
# Super-Meta-Rule Validation
# ---------------------------------------------------------------------------

def validate_super_meta_rule(
    smeta: SuperMetaRule,
    current_meta_rules: list[MetaRule],
) -> bool:
    """Check if a super-meta-rule is still valid.

    A super-meta-rule is invalid when fewer than 2 of its source
    meta-rules still exist (AGM contraction).

    Args:
        smeta: The super-meta-rule to validate.
        current_meta_rules: Currently active meta-rules.

    Returns:
        ``True`` if still supported by enough source meta-rules.
    """
    current_ids = {m.id for m in current_meta_rules}
    surviving = sum(1 for sid in smeta.source_meta_rule_ids if sid in current_ids)
    return surviving >= 2


# ---------------------------------------------------------------------------
# Super-Meta-Rule Refresh
# ---------------------------------------------------------------------------

def refresh_super_meta_rules(
    meta_rules: list[MetaRule],
    existing_supers: list[SuperMetaRule],
    current_session: int = 0,
    min_group_size: int = 3,
) -> list[SuperMetaRule]:
    """Re-discover super-meta-rules, keeping valid existing ones.

    Pipeline mirrors ``refresh_meta_rules``:
        1. Validate existing super-meta-rules against current meta-rules.
        2. Re-run discovery.
        3. Merge (existing take priority for created_session).
        4. Discover tier-3 universals from the merged tier-2 set.

    Args:
        meta_rules: All currently active meta-rules.
        existing_supers: Previously discovered super-meta-rules.
        current_session: Current session number.
        min_group_size: Minimum group size for discovery.

    Returns:
        Updated list of :class:`SuperMetaRule` objects (tier 2 and 3).
    """
    # Step 1: validate existing
    valid_existing: dict[str, SuperMetaRule] = {}
    for smeta in existing_supers:
        if smeta.tier == TIER_SUPER_META and validate_super_meta_rule(smeta, meta_rules):
            smeta.last_validated_session = current_session
            valid_existing[smeta.id] = smeta

    # Step 2: re-discover tier 2
    discovered = detect_super_meta_rules(meta_rules, min_group_size, current_session)

    # Step 3: merge
    merged: dict[str, SuperMetaRule] = {}
    for smeta in discovered:
        if smeta.id in valid_existing:
            merged[smeta.id] = valid_existing[smeta.id]
        else:
            merged[smeta.id] = smeta

    for sid, smeta in valid_existing.items():
        if sid not in merged:
            merged[sid] = smeta

    tier2_list = sorted(merged.values(), key=lambda s: s.confidence, reverse=True)

    # Step 4: discover tier-3 universals
    universals = detect_universal_rules(tier2_list, min_group_size, current_session)

    # Keep existing valid universals
    existing_universals = {s.id: s for s in existing_supers if s.tier == TIER_UNIVERSAL}
    for uid, univ in existing_universals.items():
        # Validate: at least 2 source super-metas still in tier2_list
        tier2_ids = {s.id for s in tier2_list}
        surviving = sum(1 for sid in univ.source_meta_rule_ids if sid in tier2_ids)
        if surviving >= 2:
            univ.last_validated_session = current_session
            if uid not in {u.id for u in universals}:
                universals.append(univ)

    return tier2_list + sorted(universals, key=lambda u: u.confidence, reverse=True)


# ---------------------------------------------------------------------------
# Super-Meta-Rule Formatting
# ---------------------------------------------------------------------------

def format_super_meta_rules_for_prompt(
    supers: list[SuperMetaRule],
    context: str = "",
    condition_context: dict | None = None,
) -> str:
    """Format super-meta-rules for injection into LLM context.

    Super-meta-rules go FIRST in the prompt (primacy positioning) as
    they represent the highest-priority generalised principles.

    When *context* is provided, rules are re-ranked by context weight.

    When *condition_context* is provided, rules are filtered through
    :func:`evaluate_conditions` before formatting.

    Args:
        supers: Super-meta-rules to format (tier 2 and 3).
        context: Optional task-context label for re-ranking.
        condition_context: Optional dict for precondition/anti-condition
            filtering.

    Returns:
        Formatted string block, or ``""`` if *supers* is empty.
    """
    if not supers:
        return ""

    # Filter by preconditions/anti-conditions
    if condition_context is not None:
        supers = [s for s in supers if evaluate_conditions(s, condition_context)]

    if not supers:
        return ""

    # Re-rank by context weight
    if context:
        ctx = context
        weighted: list[tuple[SuperMetaRule, float]] = []
        for s in supers:
            w = s.context_weights.get(ctx, s.context_weights.get("default", 1.0))
            weighted.append((s, s.confidence * w))
        weighted.sort(key=lambda t: t[1], reverse=True)
        supers = [s for s, _ in weighted]

    # Separate tiers for formatting
    universals = [s for s in supers if s.tier >= TIER_UNIVERSAL]
    tier2 = [s for s in supers if s.tier == TIER_SUPER_META]

    lines: list[str] = []

    if universals:
        lines.append("## Universal Principles (highest priority)")
        for i, u in enumerate(universals, start=1):
            n = len(u.source_meta_rule_ids)
            cats = ", ".join(u.source_categories[:5])
            lines.append(
                f"{i}. [UNIV:{u.confidence:.2f}|{n} super-rules|{cats}] "
                f"{u.abstraction}"
            )
            for ex in u.examples:
                lines.append(f"   - {ex}")

    if tier2:
        lines.append("")
        lines.append("## Super-Meta-Rules (compound meta-principles)")
        for i, s in enumerate(tier2, start=1):
            n = len(s.source_meta_rule_ids)
            cats = ", ".join(s.source_categories[:5])
            lines.append(
                f"{i}. [SMETA:{s.confidence:.2f}|{n} meta-rules|{cats}] "
                f"{s.abstraction}"
            )
            for ex in s.examples:
                lines.append(f"   - {ex}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SQLite Storage
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meta_rules (
    id TEXT PRIMARY KEY,
    principle TEXT NOT NULL,
    source_categories TEXT,
    source_lesson_ids TEXT,
    confidence REAL,
    created_session INTEGER,
    last_validated_session INTEGER,
    scope TEXT,
    examples TEXT,
    context_weights TEXT
);
"""

_ADD_CONTEXT_WEIGHTS_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN context_weights TEXT"
)

_ADD_APPLIES_WHEN_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN applies_when TEXT"
)

_ADD_NEVER_WHEN_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN never_when TEXT"
)

_ADD_TRANSFER_SCOPE_SQL = (
    "ALTER TABLE meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'"
)


def ensure_table(db_path: str | Path) -> None:
    """Create the meta_rules table if it does not exist.

    Also migrates existing tables by adding the ``context_weights``
    column when it is missing (backward-compatible upgrade).

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate: add columns if table existed before this version
        for stmt in (_ADD_CONTEXT_WEIGHTS_SQL, _ADD_APPLIES_WHEN_SQL, _ADD_NEVER_WHEN_SQL, _ADD_TRANSFER_SCOPE_SQL):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()
    finally:
        conn.close()


def save_meta_rules(db_path: str | Path, metas: list[MetaRule]) -> int:
    """Persist meta-rules to system.db, replacing all existing rows.

    Args:
        db_path: Path to the SQLite database file.
        metas: Meta-rules to save.

    Returns:
        Number of meta-rules saved.
    """
    ensure_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM meta_rules")
        for meta in metas:
            conn.execute(
                """INSERT INTO meta_rules
                   (id, principle, source_categories, source_lesson_ids,
                    confidence, created_session, last_validated_session,
                    scope, examples, context_weights, applies_when, never_when,
                    transfer_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meta.id,
                    meta.principle,
                    json.dumps(meta.source_categories),
                    json.dumps(meta.source_lesson_ids),
                    meta.confidence,
                    meta.created_session,
                    meta.last_validated_session,
                    json.dumps(meta.scope),
                    json.dumps(meta.examples),
                    json.dumps(meta.context_weights),
                    json.dumps(meta.applies_when),
                    json.dumps(meta.never_when),
                    meta.transfer_scope.value,
                ),
            )
        conn.commit()
        return len(metas)
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_meta_rules(db_path: str | Path) -> list[MetaRule]:
    """Load meta-rules from system.db.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of :class:`MetaRule` objects, sorted by confidence
        descending.  Empty list if the table does not exist.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_rules'"
        )
        if not cursor.fetchone():
            return []

        rows = conn.execute(
            """SELECT id, principle, source_categories, source_lesson_ids,
                      confidence, created_session, last_validated_session,
                      scope, examples, context_weights, applies_when, never_when,
                      transfer_scope
               FROM meta_rules
               ORDER BY confidence DESC"""
        ).fetchall()

        # Map stored strings back to enum values
        _SCOPE_MAP = {s.value: s for s in RuleTransferScope}

        metas: list[MetaRule] = []
        for row in rows:
            metas.append(MetaRule(
                id=row[0],
                principle=row[1],
                source_categories=json.loads(row[2]) if row[2] else [],
                source_lesson_ids=json.loads(row[3]) if row[3] else [],
                confidence=row[4] or 0.0,
                created_session=row[5] or 0,
                last_validated_session=row[6] or 0,
                scope=json.loads(row[7]) if row[7] else {},
                examples=json.loads(row[8]) if row[8] else [],
                context_weights=json.loads(row[9]) if row[9] else {"default": 1.0},
                applies_when=json.loads(row[10]) if row[10] else [],
                never_when=json.loads(row[11]) if row[11] else [],
                transfer_scope=_SCOPE_MAP.get(row[12], RuleTransferScope.PERSONAL) if row[12] else RuleTransferScope.PERSONAL,
            ))
        return metas
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Super-Meta-Rule SQLite Storage
# ---------------------------------------------------------------------------

_CREATE_SUPER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS super_meta_rules (
    id TEXT PRIMARY KEY,
    abstraction TEXT NOT NULL,
    source_meta_rule_ids TEXT,
    tier INTEGER,
    confidence REAL,
    context_weights TEXT,
    source_categories TEXT,
    created_session INTEGER,
    last_validated_session INTEGER,
    scope TEXT,
    examples TEXT
);
"""


_ADD_SUPER_APPLIES_WHEN_SQL = (
    "ALTER TABLE super_meta_rules ADD COLUMN applies_when TEXT"
)

_ADD_SUPER_NEVER_WHEN_SQL = (
    "ALTER TABLE super_meta_rules ADD COLUMN never_when TEXT"
)

_ADD_SUPER_TRANSFER_SCOPE_SQL = (
    "ALTER TABLE super_meta_rules ADD COLUMN transfer_scope TEXT DEFAULT 'personal'"
)


def ensure_super_table(db_path: str | Path) -> None:
    """Create the super_meta_rules table if it does not exist.

    Also migrates existing tables by adding ``applies_when`` and
    ``never_when`` columns when missing (backward-compatible upgrade).

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_SUPER_TABLE_SQL)
        for stmt in (_ADD_SUPER_APPLIES_WHEN_SQL, _ADD_SUPER_NEVER_WHEN_SQL, _ADD_SUPER_TRANSFER_SCOPE_SQL):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # Column already exists
        conn.commit()
    finally:
        conn.close()


def save_super_meta_rules(db_path: str | Path, supers: list[SuperMetaRule]) -> int:
    """Persist super-meta-rules to system.db, replacing all existing rows.

    Args:
        db_path: Path to the SQLite database file.
        supers: Super-meta-rules to save (tier 2 and 3).

    Returns:
        Number of super-meta-rules saved.
    """
    ensure_super_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM super_meta_rules")
        for s in supers:
            conn.execute(
                """INSERT INTO super_meta_rules
                   (id, abstraction, source_meta_rule_ids, tier,
                    confidence, context_weights, source_categories,
                    created_session, last_validated_session, scope, examples,
                    applies_when, never_when, transfer_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    s.id,
                    s.abstraction,
                    json.dumps(s.source_meta_rule_ids),
                    s.tier,
                    s.confidence,
                    json.dumps(s.context_weights),
                    json.dumps(s.source_categories),
                    s.created_session,
                    s.last_validated_session,
                    json.dumps(s.scope),
                    json.dumps(s.examples),
                    json.dumps(s.applies_when),
                    json.dumps(s.never_when),
                    s.transfer_scope.value,
                ),
            )
        conn.commit()
        return len(supers)
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_super_meta_rules(db_path: str | Path) -> list[SuperMetaRule]:
    """Load super-meta-rules from system.db.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of :class:`SuperMetaRule` objects, sorted by tier descending
        then confidence descending.  Empty list if table does not exist.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='super_meta_rules'"
        )
        if not cursor.fetchone():
            return []

        rows = conn.execute(
            """SELECT id, abstraction, source_meta_rule_ids, tier,
                      confidence, context_weights, source_categories,
                      created_session, last_validated_session, scope, examples,
                      applies_when, never_when, transfer_scope
               FROM super_meta_rules
               ORDER BY tier DESC, confidence DESC"""
        ).fetchall()

        _SCOPE_MAP = {s.value: s for s in RuleTransferScope}

        supers: list[SuperMetaRule] = []
        for row in rows:
            supers.append(SuperMetaRule(
                id=row[0],
                abstraction=row[1],
                source_meta_rule_ids=json.loads(row[2]) if row[2] else [],
                tier=row[3] or TIER_SUPER_META,
                confidence=row[4] or 0.0,
                context_weights=json.loads(row[5]) if row[5] else {"default": 1.0},
                source_categories=json.loads(row[6]) if row[6] else [],
                created_session=row[7] or 0,
                last_validated_session=row[8] or 0,
                scope=json.loads(row[9]) if row[9] else {},
                examples=json.loads(row[10]) if row[10] else [],
                applies_when=json.loads(row[11]) if row[11] else [],
                never_when=json.loads(row[12]) if row[12] else [],
                transfer_scope=_SCOPE_MAP.get(row[13], RuleTransferScope.PERSONAL) if row[13] else RuleTransferScope.PERSONAL,
            ))
        return supers
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Lesson Parsing (for testing with real data)
# ---------------------------------------------------------------------------

_LESSON_LINE_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\]\s+"
    r"\[(\w+):?([\d.]*)\]\s+"
    r"(\w[\w_/]*?):\s+"
    r"(.+)"
)


def parse_lessons_from_markdown(text: str) -> list[Lesson]:
    """Parse lessons from the markdown format used in lessons.md.

    Handles the format:
        [DATE] [STATE:CONFIDENCE] CATEGORY: description

    Args:
        text: Raw markdown text containing lesson entries.

    Returns:
        List of parsed :class:`Lesson` objects.
    """
    lessons: list[Lesson] = []
    for line in text.splitlines():
        line = line.strip()
        m = _LESSON_LINE_RE.match(line)
        if not m:
            continue

        date_str, state_str, conf_str, category, description = m.groups()

        # Map state string to enum
        state_map = {
            "INSTINCT": LessonState.INSTINCT,
            "PATTERN": LessonState.PATTERN,
            "RULE": LessonState.RULE,
            "UNTESTABLE": LessonState.UNTESTABLE,
        }
        state = state_map.get(state_str.upper(), LessonState.INSTINCT)

        confidence = float(conf_str) if conf_str else 0.50
        if state == LessonState.RULE and confidence < 0.90:
            confidence = 0.90

        # Extract root cause if present
        root_cause = ""
        if "Root cause:" in description:
            parts = description.split("Root cause:", 1)
            description = parts[0].strip()
            root_cause = parts[1].strip()

        transfer_scope = _classify_meta_transfer_scope(description)

        lessons.append(Lesson(
            date=date_str,
            state=state,
            confidence=confidence,
            category=category.upper(),
            description=description,
            root_cause=root_cause,
            transfer_scope=transfer_scope,
        ))

    return lessons
