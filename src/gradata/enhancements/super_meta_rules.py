"""
Super-Meta-Rule Logic — tier-2 and tier-3 principle emergence.
==============================================================
Discovers super-meta-rules from groups of related meta-rules (Rosch 1978:
subordinate / basic / superordinate).  All SQLite persistence lives in
``meta_rules_storage.py``; core meta-rule logic lives in ``meta_rules.py``.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from gradata.enhancements.meta_rules import (
    MetaRule,
    SuperMetaRule,
    TIER_SUPER_META,
    TIER_UNIVERSAL,
    _classify_meta_transfer_scope,
    _detect_themes,
)


# ---------------------------------------------------------------------------
# Super-Meta-Rule Helpers
# ---------------------------------------------------------------------------

def _super_meta_id(meta_rule_ids: list[str]) -> str:
    """Deterministic super-meta-rule ID from sorted source meta-rule IDs."""
    canonical = "|".join(sorted(meta_rule_ids))
    return "SMETA-" + hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _merge_context_weights(metas: list[MetaRule] | list[SuperMetaRule] | list[MetaRule | SuperMetaRule]) -> dict[str, float]:
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


def _synthesise_super_principle(metas: list[MetaRule] | list[SuperMetaRule] | list[MetaRule | SuperMetaRule], tier: int) -> str:
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
# Super-Meta-Rule Discovery (category + theme)
# ---------------------------------------------------------------------------


def detect_super_meta_rules(
    meta_rules: list[MetaRule],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[SuperMetaRule]:
    """Discover tier-2 super-meta-rules from groups of related meta-rules.

    Uses both category overlap and theme detection as grouping strategies.

    Args:
        meta_rules: All currently active meta-rules.
        min_group_size: Minimum group size to form a super-meta-rule.
        current_session: Current session number.

    Returns:
        List of tier-2 :class:`SuperMetaRule` objects.
    """
    if len(meta_rules) < min_group_size:
        return []

    results: list[SuperMetaRule] = []
    seen_ids: set[str] = set()

    # Strategy 1: category overlap
    cat_groups = _group_meta_rules_by_category_overlap(meta_rules)
    for _label, group in cat_groups.items():
        if len(group) >= min_group_size:
            smeta = _build_super_meta(group, TIER_SUPER_META, current_session)
            if smeta.id not in seen_ids:
                seen_ids.add(smeta.id)
                results.append(smeta)

    # Strategy 2: theme overlap
    theme_groups = _group_meta_rules_by_theme(meta_rules)
    for _theme, group in theme_groups.items():
        if len(group) >= min_group_size:
            smeta = _build_super_meta(group, TIER_SUPER_META, current_session)
            if smeta.id not in seen_ids:
                seen_ids.add(smeta.id)
                results.append(smeta)

    results.sort(key=lambda s: s.confidence, reverse=True)
    return results


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


def format_super_meta_rules(
    supers: list[SuperMetaRule],
    context: str | None = None,
    condition_context: dict[str, object] | None = None,
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
    # Deferred import to avoid circular dependency at module load time
    from gradata.enhancements.meta_rules import evaluate_conditions

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
