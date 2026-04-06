"""
Meta-Rule Emergence — compound learning through principle discovery.
====================================================================
3+ related corrections merge into higher-order principles.
Discovery runs at session close; the rule engine prefers meta-rules
over individual rules (1 meta-rule replaces 3-5 corrections).

Public API is fully preserved here via re-exports from:
  - ``meta_rules_storage`` (SQLite persistence)
  - ``super_meta_rules`` (tier-2/3 logic)
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field

from gradata._types import ELIGIBLE_STATES, Lesson, RuleTransferScope

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

# Tier constants (Rosch 1978: subordinate / basic / superordinate)
TIER_META = 1           # Meta-rule: emerges from 3+ graduated lessons
TIER_SUPER_META = 2     # Super-meta-rule: emerges from 3+ meta-rules
TIER_UNIVERSAL = 3      # Universal principle: emerges from 3+ super-meta-rules


@dataclass
class MetaRule:
    """Emergent principle from 3+ related corrections."""

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
    """Higher-order principle from 3+ meta-rules (Rosch tier 2/3)."""

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
        "never", "guess", "assume", "assumption", "validate",
        "validated", "source", "evidence", "facts", "factual",
    },
    "research_first": {
        "research", "investigate", "before",
        "prior", "lookup", "enrich", "enrichment", "profile",
    },
    "entity_handling": {
        "entity", "item", "task", "message", "demo", "followup",
        "follow", "email", "emails", "draft", "drafting",
        "subject", "thread", "reply",
    },
    "process_discipline": {
        "skip", "skipping", "never", "always", "mandatory", "gate",
        "gates", "checklist", "step", "steps", "wrap", "startup",
        "audit", "verify", "verification", "done", "ready", "complete",
    },
    "tool_usage": {
        "tool", "tools", "api", "scraper",
        "playwright", "integration", "endpoint",
    },
    "communication_tone": {
        "tone", "empathy", "condescending", "casual", "direct",
        "agency", "positioning", "framing", "pitch", "sell",
        "feature", "outcome", "pain", "acknowledge",
    },
    "data_integrity": {
        "filter", "owner", "owner_only", "shared_filter", "shared", "blended",
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

    Extracts recurring patterns from lesson descriptions:
    - Words consistently cut across lessons → things the user dislikes
    - Words consistently added → things the user prefers
    - Tone/structure signals → communication style preferences

    Produces a human-readable principle like:
        "Prefer direct language (cut hedging: perhaps, might, probably)
         and add specifics (numbers, timelines, names)"
    """
    from collections import Counter

    # Parse structured descriptions to extract cut/added words and signals
    all_cut: Counter[str] = Counter()
    all_added: Counter[str] = Counter()
    signals: list[str] = []

    for lesson in lessons:
        desc = lesson.description

        # Extract "cut: word, word" patterns
        cut_match = re.search(r"cut:\s*([^;)]+)", desc, re.IGNORECASE)
        if cut_match:
            words = [w.strip() for w in cut_match.group(1).split(",") if w.strip()]
            all_cut.update(words)

        # Extract "added: word, word" patterns
        add_match = re.search(r"added:\s*([^;)]+)", desc, re.IGNORECASE)
        if add_match:
            words = [w.strip() for w in add_match.group(1).split(",") if w.strip()]
            all_added.update(words)

        # Collect tone/structure signals
        if "formalized" in desc.lower():
            signals.append("formalize")
        elif "casualized" in desc.lower():
            signals.append("casualize")
        if "strengthened" in desc.lower():
            signals.append("strengthen tone")
        elif "softened" in desc.lower():
            signals.append("soften tone")
        if "structure changed" in desc.lower():
            signals.append("restructure")
        if "reordered" in desc.lower():
            signals.append("reorder")

        # Handle non-structured descriptions (human-written lessons)
        if not cut_match and not add_match and "→" in desc:
            behaviour = desc.split("→", 1)[1].strip()
            first = re.split(r"[.!]", behaviour)[0].strip()
            if first and len(first) < 120:
                signals.append(first)

    # Build principle from recurring patterns
    parts: list[str] = []

    # Tone direction (most common signal)
    signal_counts = Counter(signals)
    top_signals = [s for s, _ in signal_counts.most_common(2) if signal_counts[s] >= 2]
    if top_signals:
        parts.append(f"Style: {', '.join(top_signals)}")

    # Most-cut words (things user consistently removes) — need 2+ occurrences
    frequent_cuts = [w for w, c in all_cut.most_common(8) if c >= 2]
    if frequent_cuts:
        parts.append(f"Avoid: {', '.join(frequent_cuts[:6])}")

    # Most-added words (things user consistently adds)
    frequent_adds = [w for w, c in all_added.most_common(8) if c >= 2]
    if frequent_adds:
        parts.append(f"Prefer: {', '.join(frequent_adds[:6])}")

    # Theme-specific framing
    _FRAMES: dict[str, str] = {
        "formatting": "Clean formatting",
        "pricing": "Precise pricing language",
        "accuracy": "Verify before stating",
        "research_first": "Research before action",
        "entity_handling": "Entity communication protocol",
        "process_discipline": "Process discipline",
        "tool_usage": "Correct tool usage",
        "communication_tone": "Tone and audience fit",
        "data_integrity": "Data integrity",
        "ip_protection": "Protect internals",
        "content": "Content preferences",
        "tone": "Communication style",
        "structure": "Document structure",
        "factual": "Factual accuracy",
        "process": "Workflow discipline",
        "style": "Formatting style",
    }

    frame = _FRAMES.get(theme.lower(), theme.replace("_", " ").title())

    if parts:
        return f"{frame}: {'. '.join(parts)}"

    # Fallback: collect raw descriptions
    descs = []
    for lesson in lessons:
        first = re.split(r"[.!;]", lesson.description)[0].strip()
        if first and len(first) < 100 and first.lower() not in {d.lower() for d in descs}:
            descs.append(first)
    if descs:
        summary = "; ".join(descs[:4])
        if len(descs) > 4:
            summary += f" (+{len(descs) - 4} more)"
        return f"{frame}: {summary}"

    return f"{frame}: {len(lessons)} related corrections"


