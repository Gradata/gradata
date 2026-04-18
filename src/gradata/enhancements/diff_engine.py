"""
Diff Engine — compute structured diffs between draft and final text.
====================================================================
SDK LAYER: Pure stdlib logic by default. Optional sentence-transformer
embedder can be injected via ``compute_diff(..., embedder=...)`` or by
installing the ``embeddings`` extra (``pip install gradata[embeddings]``).

Usage::

    from .diff_engine import compute_diff

    result = compute_diff(draft, final)
    print(result.severity)          # "minor"
    print(result.summary_stats)     # {"lines_added": 2, ...}

    # Opt-in semantic blend (DPO-style preference signal; Rafailov et al.
    # 2023 treat before/after pairs as preference signal, so a semantic
    # delta on the pair is a cheap proxy for preference strength).
    result = compute_diff(draft, final, use_semantic=True)
    print(result.blended_distance)  # 0.3·lev + 0.7·semantic
"""

from __future__ import annotations

import difflib
import logging
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

_log = logging.getLogger("gradata.diff_engine")

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
    semantic_distance: float | None = None
    blended_distance: float | None = None


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


def _analyze_line_opcodes(
    draft_lines: list[str],
    final_lines: list[str],
) -> tuple[list[ChangedSection], dict[str, int]]:
    """Walk line-level SequenceMatcher opcodes once and return sections + stats.

    Combines extraction of :class:`ChangedSection` blocks with per-line
    added/removed/changed counts so we only build the matcher once per diff.

    Args:
        draft_lines: Lines from the original draft (without newlines).
        final_lines: Lines from the final version (without newlines).

    Returns:
        ``(changed_sections, summary_stats)`` where ``summary_stats`` has
        keys ``lines_added``, ``lines_removed``, ``lines_changed``.
    """
    matcher = difflib.SequenceMatcher(None, draft_lines, final_lines, autojunk=False)
    sections: list[ChangedSection] = []
    added = removed = changed = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        sections.append(ChangedSection(
            start_line=j1,
            end_line=j2,
            old_text="\n".join(draft_lines[i1:i2]),
            new_text="\n".join(final_lines[j1:j2]),
        ))

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

    stats = {
        "lines_added": added,
        "lines_removed": removed,
        "lines_changed": changed,
    }
    return sections, stats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Semantic distance (opt-in)
# ---------------------------------------------------------------------------
#
# Levenshtein (and its compression cousin NCD) measure surface edits. Two
# corrections with *identical* character-level distance can have opposite
# semantic direction — e.g. "helpful" → "helpfully" (morphological) vs
# "helpful" → "unhelpful" (polarity flip). The preference-learning lit
# (Rafailov et al. 2023, DPO; Ethayarajh et al. 2024, KTO) treats
# before/after pairs as preference signal, so semantic distance on the pair
# is a principled cheap proxy for preference strength.
#
# We *blend* rather than replace: Levenshtein captures small stylistic surface
# edits (Oliver's signature habits), semantic distance captures meaning
# shifts (actual correction). Default weights: 0.3·lev + 0.7·semantic, chosen
# to put majority weight on meaning while still surfacing high-volume surface
# edits that Oliver does care about. Weights are configurable per-call.
#
# Performance: a single `sentence-transformers` call (all-MiniLM-L6-v2,
# 22M params, 384-dim) is ~5-15 ms on CPU for a correction pair. Callers
# that run correct() hot should pass a cached embedder or opt out with
# `use_semantic=False`.

Embedder = Callable[[Sequence[str]], Sequence[Sequence[float]]]

_DEFAULT_EMBEDDER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_default_embedder_cache: Embedder | None = None
_default_embedder_unavailable = False

# Blend weights — justified in the module docstring above. Must sum to 1.0.
DEFAULT_SEMANTIC_WEIGHT = 0.7
DEFAULT_SURFACE_WEIGHT = 0.3


