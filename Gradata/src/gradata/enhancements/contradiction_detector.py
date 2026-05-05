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
"""

from __future__ import annotations

import logging
import re

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
    ("show", "hide"),
    ("show", "conceal"),
    ("start", "stop"),
    ("allow", "block"),
    ("allow", "deny"),
    ("accept", "reject"),
    ("open", "close"),
    ("expand", "collapse"),
    ("attach", "detach"),
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
    ("formal", "casual"),
    ("formal", "informal"),
    ("professional", "casual"),
    ("structured", "freeform"),
    ("strict", "relaxed"),
    ("complex", "simple"),
    ("expanded", "condensed"),
]


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for matching."""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "we",
        "you",
        "they",
        "he",
        "she",
        "and",
        "but",
        "or",
        "not",
        "no",
        "if",
        "then",
        "else",
        "when",
        "while",
        "so",
        "than",
        "too",
        "very",
        "just",
        "also",
        "all",
        "each",
        "every",
        "any",
        "some",
        "only",
    }
)


def _extract_topic_words(text: str) -> set[str]:
    """Extract meaningful topic words (nouns/adjectives), skipping stopwords."""
    return set(_normalize(text).split()) - _STOPWORDS


def _contains_phrase(text: str, phrase: str) -> bool:
    """Word-boundary match — avoids false hits like 'allow' inside 'disallow'."""
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _check_pair_list(
    new_norm: str,
    existing_norm: str,
    pairs: list[tuple[str, str]],
    score: float,
) -> float:
    """Return *score* (clamped to [0.0, 1.0]) if any pair matches on opposite sides, else 0.0."""
    clamped = min(max(score, 0.0), 1.0)
    for left, right in pairs:
        if (_contains_phrase(new_norm, left) and _contains_phrase(existing_norm, right)) or (
            _contains_phrase(new_norm, right) and _contains_phrase(existing_norm, left)
        ):
            return clamped
    return 0.0


def _check_polarity(new_norm: str, existing_norm: str) -> float:
    """Check for polarity contradictions (always vs never)."""
    return _check_pair_list(new_norm, existing_norm, _POLARITY_PAIRS, 0.9)


def _check_negation(new_norm: str, existing_norm: str) -> float:
    """Check for action negation (use vs avoid/don't use)."""
    return _check_pair_list(new_norm, existing_norm, _ACTION_OPPOSITES, 0.85)


def _check_opposite_sentiment(new_norm: str, existing_norm: str) -> float:
    """Check for opposite sentiment on overlapping topics."""
    return _check_pair_list(new_norm, existing_norm, _SENTIMENT_OPPOSITES, 0.7)
