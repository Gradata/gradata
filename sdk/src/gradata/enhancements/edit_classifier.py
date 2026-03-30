"""
Edit Classifier — 5-category classification of text diffs.
===========================================================
SDK LAYER: Layer 1 (enhancements). Pure Python heuristics.

Classifies changed sections from a DiffResult into:
  FACTUAL  — numbers, dates, names, URLs changed
  STYLE    — punctuation, formatting (em dashes, bold, colons)
  STRUCTURE — reordering, line breaks, heading/list changes
  TONE     — hedging words, formality, sentiment markers
  CONTENT  — substantive information (default for anything else)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from gradata.enhancements.diff_engine import DiffResult


@dataclass
class EditClassification:
    """A single classified edit from a diff."""
    category: str       # TONE | CONTENT | STRUCTURE | FACTUAL | STYLE
    confidence: float   # 0.0-1.0
    severity: str       # inherited from DiffResult.severity
    description: str    # human-readable summary


# ---------------------------------------------------------------------------
# Heuristic keyword sets
# ---------------------------------------------------------------------------

_FACTUAL_RE = re.compile(
    r"(\$[\d,.]+|\d{4}-\d{2}-\d{2}|\d+%|https?://\S+|\b\d{3,}\b)"
)

_STYLE_CHARS = set("—–-:;,.'\"*_`~()[]{}!?")

_TONE_WORDS = {
    "actually", "just", "really", "basically", "honestly",
    "perhaps", "maybe", "possibly", "might", "could",
    "I think", "I believe", "I feel", "in my opinion",
    "very", "extremely", "quite", "rather", "somewhat",
    "sorry", "unfortunately", "please", "kindly",
}

_STRUCTURE_MARKERS = re.compile(
    r"^(\s*[-*+]\s|\s*\d+[.)]\s|\s*#{1,6}\s|</?[a-z])", re.MULTILINE
)


def _word_set(text: str) -> set[str]:
    """Extract lowercase words from text."""
    return set(re.findall(r"\b[a-z]+\b", text.lower()))


def _classify_section(old_text: str, new_text: str, severity: str) -> EditClassification:
    """Classify a single changed section."""
    old_lower = old_text.lower()
    new_lower = new_text.lower()

    # FACTUAL: numbers, dates, URLs changed
    old_facts = set(_FACTUAL_RE.findall(old_text))
    new_facts = set(_FACTUAL_RE.findall(new_text))
    if old_facts != new_facts and (old_facts or new_facts):
        changed = (old_facts - new_facts) | (new_facts - old_facts)
        return EditClassification(
            category="FACTUAL",
            confidence=0.85,
            severity=severity,
            description=f"Changed factual content: {', '.join(list(changed)[:3])}",
        )

    # STYLE: mostly punctuation/formatting changes
    old_words = _word_set(old_text)
    new_words = _word_set(new_text)
    word_diff = len(old_words.symmetric_difference(new_words))
    char_diff = sum(1 for a, b in zip(old_text, new_text) if a != b)
    is_punctuation_heavy = (
        word_diff <= 2
        and char_diff > 0
        and char_diff <= max(5, len(old_text) * 0.15)
    )
    if is_punctuation_heavy:
        return EditClassification(
            category="STYLE",
            confidence=0.75,
            severity=severity,
            description="Punctuation or formatting change",
        )

    # STRUCTURE: same words but different arrangement
    if old_words == new_words and old_text.strip() != new_text.strip():
        return EditClassification(
            category="STRUCTURE",
            confidence=0.80,
            severity=severity,
            description="Content reordered or reformatted",
        )

    # STRUCTURE: heading/list markers changed
    old_markers = len(_STRUCTURE_MARKERS.findall(old_text))
    new_markers = len(_STRUCTURE_MARKERS.findall(new_text))
    if abs(old_markers - new_markers) >= 2:
        return EditClassification(
            category="STRUCTURE",
            confidence=0.70,
            severity=severity,
            description="List or heading structure changed",
        )

    # TONE: hedging/formality words added or removed
    tone_added = sum(1 for w in _TONE_WORDS if w in new_lower and w not in old_lower)
    tone_removed = sum(1 for w in _TONE_WORDS if w in old_lower and w not in new_lower)
    if tone_added + tone_removed >= 2:
        direction = "softened" if tone_added > tone_removed else "strengthened"
        return EditClassification(
            category="TONE",
            confidence=0.70,
            severity=severity,
            description=f"Tone {direction} ({tone_added} added, {tone_removed} removed)",
        )

    # CONTENT: default for substantive changes
    added = new_words - old_words
    removed = old_words - new_words
    desc_parts = []
    if added:
        desc_parts.append(f"added: {', '.join(list(added)[:5])}")
    if removed:
        desc_parts.append(f"removed: {', '.join(list(removed)[:5])}")
    return EditClassification(
        category="CONTENT",
        confidence=0.60,
        severity=severity,
        description=f"Content change ({'; '.join(desc_parts) if desc_parts else 'modified'})",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_edits(diff: DiffResult) -> list[EditClassification]:
    """Classify each changed section in a DiffResult.

    Returns one EditClassification per changed section.
    Empty list if no changes detected.
    """
    if not diff.changed_sections:
        return []

    return [
        _classify_section(
            section.old_text,
            section.new_text,
            diff.severity,
        )
        for section in diff.changed_sections
    ]


def summarize_edits(classifications: list[EditClassification]) -> str:
    """Produce a human-readable summary of edit classifications.

    Example: "3 edits: 2 TONE (minor), 1 CONTENT (moderate)"
    """
    if not classifications:
        return ""

    counts: Counter[str] = Counter()
    severities: dict[str, str] = {}
    for c in classifications:
        counts[c.category] += 1
        severities[c.category] = c.severity  # last wins (all same for now)

    parts = [
        f"{count} {cat} ({severities.get(cat, 'unknown')})"
        for cat, count in counts.most_common()
    ]
    total = sum(counts.values())
    return f"{total} edit{'s' if total != 1 else ''}: {', '.join(parts)}"