# ---------------------------------------------------------------------------
# Transfer Scope Classification (delegates to rule_engine)
# ---------------------------------------------------------------------------

# Lazy import to avoid circular dependency with rule_engine.py
def _classify_meta_transfer_scope(rule_text: str) -> "RuleTransferScope":
    from gradata.rules.rule_engine import classify_transfer_scope
    return classify_transfer_scope(rule_text)


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
        if lesson.state in ELIGIBLE_STATES:
            groups[lesson.category].append(lesson)
    return dict(groups)


def _group_by_theme(lessons: list[Lesson]) -> dict[str, list[Lesson]]:
    """Group lessons across categories by semantic theme overlap.

    Two-pass strategy:
      1. Keyword-based: assign lessons to known theme clusters.
      2. Semantic fallback: lessons that didn't match any keyword theme
         are clustered by pairwise similarity (catches paraphrases).
    """
    eligible = [l for l in lessons if l.state in ELIGIBLE_STATES]
    theme_groups: dict[str, list[Lesson]] = defaultdict(list)
    unmatched: list[Lesson] = []

    # Pass 1: keyword themes
    for lesson in eligible:
        themes = _detect_themes(lesson.description)
        if themes:
            best_theme = max(themes, key=themes.get)  # type: ignore[arg-type]
            theme_groups[best_theme].append(lesson)
        else:
            unmatched.append(lesson)

    # Pass 2: semantic clustering for unmatched lessons
    if len(unmatched) >= 3:
        try:
            from gradata.enhancements.similarity import semantic_similarity
            # Greedy single-linkage: assign each unmatched lesson to its
            # nearest cluster, or start a new cluster if nothing is close.
            clusters: list[list[Lesson]] = []
            for lesson in unmatched:
                best_cluster = -1
                best_sim = 0.0
                for i, cluster in enumerate(clusters):
                    # Average-linkage: compare to all cluster members
                    # for more stable clustering than seed-only comparison.
                    avg_sim = sum(
                        semantic_similarity(lesson.description, m.description)
                        for m in cluster
                    ) / len(cluster)
                    if avg_sim > best_sim:
                        best_sim = avg_sim
                        best_cluster = i
                if best_sim >= 0.55 and best_cluster >= 0:
                    clusters[best_cluster].append(lesson)
                else:
                    clusters.append([lesson])

            for cluster in clusters:
                if len(cluster) >= 3:
                    # Deterministic name: most common category, alphabetic tie-break
                    cats = [ls.category for ls in cluster]
                    top_cat = sorted(set(cats), key=lambda c: (-cats.count(c), c))[0]
                    cluster_name = f"semantic_{top_cat.lower()}"
                    theme_groups[cluster_name].extend(cluster)
        except Exception:
            pass  # similarity module optional or computation failed

    return dict(theme_groups)


# ---------------------------------------------------------------------------
# Core: Discovery
# ---------------------------------------------------------------------------

