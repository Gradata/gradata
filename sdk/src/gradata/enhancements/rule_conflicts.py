"""
Rule Conflict Detection -- Updates, Extends, Derives relationships.
====================================================================
SDK LAYER: Layer 1 (enhancements). Imports from _types and diff_engine only.

Stolen from EverMemOS relationship tracking (updates, extends, derives).
Gradata equivalent: detect when a new correction conflicts with, extends,
or forms a pattern with existing graduated rules.

This module complements contradiction_detector.py (which catches polarity/
negation conflicts). rule_conflicts.py goes further by classifying the
*relationship* between corrections and enabling rule evolution.

Usage::

    from gradata.enhancements.rule_conflicts import detect_rule_conflict, RuleRelation

    relation, target = detect_rule_conflict(new_lesson, existing_rules)
    if relation == RuleRelation.UPDATES:
        # New lesson supersedes the target rule
        ...
    elif relation == RuleRelation.EXTENDS:
        # New lesson adds to the target rule
        ...
    elif relation == RuleRelation.DERIVES:
        # Pattern detected across rules -- meta-rule candidate
        ...
"""

from __future__ import annotations

import re
from enum import Enum

from gradata._types import ELIGIBLE_STATES, Lesson
from gradata.enhancements.diff_engine import compute_diff


class RuleRelation(Enum):
    """Relationship between a new lesson and existing rules.

    UPDATES: New correction contradicts an existing rule. The new lesson
        should supersede the old one (user changed their mind).
    EXTENDS: New correction adds nuance to an existing rule. Both should
        coexist, potentially merged into a more complete rule.
    DERIVES: A pattern is detected across multiple rules. This signals
        a meta-rule candidate -- an emergent principle.
    INDEPENDENT: No meaningful relationship detected.
    """
    UPDATES = "updates"
    EXTENDS = "extends"
    DERIVES = "derives"
    INDEPENDENT = "independent"


# ---------------------------------------------------------------------------
# Similarity computation
# ---------------------------------------------------------------------------


