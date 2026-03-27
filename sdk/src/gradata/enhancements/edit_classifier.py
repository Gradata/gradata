"""
Edit Classifier — rule-based classification of diff sections.
=============================================================
SDK LAYER: Pure stdlib logic. No LLM, no file I/O, no external dependencies.

Consumes a :class:`~gradata.enhancements.diff_engine.DiffResult` and emits a list of
:class:`EditClassification` objects, one per changed section, describing
*what kind* of edit was made.

Usage::

    from gradata.enhancements.diff_engine import compute_diff
    from gradata.enhancements.edit_classifier import classify_edits, summarize_edits

    diff = compute_diff(draft, final)
    classifications = classify_edits(diff)
    print(summarize_edits(classifications))
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.enhancements.diff_engine import DiffResult

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class EditClassification:
    """Classification of a single changed section.

    Attributes:
        category: The type of edit.  One of ``"tone"``, ``"content"``,
            ``"structure"``, ``"factual"``, or ``"style"``.
        description: Brief human-readable explanation of what changed.
        severity: Edit severity: ``"minor"``, ``"moderate"``, or ``"major"``.
        line_range: Tuple of ``(start_line, end_line)`` referencing the
            final text.  Both values are 0-based; ``end_line`` is exclusive.
    """

    category: str  # tone, content, structure, factual, style, clarity, coherence, fluency
    description: str
    severity: str
    line_range: tuple[int, int]


# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

# Tone markers: politeness, hedging, formality shifts
_TONE_ADDED_WORDS: frozenset[str] = frozenset(
    {
        "please", "kindly", "appreciate", "thank", "thanks", "sorry",
        "apologies", "unfortunately", "regret", "would", "could", "might",
        "perhaps", "possibly", "potentially", "seemingly", "apparently",
        "I think", "I believe", "I feel", "in my opinion",
    }
)
_TONE_REMOVED_WORDS: frozenset[str] = frozenset(
    {
        "please", "kindly", "appreciate", "thank", "thanks", "sorry",
        "apologies", "unfortunately", "regret", "would", "could", "might",
        "perhaps", "possibly", "potentially", "seemingly", "apparently",
    }
)

# Structure markers: headings, bullets, horizontal rules, block quotes
_STRUCTURE_RE = re.compile(
    r"^(?:#{1,6}\s|[-*+]\s|\d+\.\s|>\s|={3,}|-{3,}|\|)",
    re.MULTILINE,
)

# Factual markers: numbers, URLs, proper-noun-like tokens (capitalised words)
# Matches: plain integers/decimals, percentages, currency shorthand (100k, 2M, $500K)
_NUMBER_RE = re.compile(r"[$£€]?\d[\d,._/%-]*[kKmMbBtT]?\b")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
# Matches capitalised words that appear *mid-sentence* — i.e. preceded by a
# non-sentence-boundary character (not start-of-string or ". /! /? ").
# This avoids false positives from sentence-initial capitalisation.
_PROPER_NOUN_RE = re.compile(r"(?<=[a-z,;:)\]]) [A-Z][a-zA-Z]{2,}\b")

# Combined set of all tone words (lower-cased) to exclude from proper-noun detection
_ALL_TONE_WORDS: frozenset[str] = frozenset(
    w.lower()
    for phrase in ["please", "kindly", "appreciate", "thank", "thanks", "sorry", "apologies", "unfortunately", "regret", "would", "could", "might", "perhaps", "possibly", "potentially", "seemingly", "apparently"]
    for w in [phrase]
)

# Style-only markers: detect pure whitespace / punctuation / capitalisation
# changes — i.e. changes that produce identical text when normalised.
_WHITESPACE_NORM_RE = re.compile(r"\s+")
_PUNCTUATION_STRIP_RE = re.compile(r"[^\w\s]")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Strip punctuation, collapse whitespace, and lower-case text.

    Used to test whether two strings differ only in style (whitespace,
    punctuation, capitalisation).

    Args:
        text: Raw text to normalise.

    Returns:
        Normalised string.
    """
    text = _PUNCTUATION_STRIP_RE.sub("", text)
    text = _WHITESPACE_NORM_RE.sub(" ", text)
    return text.strip().lower()