def discover_meta_rules(
    lessons: list[Lesson],
    min_group_size: int = 3,
    current_session: int = 0,
    api_key: str | None = None,
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
        api_key: Optional LLM API key for principle synthesis.

    Returns:
        List of discovered :class:`MetaRule` objects, sorted by
        confidence descending.
    """
    seen_ids: set[str] = set()
    metas: list[MetaRule] = []

    # Strategy 1: category-based grouping
    for category, group in _group_by_category(lessons).items():
        if len(group) >= min_group_size:
            meta = merge_into_meta(group, theme_override=category.lower(), session=current_session, api_key=api_key)
            if meta.id not in seen_ids:
                seen_ids.add(meta.id)
                metas.append(meta)

    # Strategy 2: theme-based grouping (cross-category)
    for theme, group in _group_by_theme(lessons).items():
        if len(group) >= min_group_size:
            meta = merge_into_meta(group, theme_override=theme, session=current_session, api_key=api_key)
            if meta.id not in seen_ids:
                seen_ids.add(meta.id)
                metas.append(meta)

    metas.sort(key=lambda m: m.confidence, reverse=True)
    return metas


# ---------------------------------------------------------------------------

def merge_into_meta(
    rules: list[Lesson],
    theme_override: str = "",
    session: int = 0,
    api_key: str | None = None,
) -> MetaRule:
    """Synthesise a group of related rules into one meta-rule.

    Args:
        rules: The grouped lessons (all should be PATTERN or RULE).
        theme_override: If provided, use this as the theme label
            instead of auto-detecting.
        session: Current session number.
        api_key: Optional LLM API key for principle synthesis.

    Returns:
        A :class:`MetaRule` instance.
    """
    lesson_ids = [_lesson_id(l) for l in rules]
    meta_id = _meta_id(lesson_ids)

    # Stamp source lessons with their parent meta-rule ID.
    # Only stamp if not already assigned, so the first (highest-confidence)
    # meta-rule assignment wins when a lesson appears in multiple groups.
    for lesson in rules:
        if not lesson.parent_meta_rule_id:
            lesson.parent_meta_rule_id = meta_id

    # Detect theme if not overridden
    if theme_override:
        theme = theme_override
    else:
        # Combine all descriptions and pick the dominant theme
        combined = " ".join(l.description for l in rules)
        themes = _detect_themes(combined)
        theme = max(themes, key=themes.get) if themes else "general"  # type: ignore[arg-type]

    # Try LLM synthesis first (produces behavioral principles, not word lists)
    principle = None
    if api_key:
        from gradata.enhancements.llm_synthesizer import synthesise_principle_llm
        principle = synthesise_principle_llm(rules, theme, api_key=api_key)
    if principle is None:
        principle = _synthesise_principle(rules, theme)
    categories = sorted(set(l.category for l in rules))
    avg_confidence = min(1.0, round(sum(l.confidence for l in rules) / len(rules), 2)) if rules else 0.0

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
    _REVERSAL_WORDS = {"actually", "instead", "wrong", "incorrect", "stop", "dont", "don", "not"}

    # Scale overlap threshold relative to principle size so short principles
    # (4-6 tokens) can still be invalidated. Minimum 2 overlapping tokens.
    overlap_threshold = max(2, len(principle_tokens) // 3)

    for correction in recent_corrections:
        desc = correction.get("description", "")
        desc_tokens = _tokenise(desc)

        overlap = len(principle_tokens & desc_tokens)
        has_reversal = bool(desc_tokens & _REVERSAL_WORDS)

        # Significant overlap + reversal language = likely contradiction
        if overlap >= overlap_threshold and has_reversal:
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
    api_key: str | None = None,
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
        api_key: Optional LLM API key for principle synthesis.

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
    discovered = discover_meta_rules(lessons, min_group_size, current_session, api_key=api_key)

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
# Lesson Parsing (for testing with real data)
# ---------------------------------------------------------------------------

def parse_lessons_from_markdown(text: str) -> list[Lesson]:
    """Parse lessons from lessons.md. Delegates to the authoritative parser.

    .. deprecated:: 0.1.0
        Use ``gradata.enhancements.self_improvement.parse_lessons`` directly.
    """
    from gradata.enhancements.self_improvement import parse_lessons
    return parse_lessons(text)


# ---------------------------------------------------------------------------
# Lazy re-exports (break circular import: meta_rules ↔ meta_rules_storage)
# ---------------------------------------------------------------------------


def __getattr__(name: str):  # noqa: N807
    """Lazy-load storage symbols to avoid circular imports."""
    _STORAGE_NAMES = {
        "ensure_table", "save_meta_rules", "load_meta_rules",
        "ensure_super_table", "save_super_meta_rules", "load_super_meta_rules",
        "ensure_meta_table",
    }
    if name in _STORAGE_NAMES:
        import gradata.enhancements.meta_rules_storage as _storage
        obj = getattr(_storage, "ensure_table" if name == "ensure_meta_table" else name)
        globals()[name] = obj
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
