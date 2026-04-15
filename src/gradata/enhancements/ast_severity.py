"""
AST-Aware Severity Classifier.
==============================
SDK LAYER: Pure stdlib logic. No file I/O, no external dependencies.

Motivation
----------
The default severity path (``diff_engine.compute_diff`` /
``sidecar.watcher._classify_severity``) runs on line-level edit distance.
On source code that's noisy: a reformat, quote-style flip, or import
reorder produces a high edit-distance score even though nothing
semantically changed. Conversely, a one-character change to a function
signature has tiny edit distance but a large semantic blast radius.

This module adds an OPTIONAL AST-based path that parses both sides with
Python's built-in ``ast`` module and scores the structural delta instead
of the textual delta. If either side fails to parse, the caller is
expected to fall back to the edit-distance classifier (this module does
NOT raise on parse failure — it returns ``None`` instead).

Gating
------
Callers should only invoke :func:`classify_ast_severity` when:

1. The config flag ``GRADATA_AST_SEVERITY`` is truthy in the environment, AND
2. The file being compared is in a supported language (currently Python).

Enum
----
Returns the same 5-label severity enum used by ``diff_engine``:
``"as-is"``, ``"minor"``, ``"moderate"``, ``"major"``, ``"discarded"``.
(The design brief called these ``trivial/minor/moderate/major/rewrite`` —
we conform to the enum already shipped in ``diff_engine.py`` instead.)

Cutoffs are guesses; they should be tuned empirically against labelled
correction data.
"""

from __future__ import annotations

import ast
import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# These values mirror the labels used by diff_engine._SEVERITY_THRESHOLDS so
# downstream consumers (graduation, edit_classifier, metrics) don't need to
# branch on which classifier was used.
_SEVERITY_AS_IS = "as-is"
_SEVERITY_MINOR = "minor"
_SEVERITY_MODERATE = "moderate"
_SEVERITY_MAJOR = "major"
_SEVERITY_DISCARDED = "discarded"

# AST-score -> severity cutoffs.
#
# These are educated guesses — tune empirically against labelled corrections.
# Rationale for the current numbers:
#   - 0.05   : a rename of one local within a medium function
#   - 0.15   : a handful of statement-level edits in one function
#   - 0.35   : signature or control-flow change touching >1 function
#   - 0.70   : whole-function rewrite / multiple major edits
# Above 0.70 we call it a rewrite (mapped to "discarded" in our enum).
_AST_SEVERITY_CUTOFFS: list[tuple[float, str]] = [
    (0.05, _SEVERITY_AS_IS),
    (0.15, _SEVERITY_MINOR),
    (0.35, _SEVERITY_MODERATE),
    (0.70, _SEVERITY_MAJOR),
]

# Languages we know how to parse. Today: only Python.
_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"python", "py"})

# File extensions we accept as a language hint.
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".py", ".pyi"})