def _text_similarity(a: str, b: str) -> float:
    """Compute normalized text similarity using the diff engine.

    Returns a float in [0.0, 1.0] where 1.0 = identical.
    Uses 1 - edit_distance from the compression-aware diff engine.
    """
    if not a or not b:
        return 0.0
    if a.strip().lower() == b.strip().lower():
        return 1.0

    diff = compute_diff(a, b)
    return round(1.0 - diff.edit_distance, 4)


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, excluding stopwords."""
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "it", "its",
        "this", "that", "and", "but", "or", "not", "no", "if", "then",
        "when", "so", "than", "too", "very", "just", "also", "all",
        "each", "every", "any", "some", "only", "i", "we", "you",
        "they", "he", "she", "my", "your", "our", "their",
    }
    words = set(re.sub(r"[^\w\s]", " ", text.lower()).split())
    return words - stopwords


def _detect_opposite_direction(a_desc: str, b_desc: str) -> bool:
    """Check if two descriptions point in opposite directions.

    Heuristic: if one says "use X" and the other says "don't use X"
    or "avoid X", they're opposite.
    """
    a_lower = a_desc.lower()
    b_lower = b_desc.lower()

    # Action opposites
    opposites = [
        ("use", "avoid"), ("use", "don't use"), ("use", "do not use"),
        ("include", "exclude"), ("include", "remove"), ("include", "omit"),
        ("add", "remove"), ("add", "don't add"), ("add", "do not add"),
        ("always", "never"), ("must", "must not"), ("keep", "remove"),
        ("prefer", "avoid"), ("enable", "disable"),
        ("before", "after"), ("first", "last"),
    ]

    for pos, neg in opposites:
        if (pos in a_lower and neg in b_lower) or (neg in a_lower and pos in b_lower):
            return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_rule_conflict(
    new_lesson: Lesson,
    existing_rules: list[Lesson],
    *,
    update_threshold: float = 0.80,
    extend_threshold: float = 0.60,
    derive_min_cluster: int = 3,
) -> tuple[RuleRelation, Lesson | None]:
    """Check if a new lesson conflicts with or extends existing rules.

    Classification logic:
    - UPDATES: similarity > update_threshold AND opposite direction
      (the user changed their mind about a previous correction)
    - EXTENDS: similarity > extend_threshold AND same direction
      (the user is adding nuance to an existing rule)
    - DERIVES: 3+ existing rules share category + keyword overlap
      with the new lesson (meta-rule candidate)
    - INDEPENDENT: no meaningful relationship

    Args:
        new_lesson: The newly created lesson to check.
        existing_rules: List of existing lessons (typically PATTERN/RULE state).
        update_threshold: Minimum similarity for UPDATES classification.
        extend_threshold: Minimum similarity for EXTENDS classification.
        derive_min_cluster: Minimum cluster size for DERIVES.

    Returns:
        Tuple of (relation, target_lesson).
        For UPDATES/EXTENDS, target_lesson is the most similar existing rule.
        For DERIVES, target_lesson is None (the pattern is across multiple).
        For INDEPENDENT, target_lesson is None.
    """
    if not existing_rules:
        return (RuleRelation.INDEPENDENT, None)

    new_desc = new_lesson.description
    new_keywords = _extract_keywords(new_desc)

    best_similarity = 0.0
    best_rule: Lesson | None = None
    category_cluster: list[Lesson] = []

    for rule in existing_rules:
        # Only compare against eligible rules
        if rule.state not in ELIGIBLE_STATES:
            continue

        similarity = _text_similarity(new_desc, rule.description)

        if similarity > best_similarity:
            best_similarity = similarity
            best_rule = rule

        # Track category cluster for DERIVES detection
        if rule.category == new_lesson.category:
            rule_keywords = _extract_keywords(rule.description)
            if new_keywords & rule_keywords:  # At least one shared keyword
                category_cluster.append(rule)

    # UPDATES: high similarity + opposite direction
    if best_rule is not None and best_similarity > update_threshold:
        if _detect_opposite_direction(new_desc, best_rule.description):
            return (RuleRelation.UPDATES, best_rule)

    # EXTENDS: moderate similarity + same direction
    if best_rule is not None and best_similarity > extend_threshold:
        if not _detect_opposite_direction(new_desc, best_rule.description):
            return (RuleRelation.EXTENDS, best_rule)

    # DERIVES: 3+ rules in same category with keyword overlap
    if len(category_cluster) >= derive_min_cluster:
        return (RuleRelation.DERIVES, None)

    return (RuleRelation.INDEPENDENT, None)


def classify_all_relations(
    new_lesson: Lesson,
    existing_rules: list[Lesson],
) -> list[tuple[RuleRelation, Lesson, float]]:
    """Classify the relationship between a new lesson and ALL existing rules.

    Unlike detect_rule_conflict (which returns the primary relationship),
    this function returns a sorted list of all relationships with their
    similarity scores. Useful for building the learning graph.

    Args:
        new_lesson: The newly created lesson.
        existing_rules: All existing lessons to compare against.

    Returns:
        List of (relation, existing_lesson, similarity) tuples,
        sorted by similarity descending. Only includes rules with
        similarity > 0.3.
    """
    results: list[tuple[RuleRelation, Lesson, float]] = []
    new_desc = new_lesson.description

    for rule in existing_rules:
        similarity = _text_similarity(new_desc, rule.description)
        if similarity < 0.3:
            continue

        is_opposite = _detect_opposite_direction(new_desc, rule.description)

        if similarity > 0.80 and is_opposite:
            relation = RuleRelation.UPDATES
        elif similarity > 0.60 and not is_opposite:
            relation = RuleRelation.EXTENDS
        else:
            relation = RuleRelation.INDEPENDENT

        results.append((relation, rule, similarity))

    results.sort(key=lambda x: x[2], reverse=True)
    return results