def _words(text: str) -> set[str]:
    """Return the set of lowercase word tokens in *text*.

    Args:
        text: Input string.

    Returns:
        Set of lowercase word strings (alphabetic only, length >= 2).
    """
    return {w.lower() for w in re.findall(r"[a-zA-Z]{2,}", text)}


def _detect_tone(old: str, new: str) -> bool:
    """Return ``True`` if the change looks like a tone shift.

    A tone shift is detected when:
    - A politeness/hedging word was added to or removed from the text, or
    - The ratio of uppercase-starting sentences changed meaningfully (formal
      vs informal register detection is approximated this way).

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        ``True`` if the heuristic detects a tone shift.
    """
    old_words = _words(old)
    new_words = _words(new)
    added_words = new_words - old_words
    removed_words = old_words - new_words

    if added_words & _TONE_ADDED_WORDS:
        return True
    return bool(removed_words & _TONE_REMOVED_WORDS)


def _detect_structure(old: str, new: str) -> bool:
    """Return ``True`` if the change involves structural markdown elements.

    Looks for headings, bullets, numbered lists, block quotes, or horizontal
    rules appearing or disappearing between ``old`` and ``new``.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        ``True`` if a structural change is detected.
    """
    old_structure = bool(_STRUCTURE_RE.search(old))
    new_structure = bool(_STRUCTURE_RE.search(new))
    # Either side has structural markers and they differ
    if old_structure != new_structure:
        return True
    # Both have structure but the marker count differs (reordering)
    old_count = len(_STRUCTURE_RE.findall(old))
    new_count = len(_STRUCTURE_RE.findall(new))
    return old_count != new_count


def _detect_factual(old: str, new: str) -> bool:
    """Return ``True`` if the change contains a factual difference.

    Factual changes include: numbers changed, URLs added/removed, or proper
    nouns (capitalised multi-character tokens) added or removed.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        ``True`` if a factual change is detected.
    """
    if _NUMBER_RE.findall(old) != _NUMBER_RE.findall(new):
        return True
    old_urls = set(_URL_RE.findall(old))
    new_urls = set(_URL_RE.findall(new))
    if old_urls != new_urls:
        return True
    old_proper = {
        w for w in _PROPER_NOUN_RE.findall(old) if w.lower() not in _ALL_TONE_WORDS
    }
    new_proper = {
        w for w in _PROPER_NOUN_RE.findall(new) if w.lower() not in _ALL_TONE_WORDS
    }
    return old_proper != new_proper


def _detect_style_only(old: str, new: str) -> bool:
    """Return ``True`` when the change is style-only.

    A style-only change produces identical normalised text — i.e. only
    whitespace, punctuation, or capitalisation changed.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        ``True`` if the texts are semantically identical after normalisation.
    """
    return bool(old.strip() or new.strip()) and _normalise(old) == _normalise(new)