def _load_default_embedder() -> Embedder | None:
    """Lazy-load sentence-transformers. Returns None if unavailable.

    Caches the loaded model on first call so subsequent corrections reuse it.
    Graceful failure: logs debug and returns None if the dependency is not
    installed — callers must handle None by falling back to surface distance.
    """
    global _default_embedder_cache, _default_embedder_unavailable
    if _default_embedder_cache is not None:
        return _default_embedder_cache
    if _default_embedder_unavailable:
        return None
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        _default_embedder_unavailable = True
        _log.debug(
            "sentence-transformers not installed; semantic distance disabled. "
            "Install with `pip install gradata[embeddings]` to enable.",
        )
        return None
    try:
        model = SentenceTransformer(_DEFAULT_EMBEDDER_MODEL)
    except Exception as exc:  # pragma: no cover - env/network failure
        _default_embedder_unavailable = True
        _log.debug("Default embedder load failed (%s); semantic distance disabled.",
                   exc)
        return None

    def _embed(texts: Sequence[str]) -> Sequence[Sequence[float]]:
        # sentence-transformers returns numpy arrays; convert to plain lists
        # so the math below works on pure Python.
        vecs = model.encode(list(texts))
        return [list(v) for v in vecs]

    _default_embedder_cache = _embed
    return _embed


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine distance in [0.0, 2.0]. 0=identical, 1=orthogonal, 2=opposite.

    We clamp to [0.0, 1.0] downstream for blending so polarity flips saturate
    at the same magnitude as "completely unrelated" — the blended distance is
    a severity proxy, not a similarity score.
    """
    import math

    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    similarity = dot / (norm_a * norm_b)
    return 1.0 - similarity


def compute_semantic_distance(
    before: str,
    after: str,
    embedder: Embedder | None = None,
) -> float | None:
    """Compute cosine distance between sentence-embeddings of ``(before, after)``.

    Args:
        before: The original text (draft).
        after: The corrected text (final).
        embedder: Callable mapping ``list[str] -> list[list[float]]``. If
            ``None``, a shared sentence-transformers model is lazy-loaded
            (requires the ``embeddings`` optional dependency).

    Returns:
        Cosine distance clamped to ``[0.0, 1.0]`` where 0.0 = semantically
        identical, 1.0 = orthogonal or opposite. ``None`` when no embedder
        is available (caller falls back to surface distance).
    """
    if not before and not after:
        return 0.0
    emb = embedder if embedder is not None else _load_default_embedder()
    if emb is None:
        return None
    try:
        vecs = emb([before or "", after or ""])
    except Exception as exc:  # pragma: no cover - runtime embedder failure
        _log.debug("Embedder call failed (%s); semantic distance unavailable.", exc)
        return None
    if len(vecs) < 2:
        return None
    cos_dist = _cosine_distance(vecs[0], vecs[1])
    # Clamp to [0, 1] — cosine distance can range [0, 2] but we use it as a
    # severity proxy blended with [0, 1] Levenshtein.
    return round(max(0.0, min(1.0, cos_dist)), 6)


def combine_distances(
    lev_normalized: float,
    semantic: float,
    *,
    surface_weight: float = DEFAULT_SURFACE_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> float:
    """Linear blend of normalised surface and semantic distances.

    Both inputs must lie in ``[0.0, 1.0]``. The weighted sum is clipped to
    ``[0.0, 1.0]`` for downstream severity classification.

    The default 0.3 / 0.7 split is justified in the module docstring and
    mirrors the preference-learning reasoning (meaning shifts > surface
    style under DPO-style preference signal — Rafailov et al. 2023).
    """
    if abs((surface_weight + semantic_weight) - 1.0) > 1e-6:
        raise ValueError(
            f"Weights must sum to 1.0 (got {surface_weight + semantic_weight}).",
        )
    blended = surface_weight * lev_normalized + semantic_weight * semantic
    return round(max(0.0, min(1.0, blended)), 6)


def compute_diff(
    draft: str,
    final: str,
    *,
    use_semantic: bool = False,
    embedder: Embedder | None = None,
    surface_weight: float = DEFAULT_SURFACE_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> DiffResult:
    """Compute a structured diff between a draft and a final version of text.

    Uses ``difflib.SequenceMatcher`` for the normalised edit distance and
    opcode-based section extraction.  Surface-level logic is pure Python
    stdlib.

    When ``use_semantic=True`` (or ``embedder`` is supplied), also computes a
    sentence-embedding cosine distance and a blended severity score:

        blended = surface_weight · lev_normalized + semantic_weight · semantic

    Motivation: Levenshtein conflates morphological changes ("helpful" →
    "helpfully") with polarity flips ("helpful" → "unhelpful"); the former
    should be low-severity, the latter high-severity. The semantic delta
    separates them. See module docstring for the preference-learning
    justification (Rafailov et al. 2023, DPO).

    When ``use_semantic=True`` but the embedder is unavailable (optional
    dependency missing, load error), ``compute_diff`` gracefully falls back
    to surface-only severity and leaves ``semantic_distance=None``.

    Args:
        draft: The original text (e.g. Claude's first output).
        final: The edited or accepted text (e.g. after human review).
        use_semantic: If True, compute embedding cosine distance and blend.
        embedder: Optional override callable ``Sequence[str] -> Sequence[Sequence[float]]``.
        surface_weight: Blend weight on Levenshtein (default 0.3).
        semantic_weight: Blend weight on semantic distance (default 0.7).

    Returns:
        A :class:`DiffResult` with ``edit_distance``, ``changed_sections``,
        ``severity``, ``summary_stats``, and optionally ``semantic_distance``
        / ``blended_distance`` populated.

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
        if not draft and not final:
            compression_dist = 0.0
        elif not draft or not final:
            compression_dist = 1.0
        else:
            _ab = draft.encode("utf-8") + final.encode("utf-8")
            _ca = len(zlib.compress(draft.encode("utf-8"), level=9))
            _cb = len(zlib.compress(final.encode("utf-8"), level=9))
            _cab = len(zlib.compress(_ab, level=9))
            _maxc = max(_ca, _cb)
            _ncd = (_cab - min(_ca, _cb)) / _maxc if _maxc else 0.0
            compression_dist = round(max(0.0, min(1.0, _ncd)), 6)
    else:
        compression_dist = edit_distance  # NCD unreliable on short texts

    changed_sections, summary_stats = _analyze_line_opcodes(draft_lines, final_lines)

    # Optional semantic distance + blended severity (b009dc0).
    semantic_dist: float | None = None
    blended: float | None = None
    if use_semantic or embedder is not None:
        semantic_dist = compute_semantic_distance(draft, final, embedder=embedder)

    # Severity: prefer blended when semantic is available, else surface logic.
    # Surface logic: compression distance for long texts, edit_distance for short.
    surface_for_severity = (
        compression_dist
        if len(draft) + len(final) >= MIN_COMPRESSION_LENGTH
        else edit_distance
    )
    if semantic_dist is not None:
        blended = combine_distances(
            surface_for_severity, semantic_dist,
            surface_weight=surface_weight, semantic_weight=semantic_weight,
        )
        severity = _classify_severity(blended)
    else:
        severity = _classify_severity(surface_for_severity)

    return DiffResult(
        edit_distance=edit_distance,
        compression_distance=compression_dist,
        changed_sections=changed_sections,
        severity=severity,
        summary_stats=summary_stats,
        semantic_distance=semantic_dist,
        blended_distance=blended,
    )
