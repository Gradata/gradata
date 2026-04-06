"""
Semantic Contradiction Detector — catch rules that fight each other.
====================================================================
SDK LAYER: Layer 1 (enhancements). Imports from _types only.

Before a lesson graduates from INSTINCT to PATTERN (or PATTERN to RULE),
this module checks whether the new rule contradicts any existing graduated
rules. Uses keyword-based heuristic detection (no embeddings needed).

Contradiction types detected:
  - POLARITY: "always X" vs "never X"
  - NEGATION: "use X" vs "don't use X" / "avoid X"
  - OPPOSITE_ACTION: "include X" vs "remove X" / "exclude X"
  - TOPIC_CONFLICT: Same topic keywords with opposing sentiment

If contradictions are found with confidence > 0.7, the lesson is flagged
as PENDING_REVIEW instead of graduating automatically.

OPEN SOURCE: Detection heuristics are open. Embedding-based semantic
similarity is proprietary cloud-side (medium-term).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("gradata.contradiction_detector")

# ---------------------------------------------------------------------------
# Contradiction Patterns
# ---------------------------------------------------------------------------

# Polarity pairs: if rule A says "always X" and rule B says "never X"
_POLARITY_PAIRS: list[tuple[str, str]] = [
    ("always", "never"),
    ("must", "must not"),
    ("must", "never"),
    ("required", "forbidden"),
    ("mandatory", "optional"),
]

# Action opposites: "use X" vs "avoid X"
_ACTION_OPPOSITES: list[tuple[str, str]] = [
    ("use", "avoid"),
    ("use", "don't use"),
    ("use", "do not use"),
    ("include", "exclude"),
    ("include", "remove"),
    ("include", "omit"),
    ("add", "remove"),
    ("add", "don't add"),
    ("add", "do not add"),
    ("enable", "disable"),
    ("prefer", "avoid"),
    ("keep", "remove"),
    ("keep", "drop"),
    ("keep", "delete"),
]

# Sentiment opposites on same topic
_SENTIMENT_OPPOSITES: list[tuple[str, str]] = [
    ("good", "bad"),
    ("correct", "incorrect"),
    ("right", "wrong"),
    ("before", "after"),
    ("first", "last"),
    ("more", "less"),
    ("increase", "decrease"),
    ("long", "short"),
    ("detailed", "brief"),
    ("verbose", "concise"),
]


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for matching."""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def _extract_topic_words(text: str) -> set[str]:
    """Extract meaningful topic words (nouns/adjectives), skipping stopwords."""
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "it", "its", "this", "that", "these", "those", "i", "we", "you",
        "they", "he", "she", "and", "but", "or", "not", "no", "if", "then",
        "else", "when", "while", "so", "than", "too", "very", "just", "also",
        "all", "each", "every", "any", "some", "only",
    }
    words = set(_normalize(text).split())
    return words - stopwords


def _check_polarity(new_norm: str, existing_norm: str) -> float:
    """Check for polarity contradictions (always vs never)."""
    for pos, neg in _POLARITY_PAIRS:
        if pos in new_norm and neg in existing_norm:
            return 0.9
        if neg in new_norm and pos in existing_norm:
            return 0.9
    return 0.0


def _check_negation(new_norm: str, existing_norm: str) -> float:
    """Check for action negation (use vs avoid/don't use)."""
    for action, opposite in _ACTION_OPPOSITES:
        # New rule uses action, existing uses opposite (or vice versa)
        if action in new_norm and opposite in existing_norm:
            return 0.85
        if opposite in new_norm and action in existing_norm:
            return 0.85
    return 0.0


def _check_opposite_sentiment(new_norm: str, existing_norm: str) -> float:
    """Check for opposite sentiment on overlapping topics."""
    for pos, neg in _SENTIMENT_OPPOSITES:
        if pos in new_norm and neg in existing_norm:
            return 0.7
        if neg in new_norm and pos in existing_norm:
            return 0.7
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_contradictions(
    new_rule: str,
    existing_rules: list[dict],
) -> list[dict]:
    """Check if a new rule contradicts existing graduated rules.

    Uses keyword-based heuristic detection:
    - "always X" vs "never X" (polarity)
    - "use X" vs "don't use X" / "avoid X" (negation)
    - Opposite sentiment on same topic

    Args:
        new_rule: The new rule text to check.
        existing_rules: List of dicts with at minimum 'description' and
            'category' keys. May also have 'confidence' and 'state'.

    Returns:
        List of {existing_rule, contradiction_type, confidence} dicts.
        Empty list if no contradictions found.
    """
    if not new_rule or not existing_rules:
        return []

    new_norm = _normalize(new_rule)
    new_topics = _extract_topic_words(new_rule)
    contradictions: list[dict] = []

    for rule in existing_rules:
        desc = rule.get("description", "")
        if not desc:
            continue

        existing_norm = _normalize(desc)
        existing_topics = _extract_topic_words(desc)

        # Must share at least one topic word to be a potential contradiction
        topic_overlap = new_topics & existing_topics
        if not topic_overlap:
            continue

        # Topic overlap ratio for weighting
        overlap_ratio = len(topic_overlap) / max(
            1, min(len(new_topics), len(existing_topics))
        )

        # Check each contradiction type
        best_type = ""
        best_confidence = 0.0

        polarity = _check_polarity(new_norm, existing_norm)
        if polarity > best_confidence:
            best_confidence = polarity
            best_type = "POLARITY"

        negation = _check_negation(new_norm, existing_norm)
        if negation > best_confidence:
            best_confidence = negation
            best_type = "NEGATION"

        sentiment = _check_opposite_sentiment(new_norm, existing_norm)
        if sentiment > best_confidence:
            best_confidence = sentiment
            best_type = "OPPOSITE_SENTIMENT"

        if best_confidence > 0.0:
            # Weight by topic overlap — more shared topics = higher confidence
            weighted_confidence = round(best_confidence * min(1.0, overlap_ratio + 0.3), 2)
            contradictions.append({
                "existing_rule": rule,
                "contradiction_type": best_type,
                "confidence": weighted_confidence,
                "shared_topics": sorted(topic_overlap),
            })

    # Sort by confidence descending
    contradictions.sort(key=lambda c: c["confidence"], reverse=True)
    return contradictions


