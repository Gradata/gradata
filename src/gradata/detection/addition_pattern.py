# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Gradata

"""Signal 4 — Addition pattern detection.

Detects when users repeatedly ADD the same type of content (type annotations,
imports, comments, links) without changing existing text.  After N repetitions,
creates a candidate lesson.
"""

from __future__ import annotations

import ast
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field

# ── Pure addition check ───────────────────────────────────────────────────


def is_addition(old: str, new: str, min_added_chars: int = 10) -> bool:
    """True when *new* contains *old* plus added content (insertion, not replacement).

    - Empty old + non-empty new (>= min_added_chars) counts as addition.
    - Returns False if old changed significantly or added content is too short.
    """
    if not isinstance(min_added_chars, int) or min_added_chars < 0:
        raise ValueError(f"min_added_chars must be a non-negative integer, got {min_added_chars}")

    # Empty old, non-empty new = new file content
    if not old and new and len(new) >= min_added_chars:
        return True

    if not old or not new:
        return False

    # Check if old is a subsequence of new (all chars of old appear in order in new)
    if len(new) < len(old):
        return False

    # Two-pointer subsequence scan
    old_idx = 0
    new_idx = 0
    while old_idx < len(old) and new_idx < len(new):
        if old[old_idx] == new[new_idx]:
            old_idx += 1
        new_idx += 1

    # If we didn't match all of old, it's not a subsequence
    if old_idx < len(old):
        return False

    added = len(new) - len(old)
    return added >= min_added_chars


# ── Structural classification ─────────────────────────────────────────────

# Extension → high-level category
_EXT_CATEGORY: dict[str, str] = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".rs": "rust", ".go": "go", ".java": "java", ".rb": "ruby",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".cs": "csharp",
    ".swift": "swift", ".kt": "kotlin",
    ".md": "markdown", ".txt": "text", ".rst": "restructuredtext",
}

# Regex patterns for non-Python code files
_CODE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("import", re.compile(r"(?:^|\n)\s*(?:import |from .+ import |require\(|#include )")),
    ("type_annotation", re.compile(r":\s*\w+[\w\[\], |]*(?:\s*[=;)]|\s*$)", re.MULTILINE)),
    ("comment", re.compile(r"(?:^|\n)\s*(?://|/\*|#\s)")),
    ("error_handling", re.compile(r"(?:try\s*\{|catch\s*\(|except\s)")),
    ("logging", re.compile(r"(?:console\.(?:log|warn|error)|logger\.|log\.|print\()")),
]

# Regex patterns for text/markdown files
_TEXT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("link", re.compile(r"\[.+?\]\(.+?\)")),
    ("emphasis", re.compile(r"\*\*.+?\*\*")),
    ("list_item", re.compile(r"(?:^|\n)\s*[-*+]\s")),
    ("heading", re.compile(r"(?:^|\n)#{1,6}\s")),
    ("code_block", re.compile(r"```")),
]


def classify_addition(old: str, new: str, file_ext: str) -> tuple[str, str]:
    """Return (category, structural_type) fingerprint for the addition.

    *file_ext* should include the dot, e.g. ``".py"``.
    """
    ext = file_ext.lower()
    category = _EXT_CATEGORY.get(ext, ext.lstrip(".") if ext else "unknown")

    # Extract only the added portion
    if old and old in new:
        idx = new.index(old)
        added_text = new[:idx] + new[idx + len(old):]
    else:
        added_text = new

    # Python: use AST
    if ext in (".py", ".pyi"):
        _stype = "other"
        try:
            _tree = ast.parse(added_text)
        except SyntaxError:
            _tree = None
            if re.search(r"(?:^|\n)\s*(?:import |from .+ import )", added_text):
                _stype = "import"
            elif re.search(r":\s*\w+", added_text):
                _stype = "type_annotation"
            elif re.search(r'""".*?"""|\'\'\'.*?\'\'\'', added_text, re.DOTALL):
                _stype = "docstring"
            elif re.search(r"#\s", added_text):
                _stype = "comment"
        if _tree is not None:
            for _node in ast.walk(_tree):
                if isinstance(_node, (ast.Import, ast.ImportFrom)):
                    _stype = "import"
                    break
                if isinstance(_node, ast.AnnAssign):
                    _stype = "type_annotation"
                    break
                if isinstance(_node, ast.FunctionDef):
                    if _node.returns is not None:
                        _stype = "return_type"
                        break
                    if (_node.body and isinstance(_node.body[0], ast.Expr)
                            and isinstance(_node.body[0].value, ast.Constant)
                            and isinstance(_node.body[0].value.value, str)):
                        _stype = "docstring"
                        break
                if (isinstance(_node, ast.Expr) and isinstance(_node.value, ast.Constant)
                        and isinstance(_node.value.value, str)):
                    _stype = "docstring"
                    break
                if isinstance(_node, ast.Assert):
                    _stype = "assertion"
                    break
            else:
                if re.search(r"(?:^|\n)\s*@\w+", added_text):
                    _stype = "decorator"
        return (category, _stype)

    # Markdown / text files
    if ext in (".md", ".txt", ".rst"):
        for type_name, pattern in _TEXT_PATTERNS:
            if pattern.search(added_text):
                return (category, type_name)
        return (category, "other")

    # Other code files: regex patterns
    if category != "unknown":
        for type_name, pattern in _CODE_PATTERNS:
            if pattern.search(added_text):
                return (category, type_name)

    return (category, "other")


# ── Tracker — accumulates fingerprints, fires lessons ──────────────────────


@dataclass
class _FingerprintCounter:
    """Track occurrences of a fingerprint across sessions."""
    count: int = 0
    sessions: set[str] = field(default_factory=set)


class AdditionTracker:
    """Accumulate addition fingerprints; emit a lesson dict at threshold.

    Args:
        threshold: occurrences in a single session to trigger.
        cross_session_threshold: occurrences across 2+ distinct sessions to trigger.
    """

    def __init__(self, threshold: int = 3, cross_session_threshold: int = 2) -> None:
        if not isinstance(threshold, int) or threshold < 1:
            raise ValueError(f"threshold must be a positive integer, got {threshold}")
        if not isinstance(cross_session_threshold, int) or cross_session_threshold < 1:
            raise ValueError(f"cross_session_threshold must be a positive integer, got {cross_session_threshold}")
        self._threshold = threshold
        self._cross_session_threshold = cross_session_threshold
        self._counters: dict[tuple[str, str], _FingerprintCounter] = defaultdict(
            _FingerprintCounter
        )
        self._lock = threading.Lock()

    def record(
        self, fingerprint: tuple[str, str], session_id: str
    ) -> dict | None:
        """Record one occurrence. Returns a lesson dict when threshold met."""
        category, stype = fingerprint
        lesson = None

        with self._lock:
            counter = self._counters[fingerprint]
            counter.count += 1
            counter.sessions.add(session_id)

            # Check cross-session first (2 occurrences across 2+ sessions)
            if (
                len(counter.sessions) >= 2
                and counter.count >= self._cross_session_threshold
            ) or counter.count >= self._threshold:
                self._counters[fingerprint] = _FingerprintCounter()
                lesson = self._make_lesson(category, stype)

        return lesson

    @staticmethod
    def _make_lesson(category: str, stype: str) -> dict:
        return {
            "description": f"Always include {stype} in {category} files",
            "category": category,
            "detection": "addition_pattern",
            "fingerprint": f"{category.upper()}:{stype}",
        }
