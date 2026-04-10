"""
Diff Engine — compute structured diffs between draft and final text.
====================================================================
SDK LAYER: Pure stdlib logic. No file I/O, no external dependencies.

Usage::

    from gradata.enhancements.diff_engine import compute_diff

    result = compute_diff(draft, final)
    print(result.severity)          # "minor"
    print(result.summary_stats)     # {"lines_added": 2, ...}
"""

from __future__ import annotations

import difflib
import zlib
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class ChangedSection:
    """A contiguous block of lines that differ between draft and final.

    Attributes:
        start_line: 0-based line index in the *final* text where the change
            begins.
        end_line: 0-based line index in the *final* text where the change
            ends (exclusive).
        old_text: The original content from the draft.
        new_text: The replacement content in the final.
    """

    start_line: int
    end_line: int
    old_text: str
    new_text: str


@dataclass
class DiffResult:
    """Full comparison result between a draft and a final version of text.

    Attributes:
        edit_distance: Normalised Levenshtein-style ratio in the range
            ``[0.0, 1.0]``.  ``0.0`` means identical; ``1.0`` means
            completely different.
        compression_distance: LZ77-based normalized compression distance
            in the range ``[0.0, 1.0]``. Better correlated with actual
            human editing effort than Levenshtein (Devatine & Abraham, 2024).
            Captures block operations (paragraph moves, section restructuring)
            that character-level edit distance misses.
        changed_sections: List of discrete changed blocks extracted from the
            unified diff.
        severity: Human label derived from ``compression_distance`` (primary)
            with ``edit_distance`` as tiebreaker:

            * ``"as-is"``    — distance < 0.02
            * ``"minor"``    — distance < 0.10
            * ``"moderate"`` — distance < 0.30
            * ``"major"``    — distance < 0.60
            * ``"discarded"``— distance >= 0.60

        summary_stats: Aggregate line counts with keys ``lines_added``,
            ``lines_removed``, and ``lines_changed``.
    """

    edit_distance: float
    compression_distance: float
    changed_sections: list[ChangedSection]
    severity: str
    summary_stats: dict[str, int]
    semantic_similarity: float | None = None


# ---------------------------------------------------------------------------
# Severity thresholds
# ---------------------------------------------------------------------------

_SEVERITY_THRESHOLDS: list[tuple[float, str]] = [
    (0.02, "as-is"),
    (0.10, "minor"),
    (0.30, "moderate"),
    (0.80, "major"),  # Was 0.60 — too many real corrections were "discarded"
]


def _classify_severity(edit_distance: float) -> str:
    """Map a normalised edit distance to a severity label.

    Args:
        edit_distance: Value in ``[0.0, 1.0]``.

    Returns:
        One of ``"as-is"``, ``"minor"``, ``"moderate"``, ``"major"``,
        or ``"discarded"``.
    """
    for threshold, label in _SEVERITY_THRESHOLDS:
        if edit_distance < threshold:
            return label
    return "discarded"


# ---------------------------------------------------------------------------
# Semantic severity adjustment
# ---------------------------------------------------------------------------

_SEVERITY_DOWNGRADE: dict[str, str] = {
    "discarded": "major",
    "major": "moderate",
    "moderate": "minor",
    "minor": "as-is",
}

_SEMANTIC_DOWNGRADE_THRESHOLD = 0.85


def adjust_severity_by_semantics(
    result: DiffResult,
    semantic_similarity: float,
    threshold: float = _SEMANTIC_DOWNGRADE_THRESHOLD,
) -> DiffResult:
    """Downgrade severity by one level when semantic similarity is high."""
    new_severity = result.severity
    if semantic_similarity >= threshold and result.severity in _SEVERITY_DOWNGRADE:
        new_severity = _SEVERITY_DOWNGRADE[result.severity]

    return DiffResult(
        edit_distance=result.edit_distance,
        compression_distance=result.compression_distance,
        changed_sections=result.changed_sections,
        severity=new_severity,
        summary_stats=result.summary_stats,
        semantic_similarity=semantic_similarity,
    )


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _extract_changed_sections(
    draft_lines: list[str],
    final_lines: list[str],
) -> list[ChangedSection]:
    """Extract contiguous changed blocks from a unified diff.

    Uses ``difflib.SequenceMatcher`` opcodes to identify replace/insert/
    delete operations and converts them into :class:`ChangedSection` objects.

    Args:
        draft_lines: Lines from the original draft (without newlines).
        final_lines: Lines from the final version (without newlines).

    Returns:
        List of :class:`ChangedSection` instances, one per contiguous change
        block.  Empty list when the texts are identical.
    """
    matcher = difflib.SequenceMatcher(None, draft_lines, final_lines, autojunk=False)
    sections: list[ChangedSection] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        old_text = "\n".join(draft_lines[i1:i2])
        new_text = "\n".join(final_lines[j1:j2])

        sections.append(
            ChangedSection(
                start_line=j1,
                end_line=j2,
                old_text=old_text,
                new_text=new_text,
            )
        )

    return sections


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------