def _detect_clarity(old: str, new: str) -> bool:
    """Return ``True`` if the change improves readability without changing meaning.

    Clarity edits are the MOST COMMON edit type (Grammarly IteraTeR, ACL 2022)
    yet were previously invisible, misclassified as "content."

    Signals: sentence splitting, simplification (shorter words replacing longer),
    removing jargon, adding explanatory phrases. Key differentiator from content:
    the information set is the same, just expressed more clearly.
    """
    # If normalised forms are identical, it's style not clarity
    if _normalise(old) == _normalise(new):
        return False

    old_words = _words(old)
    new_words = _words(new)

    # Same information test: high word overlap (>70%) suggests rewording, not new info
    if not old_words or not new_words:
        return False
    overlap = len(old_words & new_words)
    union = len(old_words | new_words)
    jaccard = overlap / union if union > 0 else 0

    if jaccard < 0.5:
        return False  # Too much change — probably content, not clarity

    # Sentence splitting: more sentences in new than old
    old_sentences = len(re.split(r'[.!?]+', old.strip()))
    new_sentences = len(re.split(r'[.!?]+', new.strip()))
    if new_sentences > old_sentences and jaccard > 0.6:
        return True

    # Simplification: average word length decreased
    old_avg = sum(len(w) for w in old_words) / max(len(old_words), 1)
    new_avg = sum(len(w) for w in new_words) / max(len(new_words), 1)
    if new_avg < old_avg - 0.5 and jaccard > 0.6:
        return True

    return False


# Single-word only — multi-word phrases can't match via set intersection
# with _words() which returns individual tokens.
_COHERENCE_TRANSITION_WORDS: frozenset[str] = frozenset({
    "however", "therefore", "moreover", "furthermore", "consequently",
    "additionally", "nevertheless", "meanwhile", "specifically",
    "conversely", "nonetheless", "accordingly",
})


def _detect_coherence(old: str, new: str) -> bool:
    """Return ``True`` if the change improves logical flow between ideas.

    Coherence edits add transitions, reorder arguments for better flow,
    or add connecting phrases. Different from structure (which is about
    formatting — headings, bullets) and content (which adds new information).

    Signals: transition words added, sentence reordering with same content.
    Uses a conservative word list (no common words like "first", "then", "also")
    to avoid false positives on normal prose changes.
    """

    old_words = _words(old)
    new_words = _words(new)
    added_words = new_words - old_words

    # Transition words added
    if added_words & _COHERENCE_TRANSITION_WORDS:
        # But only if overall content is similar (not a full rewrite)
        overlap = len(old_words & new_words)
        if overlap > len(old_words) * 0.5:
            return True

    return False


def _detect_fluency(old: str, new: str) -> bool:
    """Return ``True`` if the change fixes grammar or awkward phrasing.

    Fluency edits fix grammatical errors, improve word choice for natural
    reading, or smooth out awkward constructions. Different from style
    (which is only whitespace/punctuation/case) and tone (which shifts
    register/formality).

    Key distinction from style: style changes produce identical normalised
    text. Fluency changes produce DIFFERENT normalised text but preserve
    meaning.
    """
    # If normalised forms are identical, it's style not fluency
    if _normalise(old) == _normalise(new):
        return False

    old_words = _words(old)
    new_words = _words(new)

    # Very high overlap but different words = word choice / grammar fix
    if not old_words or not new_words:
        return False
    overlap = len(old_words & new_words)
    changed = len(old_words.symmetric_difference(new_words))

    # Fluency: small number of word changes, high overlap
    if changed <= 3 and overlap > len(old_words) * 0.7:
        return True

    return False


def _detect_content(old: str, new: str) -> bool:
    """Return ``True`` if information was added or removed.

    Uses line-count change as the primary signal: any net addition or
    removal of lines indicates content change.  Also fires when meaningful
    word-level content shifts that are not captured by factual/tone checks.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        ``True`` if a content change is detected.
    """
    old_lines = [ln for ln in old.splitlines() if ln.strip()]
    new_lines = [ln for ln in new.splitlines() if ln.strip()]
    if len(old_lines) != len(new_lines):
        return True
    old_words = _words(old)
    new_words = _words(new)
    sym_diff = old_words.symmetric_difference(new_words)
    return len(sym_diff) > 2


# ---------------------------------------------------------------------------
# Section-level severity
# ---------------------------------------------------------------------------


