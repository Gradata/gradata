"""
Pattern Extractor — extract repeating patterns from classified edits.
=====================================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

When brain.correct() classifies edits, this module looks for repeating
patterns across those classifications. Patterns that accumulate enough
evidence become candidate lessons via patterns_to_lessons().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gradata._types import CorrectionType, Lesson, LessonState

if TYPE_CHECKING:
    from gradata._edit_classifier import EditClassification
    from gradata.enhancements.edit_classifier import EditClassification

# Try to import EditClassification from the real module, fall back to shim
try:
    pass
except ImportError:
    pass  # type: ignore[assignment]

INITIAL_CONFIDENCE = 0.40  # Aligned with self_improvement.py (authoritative)
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
    "it", "its", "this", "that", "these", "those",
})


@dataclass
class ExtractedPattern:
    """A detected repeating pattern from classified edits."""
    category: str
    description: str
    confidence: float
    edits: list = field(default_factory=list)


def _keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text."""
    words = set(re.findall(r"\b[a-z]{3,}\b", text.lower()))
    return words - _STOPWORDS


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def extract_patterns(
    classifications: list[EditClassification],
    *,
    scope: object | None = None,
) -> list[ExtractedPattern]:
    """Extract repeating patterns from classified edits.

    Groups classifications by category, then finds clusters of similar
    descriptions within each group using keyword overlap (Jaccard > 0.3).
    Minimum 2 similar edits required to form a pattern.

    Args:
        classifications: Output from classify_edits().
        scope: Optional RuleScope for metadata (stored but not used in matching).

    Returns:
        List of detected patterns. Empty if fewer than 2 similar edits.
    """
    if not classifications:
        return []

    # Group by category
    by_category: dict[str, list[EditClassification]] = {}
    for c in classifications:
        by_category.setdefault(c.category, []).append(c)

    patterns: list[ExtractedPattern] = []

    for category, edits in by_category.items():
        if len(edits) < 2:
            continue

        # Cluster edits by keyword overlap
        keyword_sets = [_keywords(e.description) for e in edits]
        used: set[int] = set()

        for i in range(len(edits)):
            if i in used:
                continue
            cluster = [i]
            for j in range(i + 1, len(edits)):
                if j in used:
                    continue
                if _jaccard(keyword_sets[i], keyword_sets[j]) >= 0.3:
                    cluster.append(j)
                    used.add(j)

            if len(cluster) >= 2:
                used.update(cluster)
                cluster_edits = [edits[k] for k in cluster]
                # Synthesize description from common keywords
                common = keyword_sets[cluster[0]]
                for k in cluster[1:]:
                    common = common & keyword_sets[k]
                desc = (
                    f"Repeated {category.lower()} pattern"
                    + (f" involving: {', '.join(sorted(common)[:5])}" if common else "")
                )
                patterns.append(ExtractedPattern(
                    category=category,
                    description=desc,
                    confidence=min(0.50, 0.20 + 0.10 * len(cluster)),
                    edits=cluster_edits,
                ))

    return patterns


def merge_patterns(
    existing: list[ExtractedPattern],
    new: list[ExtractedPattern],
) -> list[ExtractedPattern]:
    """Merge new patterns into existing ones by category + keyword overlap.

    Patterns with same category and Jaccard > 0.5 on descriptions are merged.
    Merged patterns accumulate evidence (higher confidence, combined edits).
    New unique patterns are appended as-is.
    """
    merged = list(existing)

    for np in new:
        np_keys = _keywords(np.description)
        found = False
        for ep in merged:
            if ep.category != np.category:
                continue
            ep_keys = _keywords(ep.description)
            if _jaccard(np_keys, ep_keys) >= 0.5:
                # Merge: boost confidence, combine edits
                ep.confidence = min(1.0, ep.confidence + 0.05 * len(np.edits))
                ep.edits.extend(np.edits)
                found = True
                break
        if not found:
            merged.append(np)

    return merged


# Category -> CorrectionType mapping
_CATEGORY_TYPE_MAP: dict[str, CorrectionType] = {
    "FACTUAL": CorrectionType.FACTUAL,
    "TONE": CorrectionType.PREFERENCE,
    "STYLE": CorrectionType.PREFERENCE,
    "STRUCTURE": CorrectionType.BEHAVIORAL,
    "CONTENT": CorrectionType.BEHAVIORAL,
}


def patterns_to_lessons(patterns: list[ExtractedPattern]) -> list[Lesson]:
    """Convert patterns with sufficient evidence into candidate Lesson objects.

    New lessons start as INSTINCT at INITIAL_CONFIDENCE (0.40).
    Only patterns with confidence >= 0.25 are promoted.
    """
    from datetime import date

    lessons: list[Lesson] = []
    today = date.today().isoformat()

    for pattern in patterns:
        if pattern.confidence < 0.25:
            continue

        lessons.append(Lesson(
            date=today,
            state=LessonState.INSTINCT,
            confidence=INITIAL_CONFIDENCE,
            category=pattern.category.upper(),
            description=pattern.description,
            correction_type=_CATEGORY_TYPE_MAP.get(
                pattern.category.upper(), CorrectionType.BEHAVIORAL
            ),
        ))

    return lessons