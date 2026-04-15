"""Shared RULE-tier lesson parsing for lessons.md.

Multiple call sites (`cli.py`, `hooks/stale_hook_check.py`) previously held
near-duplicate regexes for parsing `[YYYY-MM-DD] [RULE:X.Y] category: desc`
lines. This module centralizes that so the format stays consistent.

A parsed RULE line exposes four fields:
  - prefix:     the bit before the colon (e.g. `[2026-04-14] [RULE:0.91] feedback`)
  - category:   the category word after the `[RULE:X.Y] ` tag
  - description: the cleaned text (without the `[hooked] ` marker or
                 trailing ``Metadata: {...}`` block, if present)
  - hooked:     True if EITHER the legacy ``[hooked] `` prefix is set OR the
                inline ``Metadata: {"how_enforced": "hooked", ...}`` block
                declares the lesson as hook-enforced.

Only RULE-tier lessons are parsed here; INSTINCT/PATTERN lines are ignored.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

# Captures: group(1) = full prefix, group(2) = category, group(3) = description.
_RULE_LESSON_RE = re.compile(
    r"^(\[[\d-]+\]\s+\[RULE:[\d.]+\]\s+(\w+)):\s+(.+)$"
)

_HOOKED_MARKER = "[hooked] "

# Matches a trailing ``Metadata: {...}`` JSON object appended to a RULE line.
# We parse lazily with json.loads after extracting the candidate substring so
# malformed blobs degrade to "no metadata" rather than crashing the parser.
_METADATA_RE = re.compile(r"\s*Metadata:\s*(\{.*\})\s*$")


@dataclass(frozen=True)
class RuleLesson:
    """A single parsed RULE-tier lesson line."""

    prefix: str
    category: str
    description: str  # cleaned: [hooked] marker and Metadata block stripped
    hooked: bool


def parse_rule_lesson(line: str) -> RuleLesson | None:
    """Parse one lessons.md line. Returns None if it is not a RULE-tier line."""
    m = _RULE_LESSON_RE.match(line.strip())
    if not m:
        return None
    prefix = m.group(1)
    category = m.group(2)
    raw_desc = m.group(3).strip()

    # Strip inline Metadata JSON (new structured format) and check how_enforced.
    structured_hooked = False
    meta_match = _METADATA_RE.search(raw_desc)
    if meta_match:
        try:
            meta = json.loads(meta_match.group(1))
            if isinstance(meta, dict) and meta.get("how_enforced") == "hooked":
                structured_hooked = True
        except (ValueError, TypeError):
            pass
        raw_desc = raw_desc[: meta_match.start()].rstrip()

    legacy_hooked = raw_desc.startswith(_HOOKED_MARKER)
    desc = raw_desc[len(_HOOKED_MARKER):] if legacy_hooked else raw_desc
    return RuleLesson(
        prefix=prefix,
        category=category,
        description=desc,
        hooked=legacy_hooked or structured_hooked,
    )


def iter_rule_lessons(lines: Iterable[str]) -> Iterator[RuleLesson]:
    """Yield every RULE-tier lesson found in an iterable of raw text lines."""
    for line in lines:
        parsed = parse_rule_lesson(line)
        if parsed is not None:
            yield parsed


__all__ = ["RuleLesson", "iter_rule_lessons", "parse_rule_lesson"]
