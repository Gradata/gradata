"""
Shared text-processing primitives for the gradata SDK.
=======================================================
SDK LAYER: Package-private utility (prefix ``_``). NOT exported via ``__init__.py``.

This module is the single source of truth for two heuristic constants that were
previously duplicated across ``enhancements/edit_classifier.py`` and
``enhancements/behavioral_extractor.py``:

``_FACTUAL_RE``
    A compiled regex that matches factual tokens: dollar amounts, ISO dates,
    percentages, URLs, and large numbers (3+ digits).  Used by
    ``edit_classifier.classify_edits`` and ``behavioral_extractor.detect_archetype``
    to identify REPLACEMENT_FACTUAL corrections.

    **Scope note — do NOT use for intent_classifier.py**
    ``detection/intent_classifier.py`` defines its *own* ``_FACTUAL_RE`` as a
    *list* of separate compiled patterns (iterated with ``for pat in _FACTUAL_RE``).
    The type is incompatible; collapsing them into a single shared symbol would
    silently break the intent classifier.  Keep them separate.

``_STOP_WORDS``
    A ``set`` of common English function words used by ``edit_classifier`` to
    filter meaningful words from edit diffs.

    **Scope note — do NOT use for similarity.py**
    ``enhancements/similarity.py`` intentionally extends ``_STOP_WORDS`` with
    NLP-specific terms ("change", "changed", "content", "added", "cut", "edit",
    "edits", …) that are noise for TF-IDF similarity but *are* meaningful for
    edit-category classification.  Collapsing them would corrupt the
    ``_meaningful_words`` helper in ``edit_classifier``.  ``similarity.py``
    retains its own ``frozenset``-typed, extended stop-word list.

Drift summary (at extraction time, 2026-04-16)
----------------------------------------------
+---------------------+-------------------+----------------------------------------+
| Site                | Symbol            | Status                                 |
+---------------------+-------------------+----------------------------------------+
| edit_classifier.py  | _FACTUAL_RE       | CANONICAL — extracted here             |
| behavioral_extractor| _FACTUAL_RE       | imports edit_classifier; fallback only |
| intent_classifier   | _FACTUAL_RE       | TYPE MISMATCH (list) — not collapsed   |
| edit_classifier.py  | _STOP_WORDS       | CANONICAL — extracted here             |
| similarity.py       | _STOP_WORDS       | SEMANTIC DRIFT (extended) — not coll. |
+---------------------+-------------------+----------------------------------------+
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Factual-token regex
# ---------------------------------------------------------------------------

_FACTUAL_RE = re.compile(r"(\$[\d,.]+|\d{4}-\d{2}-\d{2}|\d+%|https?://\S+|\b\d{3,}\b)")
"""Match factual tokens: dollar amounts, ISO dates, percentages, URLs, 3+-digit numbers.

Used by edit_classifier and behavioral_extractor.  *Not* compatible with
intent_classifier._FACTUAL_RE (which is a list of patterns, not a single regex).
"""

# ---------------------------------------------------------------------------
# Stop-word set (edit-classification scope)
# ---------------------------------------------------------------------------

_STOP_WORDS: set[str] = {
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
    "shall",
    "should",
    "may",
    "can",
    "could",
    "might",
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
    "about",
    "that",
    "this",
    "it",
    "its",
    "and",
    "or",
    "but",
    "not",
    "no",
    "if",
    "so",
    "than",
    "too",
    "very",
    "s",
    "t",
    "d",
    "ll",
    "ve",
    "re",
    "m",
    "i",
    "you",
    "we",
    "they",
    "he",
    "she",
    "me",
    "my",
    "your",
    "our",
    "their",
    "his",
    "her",
    "us",
    "them",
    "up",
    "out",
    "all",
    "am",
}
"""Common English function words for edit-diff filtering.

*Not* the extended NLP stop-word list in ``similarity.py`` (which adds
domain-specific terms like "change", "added", "cut", etc.).
"""