_ENV_FLAG = "GRADATA_AST_SEVERITY"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def ast_severity_enabled() -> bool:
    """Return True when the opt-in env flag is set to a truthy value.

    Truthy = one of ``1``, ``true``, ``yes``, ``on`` (case-insensitive).
    Anything else (including unset) returns False.
    """
    raw = os.environ.get(_ENV_FLAG, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def language_supported(language: str | None = None, path: str | None = None) -> bool:
    """Check whether we can parse this language / file.

    Either a language hint or a file path (whose extension we probe) is
    enough. If both are provided, either matching is sufficient.
    """
    if language and language.lower() in _SUPPORTED_LANGUAGES:
        return True
    if path:
        lower = path.lower()
        for ext in _SUPPORTED_EXTENSIONS:
            if lower.endswith(ext):
                return True
    return False


# ---------------------------------------------------------------------------
# AST scoring
# ---------------------------------------------------------------------------


def _collect_signatures(tree: ast.AST) -> list[tuple[int, str]]:
    """Walk an AST and collect (depth, node-signature) pairs.

    The signature captures a node's type plus attributes likely to encode
    semantic meaning (names, operator class, constant value type). We
    deliberately ignore line/column offsets so formatting changes don't
    register.
    """
    sigs: list[tuple[int, str]] = []

    def _node_sig(node: ast.AST) -> str:
        parts: list[str] = [type(node).__name__]
        # Names carry semantic meaning in refs / defs / attrs / args
        for attr in ("name", "id", "attr", "arg"):
            val = getattr(node, attr, None)
            if isinstance(val, str):
                parts.append(f"{attr}={val}")
        # Constants: record the type of the literal, not the value, so a
        # number tweak registers but is not overweighted.
        if isinstance(node, ast.Constant):
            parts.append(f"const={type(node.value).__name__}")
        # Operators: record the operator class (Add vs Sub etc.)
        for attr in ("op", "ops"):
            val = getattr(node, attr, None)
            if val is None:
                continue
            if isinstance(val, list):
                parts.append(f"{attr}=" + ",".join(type(o).__name__ for o in val))
            else:
                parts.append(f"{attr}={type(val).__name__}")
        return "|".join(parts)

    def _walk(node: ast.AST, depth: int) -> None:
        sigs.append((depth, _node_sig(node)))
        for child in ast.iter_child_nodes(node):
            _walk(child, depth + 1)

    _walk(tree, 0)
    return sigs


def _tree_diff_score(before: str, after: str) -> float | None:
    """Compute a normalised diff score in ``[0.0, 1.0]`` between two Python
    sources, or return ``None`` if either side fails to parse.

    Score = (symmetric-difference of node signatures) / (size of the
    larger signature multiset). Signatures include a depth tag so a node
    that moves between nesting levels still counts as a change.
    """
    try:
        before_tree = ast.parse(before)
        after_tree = ast.parse(after)
    except (SyntaxError, ValueError):
        return None

    before_sigs = _collect_signatures(before_tree)
    after_sigs = _collect_signatures(after_tree)

    # Multiset compare: count each signature on each side.
    from collections import Counter

    before_counts: Counter[tuple[int, str]] = Counter(before_sigs)
    after_counts: Counter[tuple[int, str]] = Counter(after_sigs)

    # Symmetric difference sum: for every key, |before - after|.
    all_keys = set(before_counts) | set(after_counts)
    diff_sum = 0
    for key in all_keys:
        diff_sum += abs(before_counts.get(key, 0) - after_counts.get(key, 0))

    denom = max(len(before_sigs), len(after_sigs))
    if denom == 0:
        return 0.0
    score = diff_sum / denom
    # Clamp: mismatched totals plus depth drift can push slightly above 1.
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def _classify_ast_score(score: float) -> str:
    """Map an AST diff score in ``[0.0, 1.0]`` to a severity label."""
    for cutoff, label in _AST_SEVERITY_CUTOFFS:
        if score < cutoff:
            return label
    return _SEVERITY_DISCARDED


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_ast_severity(
    before: str,
    after: str,
    language: str = "python",
) -> str | None:
    """Classify a correction using AST structural diff instead of edit distance.

    Args:
        before: Source text pre-edit (e.g. what the model wrote).
        after: Source text post-edit (e.g. what the human saved).
        language: Language hint. Only ``"python"`` / ``"py"`` is supported
            today; anything else returns ``None`` so the caller can fall
            back to edit-distance.

    Returns:
        One of ``"as-is"``, ``"minor"``, ``"moderate"``, ``"major"``,
        ``"discarded"`` on success, or ``None`` if the language is
        unsupported or either input fails to parse. Callers should treat
        ``None`` as "fall back to the edit-distance classifier" and MUST
        NOT raise.

    Example::

        sev = classify_ast_severity("x = 1\\n", "x = 1  # comment\\n")
        # -> "as-is": comment delta is a single AST leaf

    Cutoffs (``0.05 / 0.15 / 0.35 / 0.70``) are educated guesses — tune
    against labelled correction data before relying on them in production
    gating.
    """
    if not language_supported(language=language):
        return None
    score = _tree_diff_score(before, after)
    if score is None:
        return None
    return _classify_ast_score(score)