def _section_severity(old: str, new: str, diff_severity: str) -> str:
    """Derive a per-section severity label.

    Falls back to the overall diff severity when the section is small;
    otherwise caps at ``"major"`` since sections rarely span the full
    document change magnitude.

    Args:
        old: Old text for this section.
        new: New text for this section.
        diff_severity: The overall :class:`~gradata.enhancements.diff_engine.DiffResult`
            severity label.

    Returns:
        One of ``"minor"``, ``"moderate"``, or ``"major"``.
    """
    old_len = len(old.split())
    new_len = len(new.split())
    delta = abs(new_len - old_len)

    if diff_severity in ("as-is", "minor") or delta <= 3:
        return "minor"
    if diff_severity == "moderate" or delta <= 15:
        return "moderate"
    return "major"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_edits(diff: DiffResult) -> list[EditClassification]:
    """Classify each changed section in *diff* by edit category.

    Applies a priority-ordered rule chain to each :class:`ChangedSection`:

    1. **style** — pure whitespace / punctuation / capitalisation change
    2. **factual** — number, URL, or proper-noun change
    3. **structure** — heading / bullet / list reordering
    4. **tone** — politeness or hedging word shift
    5. **content** — everything else (information added or removed)

    Args:
        diff: A :class:`~gradata.enhancements.diff_engine.DiffResult` as returned by
            :func:`~gradata.enhancements.diff_engine.compute_diff`.

    Returns:
        List of :class:`EditClassification` instances, one per changed
        section.  Returns an empty list when there are no changed sections.

    Example::

        diff = compute_diff(draft, final)
        classes = classify_edits(diff)
        for c in classes:
            print(c.category, c.description)
    """
    if not diff.changed_sections:
        return []

    results: list[EditClassification] = []

    for section in diff.changed_sections:
        old = section.old_text
        new = section.new_text
        line_range = (section.start_line, section.end_line)
        severity = _section_severity(old, new, diff.severity)

        # Priority-ordered rule chain (8 categories):
        # 1. style: pure formatting (catches capitalisation-only before anything else)
        # 2. factual: numbers, URLs, proper nouns changed (highest semantic impact)
        # 3. structure: headings, bullets, lists reordered
        # 4. tone: politeness or hedging word shift
        # 5. fluency: grammar fix / word choice (small changes, high overlap)
        # 6. clarity: rewording for readability (same meaning, clearer expression)
        # 7. coherence: logical flow improvement (transitions, reordering)
        # 8. content: everything else (information added or removed)
        #
        # New categories (fluency, clarity, coherence) based on IteraTeR
        # taxonomy (Grammarly, ACL 2022). Clarity is the most common edit type
        # across all domains — previously invisible, misclassified as "content."
        if _detect_style_only(old, new):
            category = "style"
            description = "Whitespace, punctuation, or capitalisation adjusted"
        elif _detect_factual(old, new):
            category = "factual"
            description = _build_factual_description(old, new)
        elif _detect_structure(old, new):
            category = "structure"
            description = _build_structure_description(old, new)
        elif _detect_tone(old, new):
            category = "tone"
            description = _build_tone_description(old, new)
        elif _detect_fluency(old, new):
            category = "fluency"
            description = "Grammar or word choice improved"
        elif _detect_clarity(old, new):
            category = "clarity"
            description = "Rewording for readability (meaning preserved)"
        elif _detect_coherence(old, new):
            category = "coherence"
            description = "Logical flow improved (transitions or reordering)"
        else:
            category = "content"
            description = _build_content_description(old, new)

        results.append(
            EditClassification(
                category=category,
                description=description,
                severity=severity,
                line_range=line_range,
            )
        )

    return results


