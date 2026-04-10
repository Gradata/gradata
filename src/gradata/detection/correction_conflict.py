# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Gradata

"""Signal 6 — Correction-of-correction detection.

Detects when a new correction opposes a recent lesson by checking
token-level overlap between diffs.  Tracks repeated conflicts per
rule to recommend demote / kill actions.
"""

from __future__ import annotations

import re
import threading
from collections import defaultdict


def tokenize(text: str) -> set[str]:
    """Split on whitespace, lowercase, strip punctuation, return token set."""
    tokens: set[str] = set()
    for word in text.lower().split():
        cleaned = re.sub(r"[^\w]", "", word)
        if cleaned:
            tokens.add(cleaned)
    return tokens


def extract_diff_tokens(old: str, new: str) -> tuple[set[str], set[str]]:
    """Return (added_tokens, removed_tokens) between old and new text."""
    old_tokens = tokenize(old)
    new_tokens = tokenize(new)
    added = new_tokens - old_tokens
    removed = old_tokens - new_tokens
    return added, removed


def detect_conflict(
    original_added: set[str],
    new_removed: set[str],
    threshold: float = 0.3,
) -> bool:
    """True if new correction removes enough of what original added."""
    if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold must be between 0.0 and 1.0, got {threshold}")
    if not original_added or not new_removed:
        return False
    overlap = original_added & new_removed
    return len(overlap) / len(original_added) >= threshold


class ConflictTracker:
    """Track repeated correction conflicts per rule_id.

    Returns escalation action: None → "demote" → "kill".
    """

    def __init__(
        self,
        demote_threshold: int = 2,
        kill_threshold: int = 3,
    ) -> None:
        self._demote_threshold = demote_threshold
        self._kill_threshold = kill_threshold
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def record_conflict(self, rule_id: str) -> str | None:
        """Increment conflict count. Return action or None."""
        with self._lock:
            self._counts[rule_id] += 1
            count = self._counts[rule_id]
            if count >= self._kill_threshold:
                return "kill"
            if count >= self._demote_threshold:
                return "demote"
            return None

    def get_count(self, rule_id: str) -> int:
        """Return current conflict count for a rule."""
        with self._lock:
            return self._counts[rule_id]
