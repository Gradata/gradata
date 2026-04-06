"""Context-aware rule ranker with effectiveness and recency weighting."""

from __future__ import annotations

import math
from typing import Any


def rank_rules(
    rules: list[dict[str, Any]],
    *,
    current_session: int,
    task_type: str | None = None,
    context_keywords: list[str] | None = None,
    effectiveness: dict[str, dict[str, Any]] | None = None,
    max_rules: int = 10,
) -> list[dict[str, Any]]:
    """Rank rules by composite score and return top *max_rules*.

    Weighted formula (sums to 1.0):
        30% scope match
        25% confidence
        20% context relevance
        15% recency
        10% fire count

    Plus effectiveness bonus/penalty (clamped to [0, 1]).
    """
    if not rules:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for rule in rules:
        score = _score_rule(
            rule,
            current_session=current_session,
            task_type=task_type,
            context_keywords=context_keywords,
            effectiveness=effectiveness,
        )
        scored.append((score, rule))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rule for _, rule in scored[:max_rules]]


# ------------------------------------------------------------------
# Internal scoring helpers
# ------------------------------------------------------------------

def _score_rule(
    rule: dict[str, Any],
    *,
    current_session: int,
    task_type: str | None,
    context_keywords: list[str] | None,
    effectiveness: dict[str, dict[str, Any]] | None,
) -> float:
    scope = _scope_match(rule.get("category", ""), task_type)
    confidence = float(rule.get("confidence", 0.5))
    context = _context_relevance(rule.get("description", ""), context_keywords)
    recency = _recency_score(rule.get("last_session", 0), current_session)
    fire = _fire_count_score(rule.get("fire_count", 0))

    base = (
        0.30 * scope
        + 0.25 * confidence
        + 0.20 * context
        + 0.15 * recency
        + 0.10 * fire
    )

    bonus = _effectiveness_bonus(rule, effectiveness)
    return max(0.0, min(1.0, base + bonus))


def _scope_match(category: str, task_type: str | None) -> float:
    if task_type is None:
        return 0.5
    cat = category.upper()
    tt = task_type.upper()
    if cat == tt:
        return 1.0
    # Partial match: category is substring or vice-versa
    if cat in tt or tt in cat:
        return 0.7
    return 0.5


def _context_relevance(description: str, keywords: list[str] | None) -> float:
    if not keywords:
        return 0.0
    desc_lower = description.lower()
    hits = sum(1 for kw in keywords if kw.lower() in desc_lower)
    return hits / len(keywords)


def _recency_score(last_session: int, current_session: int) -> float:
    sessions_ago = max(0, current_session - last_session)
    return 1.0 / (1.0 + sessions_ago * 0.1)


def _fire_count_score(fire_count: int) -> float:
    return min(1.0, math.log1p(fire_count) / 5.0)


def _effectiveness_bonus(
    rule: dict[str, Any],
    effectiveness: dict[str, dict[str, Any]] | None,
) -> float:
    if not effectiveness:
        return 0.0
    # Try rule_id first (matches SessionHistory keys), fall back to description
    rule_id = rule.get("id") or rule.get("description", "")
    info = effectiveness.get(rule_id)
    if info is None:
        return 0.0
    if info.get("effective"):
        # Flat bonus for rules proven effective this session.
        # SessionHistory tracks effective/corrected booleans, not
        # session counts, so a fixed +0.10 is appropriate.
        return 0.10
    return -0.10
