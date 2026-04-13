"""
Meta-Rule Emergence — compound learning through principle discovery.
====================================================================
Meta-rule discovery and synthesis require Gradata Cloud.  The open-source
SDK preserves the full data model, formatting, ranking, validation, and
storage API so that cloud-generated meta-rules work seamlessly.

Discovery, grouping, and synthesis are no-ops in the open-source build.

Public API is fully preserved here via re-exports from:
  - ``meta_rules_storage`` (SQLite persistence)
  - ``super_meta_rules`` (tier-2/3 logic)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field

from gradata._types import Lesson, LessonState, RuleTransferScope

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

# Tier constants (Rosch 1978: subordinate / basic / superordinate)
TIER_SUPER_META = 2  # Super-meta-rule: emerges from 3+ meta-rules
TIER_UNIVERSAL = 3  # Universal principle: emerges from 3+ super-meta-rules


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
    return all(not _eval_single_condition(cond, context) for cond in rule.never_when)


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
# Helpers (kept for compatibility)
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


def _detect_themes(text: str) -> dict[str, int]:
    """Theme detection requires Gradata Cloud."""
    return {}


def _classify_meta_transfer_scope(rule_text: str) -> RuleTransferScope:
    """Transfer scope classification requires Gradata Cloud."""
    return RuleTransferScope.PERSONAL


# ---------------------------------------------------------------------------
# Discovery (requires Gradata Cloud)
# ---------------------------------------------------------------------------


def discover_meta_rules(
    lessons: list[Lesson],
    min_group_size: int = 3,
    current_session: int = 0,
    **kwargs: object,
) -> list[MetaRule]:
    """Scan graduated lessons for emergent meta-rules.

    Meta-rule discovery requires Gradata Cloud.  This open-source
    build returns an empty list.

    Args:
        lessons: All lessons (active + archived).
        min_group_size: Minimum group size to form a meta-rule.
        current_session: Current session number for timestamping.
        **kwargs: Accepts additional keyword arguments for compatibility.

    Returns:
        Empty list (discovery requires Gradata Cloud).
    """
    _log.info("Meta-rule discovery requires Gradata Cloud")
    return []


def merge_into_meta(
    rules: list[Lesson],
    theme_override: str = "",
    session: int = 0,
    **kwargs: object,
) -> MetaRule:
    """Synthesise a group of related rules into one meta-rule.

    Full principle synthesis requires Gradata Cloud.  This open-source
    build returns a placeholder meta-rule with correct IDs, categories,
    and confidence but no synthesised principle.

    Args:
        rules: The grouped lessons.
        theme_override: Theme label (unused in open-source build).
        session: Current session number.
        **kwargs: Accepts additional keyword arguments for compatibility.

    Returns:
        A :class:`MetaRule` with placeholder principle.
    """
    _log.info("Meta-rule synthesis requires Gradata Cloud")
    lesson_ids = [_lesson_id(l) for l in rules]
    mid = _meta_id(lesson_ids)
    categories = sorted(set(l.category for l in rules))
    avg_conf = min(1.0, round(sum(l.confidence for l in rules) / len(rules), 2)) if rules else 0.0
    return MetaRule(
        id=mid,
        principle="(requires Gradata Cloud)",
        source_categories=categories,
        source_lesson_ids=lesson_ids,
        confidence=avg_conf,
        created_session=session,
        last_validated_session=session,
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
        lines.append(f"{i}. [META:{meta.confidence:.2f}|{n} rules|{categories}] {meta.principle}")
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
    **kwargs: object,
) -> list[MetaRule]:
    """Re-discover meta-rules, keeping valid existing ones.

    In the open-source build, this validates and returns existing
    meta-rules but does not discover new ones.  New discovery
    requires Gradata Cloud.

    Args:
        lessons: All lessons (active + archived).
        existing_metas: Previously discovered meta-rules.
        recent_corrections: Corrections from the latest session(s).
        current_session: Current session number.
        min_group_size: Minimum group size (unused in open-source build).
        **kwargs: Accepts additional keyword arguments for compatibility.

    Returns:
        Validated subset of *existing_metas*.
    """
    _log.info("Meta-rule discovery requires Gradata Cloud")
    corrections = recent_corrections or []

    # Validate existing meta-rules (invalidation still works locally)
    valid: list[MetaRule] = []
    for meta in existing_metas:
        if validate_meta_rule(meta, corrections):
            meta.last_validated_session = current_session
            valid.append(meta)

    valid.sort(key=lambda m: m.confidence, reverse=True)
    return valid


# ---------------------------------------------------------------------------
# Cross-Domain Detection
# ---------------------------------------------------------------------------


def detect_cross_domain_candidates(
    lessons: list,
    min_domains: int = 3,
) -> list[dict]:
    """Find rules that appear in 3+ distinct domains — universal candidates.

    Groups graduated rules by their normalised description. Any description
    that appears (across distinct domains) in at least *min_domains* different
    domains is returned as a cross-domain candidate.

    Args:
        lessons: Iterable of :class:`~gradata._types.Lesson` objects. Only
            lessons with a non-empty ``domain`` field in their ``scope_json``
            are considered.
        min_domains: Minimum distinct domain count to qualify (default 3).

    Returns:
        List of dicts, each with keys:
        - ``"description"`` (str): The normalised rule description.
        - ``"domains"`` (list[str]): Distinct domains where the rule appears.
        - ``"avg_confidence"`` (float): Mean confidence across all matching
          lessons.
        - ``"count"`` (int): Total number of matching lessons.
    """
    # Map normalised_description -> list of (domain, confidence) pairs
    groups: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for lesson in lessons:
        # Extract domain from scope_json
        domain = ""
        if lesson.scope_json:
            try:
                scope_data = json.loads(lesson.scope_json)
                domain = scope_data.get("domain", "") or ""
            except (json.JSONDecodeError, TypeError):
                domain = ""

        if not domain:
            continue  # Skip lessons without a domain

        normalised = lesson.description.strip()
        groups[normalised].append((domain, lesson.confidence))

    candidates = []
    for description, entries in groups.items():
        distinct_domains = list({d for d, _ in entries})
        if len(distinct_domains) < min_domains:
            continue

        avg_conf = round(sum(c for _, c in entries) / len(entries), 4)
        candidates.append(
            {
                "description": description,
                "domains": distinct_domains,
                "avg_confidence": avg_conf,
                "count": len(entries),
            }
        )

    return candidates


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
# LLM-Powered Batch Synthesis
# ---------------------------------------------------------------------------


def _resolve_llm_credentials() -> tuple[str, str, str]:
    """Resolve LLM credentials from environment. Returns (key, base, model).

    Delegates to the same env vars used by ``llm_synthesizer``.
    """
    import os

    key = os.environ.get("GRADATA_LLM_KEY", "")
    base = os.environ.get("GRADATA_LLM_BASE", "")
    model = os.environ.get("GRADATA_LLM_MODEL", "gpt-4o-mini")
    return key, base, model


def _call_llm_for_synthesis(
    category: str,
    descriptions: list[str],
    *,
    provider: str = "anthropic",
) -> str:
    """Call the LLM to synthesize lesson descriptions into directives.

    Returns raw JSON string from the LLM.  This function is the seam
    that tests mock -- it isolates all network I/O.

    Raises:
        RuntimeError: On any LLM failure (caller catches).
    """

    key, base, model = _resolve_llm_credentials()
    if not key or not base:
        raise RuntimeError("No LLM credentials configured")

    bullet_text = "\n".join(f"- {d}" for d in descriptions)
    prompt = (
        f'Given these {len(descriptions)} learned rules in the "{category}" category:\n'
        f"{bullet_text}\n\n"
        "Synthesize them into 1-3 high-level actionable directives.\n"
        "Return ONLY a JSON array of objects, each with:\n"
        '  - "directive": a 1-2 sentence actionable principle\n'
        '  - "confidence": float 0.0-1.0 (how strongly supported by the rules)\n'
        "No preamble, no markdown fencing, just the JSON array."
    )

    # Use the same HTTP machinery as llm_synthesizer
    import urllib.request

    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.3,
        }
    ).encode()

    headers = {
        "Content-Type": "application/json",
    }
    # Auth header uses same pattern as llm_synthesizer
    headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        body = json.loads(resp.read().decode())

    return body["choices"][0]["message"]["content"].strip()


def llm_synthesize_rules(
    lessons: list[Lesson],
    provider: str = "anthropic",
    max_lessons: int = 10,
    max_calls: int = 1,
) -> list[dict]:
    """Synthesize graduated lessons into high-level directives via LLM.

    Args:
        lessons: Graduated lessons to synthesize.
        provider: LLM provider (uses existing llm_synthesizer infrastructure).
        max_lessons: Max lessons per synthesis call.
        max_calls: Max LLM calls per invocation (cost cap).

    Returns:
        List of ``{"directive": str, "source_lessons": list[str], "confidence": float}``.

    Falls back to empty list if no API key available or LLM call fails.
    """
    if not lessons:
        return []

    # 1. Filter to only RULE-state lessons
    rule_lessons = [le for le in lessons if le.state == LessonState.RULE]
    if not rule_lessons:
        return []

    # Check for credentials early -- graceful fallback
    key, base, _ = _resolve_llm_credentials()
    if not key or not base:
        _log.debug("llm_synthesize_rules: no LLM credentials, returning empty")
        return []

    # 2. Group by category
    groups: dict[str, list[Lesson]] = defaultdict(list)
    for lesson in rule_lessons:
        groups[lesson.category].append(lesson)

    # Sort categories by group size descending (synthesize largest first)
    sorted_categories = sorted(groups.keys(), key=lambda c: len(groups[c]), reverse=True)

    # 3. For each category group (up to max_calls)
    results: list[dict] = []
    calls_made = 0

    for category in sorted_categories:
        if calls_made >= max_calls:
            break

        group = groups[category]
        capped = group[:max_lessons]
        descriptions = [le.description for le in capped]

        try:
            raw = _call_llm_for_synthesis(
                category=category,
                descriptions=descriptions,
                provider=provider,
            )
            calls_made += 1

            parsed = _parse_synthesis_response(raw, descriptions)
            results.extend(parsed)

        except Exception as exc:
            _log.debug("LLM synthesis failed for category %s: %s", category, exc)
            continue

    return results


def _parse_synthesis_response(
    raw: str,
    source_descriptions: list[str],
) -> list[dict]:
    """Parse LLM JSON response into structured dicts.

    Returns:
        List of ``{"directive": str, "source_lessons": list[str], "confidence": float}``.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _log.debug("Failed to parse LLM synthesis response as JSON")
        return []

    if not isinstance(data, list):
        data = [data]

    results = []
    for item in data:
        if not isinstance(item, dict):
            continue
        directive = item.get("directive", "")
        if not directive:
            continue
        confidence = float(item.get("confidence", 0.8))
        confidence = max(0.0, min(1.0, confidence))

        results.append(
            {
                "directive": directive,
                "source_lessons": list(source_descriptions),
                "confidence": confidence,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Lazy re-exports (break circular import: meta_rules ↔ meta_rules_storage)
# ---------------------------------------------------------------------------


def __getattr__(name: str):
    """Lazy-load storage symbols to avoid circular imports."""
    _STORAGE_NAMES = {
        "ensure_table",
        "save_meta_rules",
        "load_meta_rules",
        "ensure_super_table",
        "save_super_meta_rules",
        "load_super_meta_rules",
        "ensure_meta_table",
    }
    if name in _STORAGE_NAMES:
        import gradata.enhancements.meta_rules_storage as _storage

        obj = getattr(_storage, "ensure_table" if name == "ensure_meta_table" else name)
        globals()[name] = obj
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