def _compute_summary_stats(
    draft_lines: list[str],
    final_lines: list[str],
) -> dict[str, int]:
    """Count added, removed, and changed lines.

    A line present only in ``final_lines`` is *added*; a line present only
    in ``draft_lines`` is *removed*; a replace opcode contributes to
    *changed* (the smaller of the two side lengths is counted as changed,
    the remainder as added or removed).

    Args:
        draft_lines: Lines from the original draft.
        final_lines: Lines from the final version.

    Returns:
        Dictionary with keys ``lines_added``, ``lines_removed``, and
        ``lines_changed``.
    """
    added = 0
    removed = 0
    changed = 0

    matcher = difflib.SequenceMatcher(None, draft_lines, final_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_count = i2 - i1
        new_count = j2 - j1
        if tag == "insert":
            added += new_count
        elif tag == "delete":
            removed += old_count
        elif tag == "replace":
            shared = min(old_count, new_count)
            changed += shared
            if new_count > old_count:
                added += new_count - old_count
            elif old_count > new_count:
                removed += old_count - new_count

    return {
        "lines_added": added,
        "lines_removed": removed,
        "lines_changed": changed,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _compression_distance(a: str, b: str) -> float:
    """Compute normalized compression distance (NCD) using zlib (LZ77).

    NCD captures block operations (paragraph moves, section restructuring)
    that character-level edit distance misses. Highly correlated with
    actual human editing effort (Devatine & Abraham, Dec 2024, arXiv:2412.17321).

    Formula: NCD(a, b) = (C(ab) - min(C(a), C(b))) / max(C(a), C(b))
    where C(x) is the compressed length of x.

    Returns a value in [0.0, 1.0]. 0.0 = identical, 1.0 = completely different.
    """
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0

    a_bytes = a.encode("utf-8")
    b_bytes = b.encode("utf-8")
    ab_bytes = a_bytes + b_bytes

    ca = len(zlib.compress(a_bytes, level=9))
    cb = len(zlib.compress(b_bytes, level=9))
    cab = len(zlib.compress(ab_bytes, level=9))

    min_c = min(ca, cb)
    max_c = max(ca, cb)

    if max_c == 0:
        return 0.0

    ncd = (cab - min_c) / max_c
    return round(max(0.0, min(1.0, ncd)), 6)


def compute_diff(draft: str, final: str) -> DiffResult:
    """Compute a structured diff between a draft and a final version of text.

    Uses ``difflib.SequenceMatcher`` for the normalised edit distance and
    opcode-based section extraction.  All logic is pure Python stdlib — no
    external dependencies.

    Args:
        draft: The original text (e.g. Claude's first output).
        final: The edited or accepted text (e.g. after human review).

    Returns:
        A :class:`DiffResult` with ``edit_distance``, ``changed_sections``,
        ``severity``, and ``summary_stats`` populated.

    Example::

        result = compute_diff("hello world", "hello brave new world")
        assert result.severity == "moderate"
        assert result.edit_distance > 0.0
    """
    draft_lines = draft.splitlines()
    final_lines = final.splitlines()

    # Normalised similarity ratio: 1.0 = identical, 0.0 = nothing in common.
    # We invert to get edit_distance where 0.0 = identical.
    similarity = difflib.SequenceMatcher(None, draft, final, autojunk=False).ratio()
    edit_distance = round(1.0 - similarity, 6)

    # Compression distance: better correlated with human editing effort.
    # Uses zlib (LZ77) to capture block operations that Levenshtein misses.
    # Caveat: NCD is unreliable on short texts (<200 chars) due to zlib overhead.
    # For short texts, fall back to edit_distance. For long texts, use NCD as
    # primary with edit_distance as tiebreaker.
    MIN_COMPRESSION_LENGTH = 200
    if len(draft) + len(final) >= MIN_COMPRESSION_LENGTH:
        compression_dist = _compression_distance(draft, final)
    else:
        compression_dist = edit_distance  # NCD unreliable on short texts

    changed_sections = _extract_changed_sections(draft_lines, final_lines)
    # Severity: use compression distance for long texts, edit_distance for short.
    # Blended approach avoids NCD's short-text weakness while capturing
    # block operations on real documents.
    if len(draft) + len(final) >= MIN_COMPRESSION_LENGTH:
        severity = _classify_severity(compression_dist)
    else:
        severity = _classify_severity(edit_distance)
    summary_stats = _compute_summary_stats(draft_lines, final_lines)

    return DiffResult(
        edit_distance=edit_distance,
        compression_distance=compression_dist,
        changed_sections=changed_sections,
        severity=severity,
        summary_stats=summary_stats,
    )
