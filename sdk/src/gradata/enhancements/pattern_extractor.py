"""
Pattern Extractor — Surface recurring behavioral patterns from classified edits.
================================================================================
SDK LAYER: Pure logic, no file I/O. Caller supplies classified edits and a scope;
this module groups them into actionable patterns and optionally converts them to
Lesson objects for the self-improvement pipeline.

Typical usage::

    from gradata.enhancements.edit_classifier import EditClassification
    from gradata._scope import RuleScope, build_scope
    from gradata.enhancements.pattern_extractor import extract_patterns, merge_patterns

    edits = [
        EditClassification("tone", "Added hedging language", "minor", (1, 3)),
        EditClassification("tone", "Softened directive phrasing", "minor", (5, 7)),
    ]
    scope = build_scope({"domain": "sales", "task_type": "email_draft"})
    patterns = extract_patterns(edits, scope)
"""

from __future__ import annotations

import copy
import difflib
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from gradata._scope import RuleScope, scope_to_dict
from gradata.enhancements.self_improvement import INITIAL_CONFIDENCE, Lesson, LessonState

if TYPE_CHECKING:
    from gradata.enhancements.edit_classifier import EditClassification

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class ExtractedPattern:
    """A recurring behavioral pattern inferred from a set of classified edits.

    Attributes:
        pattern_text: Human-readable rule derived from the edit descriptions.
            Format: "When writing <category> content: <synthesized rule>"
        category: Edit category this pattern belongs to. One of: tone,
            content, structure, factual, style.
        scope: The RuleScope context where this pattern was observed.
        confidence: Starting confidence score in [0.0, 1.0]. Initialized
            to INITIAL_CONFIDENCE (0.30) and promoted by the self-improvement
            pipeline over subsequent sessions.
        evidence_count: Number of individual edits that contributed to this
            pattern. Higher counts indicate stronger signal.
        source_edits: Brief descriptions of the edits that produced this
            pattern. Preserved for auditability.
    """

    pattern_text: str
    category: str
    scope: RuleScope
    confidence: float
    evidence_count: int
    source_edits: list[str] = field(default_factory=list)
    # Engineering Spec fields (patterns table schema)
    support_count: int = 0        # times this pattern was confirmed by corrections
    opportunity_count: int = 0     # times this pattern could have applied (in-scope outputs)
    contradiction_count: int = 0   # times this pattern was contradicted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_patterns(
    edits: list[EditClassification],
    scope: RuleScope,
    context: dict | None = None,
) -> list[ExtractedPattern]:
    """Group classified edits by category and synthesize behavioral patterns.

    Each category with two or more edits produces one pattern. Single-edit
    categories also produce patterns but carry an evidence_count of 1,
    signalling weaker signal to downstream consumers.

    Args:
        edits: Classified edits from a correction event or diff analysis.
        scope: The context (domain, task type, etc.) where the edits occurred.
        context: Optional extra context dict. Reserved for future enrichment;
            currently unused.

    Returns:
        A list of ExtractedPattern objects sorted by evidence_count descending
        (strongest signal first). Empty list if edits is empty.
    """
    if not edits:
        return []

    # Group edit descriptions by category
    grouped: dict[str, list[str]] = {}
    for edit in edits:
        grouped.setdefault(edit.category, []).append(edit.description)

    patterns: list[ExtractedPattern] = []
    for category, descriptions in grouped.items():
        pattern_text = _synthesize_pattern_text(descriptions, category)
        patterns.append(
            ExtractedPattern(
                pattern_text=pattern_text,
                category=category,
                scope=scope,
                confidence=INITIAL_CONFIDENCE,
                evidence_count=len(descriptions),
                source_edits=list(descriptions),
            )
        )

    # Sort strongest signal first
    patterns.sort(key=lambda p: p.evidence_count, reverse=True)
    return patterns


def merge_patterns(
    existing: list[ExtractedPattern],
    new: list[ExtractedPattern],
    similarity_threshold: float = 0.6,
) -> list[ExtractedPattern]:
    """Merge newly extracted patterns into an existing pattern list.

    A new pattern is merged with an existing one when ALL of the following
    hold:

    * Same category.
    * Same scope (all five RuleScope fields match).
    * Text similarity (SequenceMatcher ratio) >= similarity_threshold.

    On a match the existing pattern is updated in-place:

    * evidence_count is incremented by the new pattern's evidence_count.
    * source_edits are extended (duplicates preserved for auditability).
    * confidence is nudged upward: += 0.05 per merge, capped at 1.0.

    Unmatched new patterns are appended as-is.

    Args:
        existing: Current pattern list (may be empty).
        new: Patterns extracted from the latest correction session.
        similarity_threshold: Minimum SequenceMatcher ratio to consider two
            pattern texts as describing the same behavioral rule. Default 0.6.

    Returns:
        The merged pattern list. The input lists are not mutated.
    """
    # Deep-copy all existing patterns so callers are never surprised by mutation.
    # deepcopy handles the mutable source_edits list correctly.
    merged: list[ExtractedPattern] = [copy.deepcopy(p) for p in existing]

    for incoming in new:
        match_idx = _find_match(merged, incoming, similarity_threshold)
        if match_idx is not None:
            target = merged[match_idx]
            target.evidence_count += incoming.evidence_count
            target.source_edits.extend(incoming.source_edits)
            target.confidence = round(min(1.0, target.confidence + 0.05), 2)
        else:
            merged.append(incoming)

    return merged