def summarize_edits(classifications: list[EditClassification]) -> str:
    """Produce a single-line human-readable summary of all classifications.

    Counts occurrences of each category and formats them as a comma-separated
    sentence.  Returns a default message when the list is empty.

    Args:
        classifications: List of :class:`EditClassification` as returned by
            :func:`classify_edits`.

    Returns:
        A one-line string, e.g.
        ``"2 content edit(s), 1 tone edit(s), 1 style edit(s)."``.

    Example::

        summary = summarize_edits(classify_edits(diff))
        print(summary)  # "3 content edit(s), 1 factual edit(s)."
    """
    if not classifications:
        return "No edits detected."

    counts: dict[str, int] = {}
    for c in classifications:
        counts[c.category] = counts.get(c.category, 0) + 1

    # Canonical ordering for consistent output
    order = ["content", "factual", "tone", "structure", "clarity", "coherence", "fluency", "style"]
    parts = [
        f"{counts[cat]} {cat} edit(s)"
        for cat in order
        if cat in counts
    ]
    # Append any unexpected categories not in the canonical list
    for cat, cnt in counts.items():
        if cat not in order:
            parts.append(f"{cnt} {cat} edit(s)")

    return ", ".join(parts) + "."


# ---------------------------------------------------------------------------
# Description builders
# ---------------------------------------------------------------------------


def _build_factual_description(old: str, new: str) -> str:
    """Build a concise description of a factual change.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        Human-readable description string.
    """
    old_nums = _NUMBER_RE.findall(old)
    new_nums = _NUMBER_RE.findall(new)
    if old_nums != new_nums:
        return "Numeric value(s) changed"

    old_urls = set(_URL_RE.findall(old))
    new_urls = set(_URL_RE.findall(new))
    if old_urls != new_urls:
        return "URL(s) added or removed"

    old_proper = {
        w for w in _PROPER_NOUN_RE.findall(old) if w.lower() not in _ALL_TONE_WORDS
    }
    new_proper = {
        w for w in _PROPER_NOUN_RE.findall(new) if w.lower() not in _ALL_TONE_WORDS
    }
    added = new_proper - old_proper
    removed = old_proper - new_proper
    if added or removed:
        parts: list[str] = []
        if added:
            parts.append(f"added: {', '.join(sorted(added)[:3])}")
        if removed:
            parts.append(f"removed: {', '.join(sorted(removed)[:3])}")
        return "Proper noun(s) changed — " + "; ".join(parts)

    return "Factual content changed"


def _build_structure_description(old: str, new: str) -> str:
    """Build a concise description of a structural change.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        Human-readable description string.
    """
    old_has = bool(_STRUCTURE_RE.search(old))
    new_has = bool(_STRUCTURE_RE.search(new))
    if not old_has and new_has:
        return "Structural formatting added (heading, list, or rule)"
    if old_has and not new_has:
        return "Structural formatting removed"
    return "Structural elements reordered or modified"


def _build_tone_description(old: str, new: str) -> str:
    """Build a concise description of a tone change.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        Human-readable description string.
    """
    old_words = _words(old)
    new_words = _words(new)
    added = new_words - old_words
    removed = old_words - new_words

    added_tone = added & _TONE_ADDED_WORDS
    removed_tone = removed & _TONE_REMOVED_WORDS

    if added_tone and not removed_tone:
        return f"Softer/more polite tone — added: {', '.join(sorted(added_tone)[:3])}"
    if removed_tone and not added_tone:
        return f"More direct tone — removed: {', '.join(sorted(removed_tone)[:3])}"
    return "Tone adjusted (formality or hedging shift)"


def _build_content_description(old: str, new: str) -> str:
    """Build a concise description of a content change.

    Args:
        old: Old text block.
        new: New text block.

    Returns:
        Human-readable description string.
    """
    old_lines = [ln for ln in old.splitlines() if ln.strip()]
    new_lines = [ln for ln in new.splitlines() if ln.strip()]
    delta = len(new_lines) - len(old_lines)

    if delta > 0:
        return f"Content added ({delta} line(s) net)"
    if delta < 0:
        return f"Content removed ({abs(delta)} line(s) net)"

    old_words = _words(old)
    new_words = _words(new)
    sym_diff_count = len(old_words.symmetric_difference(new_words))
    return f"Content revised ({sym_diff_count} word(s) changed)"
