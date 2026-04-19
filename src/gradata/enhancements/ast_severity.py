"""AST-Aware Severity Classifier — scores structural deltas by diffing
``ast.dump()`` instead of raw text. Collapses whitespace/comment reformats to
``"as-is"``; up-weights signature/control-flow edits edit-distance misses.
Gated by ast_severity_enabled + language_supported; returns None on parse
fail. Labels mirror diff_engine._SEVERITY_THRESHOLDS. Cutoffs are guesses.
SDK: pure stdlib.
"""

from __future__ import annotations

import ast
import difflib
import os

_ENV_FLAG = "GRADATA_AST_SEVERITY"
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_LANGUAGES = frozenset({"python", "py"})
_EXTENSIONS = (".py", ".pyi")

# (upper-bound, label). Scores >= the final bound become "discarded".
_CUTOFFS: tuple[tuple[float, str], ...] = (
    (0.005, "as-is"),
    (0.15, "minor"),
    (0.35, "moderate"),
    (0.70, "major"),
)


def ast_severity_enabled() -> bool:
    """True when ``GRADATA_AST_SEVERITY`` is set to ``1/true/yes/on``."""
    return os.environ.get(_ENV_FLAG, "").strip().lower() in _TRUTHY


def language_supported(language: str | None = None, path: str | None = None) -> bool:
    """True when language hint or path extension matches a parser we have."""
    if language and language.lower() in _LANGUAGES:
        return True
    return bool(path) and path.lower().endswith(_EXTENSIONS)


def classify_ast_severity(
    before: str,
    after: str,
    language: str = "python",
) -> str | None:
    """Return a severity label from AST diff, or ``None`` to fall back.

    ``None`` means: unsupported language or either side failed to parse.
    Callers MUST treat ``None`` as "use the edit-distance classifier"
    and MUST NOT raise.
    """
    if not language_supported(language=language):
        return None
    try:
        before_dump = ast.dump(ast.parse(before), annotate_fields=True)
        after_dump = ast.dump(ast.parse(after), annotate_fields=True)
    except (SyntaxError, ValueError):
        return None
    score = 1.0 - difflib.SequenceMatcher(None, before_dump, after_dump).ratio()
    for cutoff, label in _CUTOFFS:
        if score < cutoff:
            return label
    return "discarded"
