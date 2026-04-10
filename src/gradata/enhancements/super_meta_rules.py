"""
Super-Meta-Rule Logic — tier-2 and tier-3 principle emergence.
==============================================================
Super-meta-rule discovery requires Gradata Cloud.  The open-source SDK
preserves the data model and formatting API; discovery and refresh are
no-ops that return empty results.

All SQLite persistence lives in ``meta_rules_storage.py``; core
meta-rule logic lives in ``meta_rules.py``.
"""

from __future__ import annotations

import logging

from gradata.enhancements.meta_rules import (
    TIER_SUPER_META,
    TIER_UNIVERSAL,
    MetaRule,
    SuperMetaRule,
    evaluate_conditions,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discovery (requires Gradata Cloud)
# ---------------------------------------------------------------------------


def detect_super_meta_rules(
    meta_rules: list[MetaRule],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[SuperMetaRule]:
    """Discover tier-2 super-meta-rules from groups of related meta-rules.

    Requires Gradata Cloud.  Returns empty list in open-source build.

    Args:
        meta_rules: All currently active meta-rules.
        min_group_size: Minimum group size to form a super-meta-rule.
        current_session: Current session number.

    Returns:
        Empty list (discovery requires Gradata Cloud).
    """
    _log.info("Super-meta-rule discovery requires Gradata Cloud")
    return []


def detect_universal_rules(
    super_metas: list[SuperMetaRule],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[SuperMetaRule]:
    """Discover tier-3 universal principles from super-meta-rules.

    Requires Gradata Cloud.  Returns empty list in open-source build.

    Args:
        super_metas: All current tier-2 super-meta-rules.
        min_group_size: Minimum group size.
        current_session: Current session number.

    Returns:
        Empty list (discovery requires Gradata Cloud).
    """
    _log.info("Universal rule discovery requires Gradata Cloud")
    return []


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


def refresh_super_meta_rules(
    meta_rules: list[MetaRule],
    existing_supers: list[SuperMetaRule],
    current_session: int = 0,
    min_group_size: int = 3,
) -> list[SuperMetaRule]:
    """Re-discover super-meta-rules, keeping valid existing ones.

    In the open-source build, this validates existing super-meta-rules
    but does not discover new ones.

    Args:
        meta_rules: All currently active meta-rules.
        existing_supers: Previously discovered super-meta-rules.
        current_session: Current session number.
        min_group_size: Minimum group size (unused in open-source build).

    Returns:
        Validated subset of *existing_supers*.
    """
    _log.info("Super-meta-rule refresh requires Gradata Cloud")
    valid: list[SuperMetaRule] = []
    for smeta in existing_supers:
        if validate_super_meta_rule(smeta, meta_rules):
            smeta.last_validated_session = current_session
            valid.append(smeta)
    valid.sort(key=lambda s: s.confidence, reverse=True)
    return valid


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_super_meta_rules(
    supers: list[SuperMetaRule],
    context: str | None = None,
    condition_context: dict[str, object] | None = None,
) -> str:
    """Format super-meta-rules for injection into LLM context.

    Super-meta-rules go FIRST in the prompt (primacy positioning) as
    they represent the highest-priority generalised principles.

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

    if condition_context is not None:
        supers = [s for s in supers if evaluate_conditions(s, condition_context)]

    if not supers:
        return ""

    if context:
        ctx = context
        weighted: list[tuple[SuperMetaRule, float]] = []
        for s in supers:
            w = s.context_weights.get(ctx, s.context_weights.get("default", 1.0))
            weighted.append((s, s.confidence * w))
        weighted.sort(key=lambda t: t[1], reverse=True)
        supers = [s for s, _ in weighted]

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