def patterns_to_lessons(patterns: list[ExtractedPattern]) -> list[Lesson]:
    """Convert ExtractedPattern objects to Lesson objects.

    Bridges the pattern extractor into the self-improvement pipeline so that
    patterns discovered from edit analysis can be tracked, promoted, and
    eventually graduated to RULE status.

    Mapping:
        * pattern.category -> lesson.category (uppercased)
        * pattern.pattern_text -> lesson.description
        * pattern.confidence -> lesson.confidence
        * state = LessonState.INSTINCT (all new patterns start here)
        * date = today (ISO format)
        * root_cause is synthesized from scope fields for traceability

    Args:
        patterns: Patterns to convert. Empty list returns empty list.

    Returns:
        A list of Lesson objects, one per pattern.
    """
    today = date.today().isoformat()
    lessons: list[Lesson] = []

    for pattern in patterns:
        scope_dict = scope_to_dict(pattern.scope)
        root_cause = _format_root_cause(scope_dict, pattern.evidence_count)

        # Serialize scope into the lesson so rules are scoped, not universal
        import json as _json
        scope_str = _json.dumps(scope_dict) if scope_dict else ""

        lessons.append(
            Lesson(
                date=today,
                state=LessonState.INSTINCT,
                confidence=pattern.confidence,
                category=pattern.category.upper(),
                description=pattern.pattern_text,
                root_cause=root_cause,
                scope_json=scope_str,
            )
        )

    return lessons


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _synthesize_pattern_text(descriptions: list[str], category: str) -> str:
    """Combine a list of edit descriptions into a single rule-like statement.

    Joins descriptions into one concise sentence with the canonical prefix
    "When writing <category> content: <rule>", avoiding the redundant
    phrasing "content content" when category is itself "content".

    For a single description the rule is used verbatim (lowercased + stripped).
    For multiple descriptions they are joined with "; " to capture all signals
    while keeping the output a single sentence.

    Args:
        descriptions: Non-empty list of edit description strings.
        category: The edit category shared by all descriptions.

    Returns:
        A single-sentence pattern string.
    """
    if not descriptions:
        return f"When writing {category}: review carefully"

    # Build prefix — avoid "content content" when category == "content"
    prefix = "When writing content" if category == "content" else f"When writing {category} content"

    if len(descriptions) == 1:
        rule = descriptions[0].strip().rstrip(".")
        return f"{prefix}: {rule.lower()}"

    # Normalise and join all descriptions, removing trailing punctuation
    parts = [d.strip().rstrip(".").lower() for d in descriptions]
    rule = "; ".join(parts)
    return f"{prefix}: {rule}"


def _find_match(
    existing: list[ExtractedPattern],
    incoming: ExtractedPattern,
    threshold: float,
) -> int | None:
    """Find the index of a matching pattern in the existing list.

    A match requires identical category, identical scope, and text similarity
    above the threshold.

    Args:
        existing: Current pattern list to search.
        incoming: The new pattern to match against.
        threshold: Minimum SequenceMatcher ratio for text similarity.

    Returns:
        Index of the best-matching pattern, or None if no match is found.
    """
    best_idx: int | None = None
    best_ratio: float = 0.0

    for idx, candidate in enumerate(existing):
        if candidate.category != incoming.category:
            continue
        if candidate.scope != incoming.scope:
            continue

        ratio = difflib.SequenceMatcher(
            None,
            candidate.pattern_text,
            incoming.pattern_text,
        ).ratio()

        if ratio >= threshold and ratio > best_ratio:
            best_ratio = ratio
            best_idx = idx

    return best_idx


def _format_root_cause(scope_dict: dict[str, str], evidence_count: int) -> str:
    """Build a root-cause string from scope fields and evidence count.

    Args:
        scope_dict: Serialized scope fields.
        evidence_count: How many edits contributed to this pattern.

    Returns:
        A compact, human-readable root cause string. Empty string if all
        scope fields are blank and evidence_count is 1.
    """
    non_empty = {k: v for k, v in scope_dict.items() if v}
    if not non_empty and evidence_count <= 1:
        return ""

    parts: list[str] = [f"{k}={v}" for k, v in non_empty.items()]
    parts.append(f"evidence_count={evidence_count}")
    return ", ".join(parts)
