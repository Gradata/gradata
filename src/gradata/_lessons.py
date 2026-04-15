"""Shared RULE-tier lesson parsing for lessons.md.

Multiple call sites (`cli.py`, `hooks/stale_hook_check.py`) previously held
near-duplicate regexes for parsing `[YYYY-MM-DD] [RULE:X.Y] category: desc`
lines. This module centralizes that so the format stays consistent.

A parsed RULE line exposes four fields:
  - prefix:     the bit before the colon (e.g. `[2026-04-14] [RULE:0.91] feedback`)
  - category:   the category word after the `[RULE:X.Y] ` tag
  - description: the cleaned text (without the `[hooked] ` marker, if present)
  - hooked:     True if the raw description had the `[hooked] ` prefix

Only RULE-tier lessons are parsed here; INSTINCT/PATTERN lines are ignored.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

# Captures: group(1) = full prefix, group(2) = category, group(3) = description.
_RULE_LESSON_RE = re.compile(
    r"^(\[[\d-]+\]\s+\[RULE:[\d.]+\]\s+(\w+)):\s+(.+)$"
)

_HOOKED_MARKER = "[hooked] "


@dataclass(frozen=True)
class RuleLesson:
    """A single parsed RULE-tier lesson line."""

    prefix: str
    category: str
    description: str  # cleaned: [hooked] marker stripped
    hooked: bool


def parse_rule_lesson(line: str) -> RuleLesson | None:
    """Parse one lessons.md line. Returns None if it is not a RULE-tier line."""
    m = _RULE_LESSON_RE.match(line.strip())
    if not m:
        return None
    prefix = m.group(1)
    category = m.group(2)
    raw_desc = m.group(3).strip()
    hooked = raw_desc.startswith(_HOOKED_MARKER)
    desc = raw_desc[len(_HOOKED_MARKER):] if hooked else raw_desc
    return RuleLesson(prefix=prefix, category=category, description=desc, hooked=hooked)


def iter_rule_lessons(lines: Iterable[str]) -> Iterator[RuleLesson]:
    """Yield every RULE-tier lesson found in an iterable of raw text lines."""
    for line in lines:
        parsed = parse_rule_lesson(line)
        if parsed is not None:
            yield parsed


__all__ = ["RuleLesson", "iter_rule_lessons", "parse_rule_lesson"]
