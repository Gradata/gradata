"""
Rules Distillation — Detect Repeated Patterns Ready for Rule Promotion
======================================================================
Layer 1 Enhancement: imports from patterns/ (memory)

Scans lessons, corrections, and events to find patterns that appear
3+ times across categories. These are candidates for promotion to
permanent behavioral rules.

This module provides the ALGORITHM only (pure computation).
The brain-layer CLI (brain/scripts/rules_distill.py) handles I/O.

The distillation pipeline:
  1. Collect all lessons (active + archived) and corrections
  2. Group by category
  3. Find categories with 3+ entries (configurable threshold)
  4. Check if already covered by existing CARL rules
  5. Propose promotions with evidence

This is distinct from self_improvement.py's graduation (which promotes
individual lessons based on confidence). Distillation finds CROSS-LESSON
patterns — when multiple separate lessons in the same category all point
to the same behavioral rule, that's a distillation candidate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class LessonEntry:
    """A single lesson or correction entry for distillation analysis."""

    date: str
    status: str  # "INSTINCT:0.30", "PATTERN:0.80", "RULE", "CORRECTION"
    category: str  # "DRAFTING", "ACCURACY", "PROCESS", etc.
    description: str
    source: str  # "lessons.md", "lessons-archive.md", "events.jsonl"


@dataclass
class DistillationProposal:
    """A proposed rule promotion based on repeated patterns."""

    category: str
    count: int  # Number of entries in this category
    principle: str  # Representative description
    evidence_sources: list[str]  # Which files contributed
    status_breakdown: dict[str, int]  # e.g., {"PATTERN:0.80": 3, "CORRECTION": 2}
    already_covered_by: str | None  # Name of existing rule if covered
    action: str  # "PROPOSE" or "ALREADY_COVERED"
    entries: list[dict] = field(default_factory=list)  # Evidence entries


def find_distillation_candidates(
    entries: list[LessonEntry],
    existing_rules: dict[str, str] | None = None,
    min_count: int = 3,
) -> list[DistillationProposal]:
    """Find categories with repeated patterns ready for rule promotion.

    Args:
        entries: All lesson entries (active + archived + corrections)
        existing_rules: Map of rule_name -> rule_text for dedup checking
        min_count: Minimum entries in a category to be considered

    Returns:
        List of DistillationProposals sorted by count (descending)
    """
    existing_rules = existing_rules or {}

    # Group by category
    by_category: dict[str, list[LessonEntry]] = defaultdict(list)
    for entry in entries:
        by_category[entry.category].append(entry)

    proposals = []
    for category, cat_entries in sorted(by_category.items()):
        if len(cat_entries) < min_count:
            continue

        # Representative description: most recent entry
        representative = cat_entries[-1].description

        # Check if already covered by existing rules
        covered_by = _check_coverage(
            " ".join(e.description for e in cat_entries),
            existing_rules,
        )

        sources = list({e.source for e in cat_entries})
        statuses = Counter(e.status for e in cat_entries)

        proposal = DistillationProposal(
            category=category,
            count=len(cat_entries),
            principle=representative,
            evidence_sources=sources,
            status_breakdown=dict(statuses),
            already_covered_by=covered_by,
            action="ALREADY_COVERED" if covered_by else "PROPOSE",
            entries=[
                {"date": e.date, "status": e.status, "desc": e.description[:120]}
                for e in cat_entries
            ],
        )
        proposals.append(proposal)

    proposals.sort(key=lambda x: (-x.count, x.category))
    return proposals


def _check_coverage(combined_text: str, existing_rules: dict[str, str]) -> str | None:
    """Check if a pattern is already covered by an existing rule.

    Uses simple keyword overlap to detect coverage.
    Returns the rule name if covered, None otherwise.
    """
    if not existing_rules:
        return None

    text_lower = combined_text.lower()
    words = set(text_lower.split())

    best_match = None
    best_overlap = 0

    for rule_name, rule_text in existing_rules.items():
        rule_words = set(rule_text.lower().split())
        overlap = len(words & rule_words)
        # Require at least 30% keyword overlap
        if rule_words and overlap / len(rule_words) > 0.30 and overlap > best_overlap:
            best_overlap = overlap
            best_match = rule_name

    return best_match


def format_proposals(proposals: list[DistillationProposal]) -> str:
    """Format proposals as human-readable text."""
    if not proposals:
        return "No distillation candidates found."

    lines = [f"# Rules Distillation — {len(proposals)} candidates\n"]
    for i, p in enumerate(proposals, 1):
        status = "COVERED" if p.already_covered_by else "PROPOSE"
        lines.append(f"## {i}. [{status}] {p.category} ({p.count} entries)")
        lines.append(f"**Principle:** {p.principle}")
        lines.append(f"**Sources:** {', '.join(p.evidence_sources)}")
        lines.append(f"**Statuses:** {p.status_breakdown}")
        if p.already_covered_by:
            lines.append(f"**Covered by:** {p.already_covered_by}")
        lines.append("")

    return "\n".join(lines)
