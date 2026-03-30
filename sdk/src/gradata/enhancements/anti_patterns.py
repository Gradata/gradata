"""
Anti-Pattern Detection — Proactive negative rules for output quality.
======================================================================
Inspired by: Jarvis (ethanplusai/jarvis) monitor.py

Checks AI outputs against known anti-patterns BEFORE the user corrects.
Creates a self-correction signal: if the brain detects its own output
matches a known bad pattern, that's a correction signal without waiting
for the user.

Anti-patterns are organized by category and can be extended with
graduated negative rules from the correction pipeline.

Usage::

    from gradata.enhancements.anti_patterns import (
        AntiPatternDetector, Detection, DEFAULT_ANTI_PATTERNS,
    )

    detector = AntiPatternDetector()
    detections = detector.check("I'd be happy to help you with that! Absolutely!")
    for d in detections:
        print(f"{d.pattern_name}: {d.matched_text}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AntiPattern",
    "Detection",
    "AntiPatternDetector",
    "DEFAULT_ANTI_PATTERNS",
    "DEFAULT_PATTERNS",
]


@dataclass
class AntiPattern:
    """A single anti-pattern to detect.

    Attributes:
        name: Identifier for this anti-pattern.
        category: Category (ai_tell, filler, hedging, over_promise, style).
        pattern: Regex pattern or literal string to match.
        is_regex: Whether pattern is a regex (vs literal substring).
        severity: How bad this is (low, medium, high).
        description: Human explanation of why this is bad.
        replacement_hint: What to do instead.
    """
    name: str
    category: str
    pattern: str
    is_regex: bool = False
    severity: str = "medium"
    description: str = ""
    replacement_hint: str = ""


@dataclass
class Detection:
    """A detected anti-pattern in output text.

    Attributes:
        pattern_name: Which anti-pattern was matched.
        category: Anti-pattern category.
        severity: How bad.
        matched_text: The text that triggered the match.
        position: Character position in the text.
        replacement_hint: What to do instead.
    """
    pattern_name: str
    category: str
    severity: str
    matched_text: str = ""
    position: int = 0
    replacement_hint: str = ""


# ---------------------------------------------------------------------------
# Default anti-pattern library
# ---------------------------------------------------------------------------

DEFAULT_PATTERNS: list[AntiPattern] = [
    # AI tells — patterns that scream "an AI wrote this"
    AntiPattern(
        name="as_an_ai",
        category="ai_tell",
        pattern=r"\bas an ai\b",
        is_regex=True,
        severity="high",
        description="Explicitly identifies as AI. Users know. Don't remind them.",
        replacement_hint="Remove the phrase entirely.",
    ),
    AntiPattern(
        name="happy_to_help",
        category="ai_tell",
        pattern="i'd be happy to",
        severity="medium",
        description="Filler phrase. Goes straight to the answer instead.",
        replacement_hint="Start with the actual answer.",
    ),
    AntiPattern(
        name="absolutely",
        category="ai_tell",
        pattern=r"\babsolutely[!.]",
        is_regex=True,
        severity="low",
        description="Over-enthusiastic agreement. Sounds robotic.",
        replacement_hint="Just agree normally or skip the acknowledgment.",
    ),
    AntiPattern(
        name="great_question",
        category="ai_tell",
        pattern="great question",
        severity="medium",
        description="Patronizing. The user doesn't need validation.",
        replacement_hint="Just answer the question.",
    ),
    AntiPattern(
        name="certainly",
        category="ai_tell",
        pattern=r"\bcertainly[!,.]",
        is_regex=True,
        severity="low",
        description="Formal filler. Sounds like a butler.",
        replacement_hint="Drop it and start with the content.",
    ),
    AntiPattern(
        name="delve_into",
        category="ai_tell",
        pattern="delve into",
        severity="medium",
        description="Wikipedia-identified AI tell. Nobody says 'delve' in conversation.",
        replacement_hint="Use 'look at', 'explore', or 'dig into'.",
    ),
    AntiPattern(
        name="leverage",
        category="ai_tell",
        pattern=r"\bleverage\b",
        is_regex=True,
        severity="low",
        description="Corporate jargon. Often marks AI-generated content.",
        replacement_hint="Use 'use'.",
    ),
    AntiPattern(
        name="in_conclusion",
        category="ai_tell",
        pattern="in conclusion",
        severity="medium",
        description="Essay structure marker. Conversations don't need conclusions.",
        replacement_hint="Just end naturally or summarize without the marker.",
    ),

    # Hedging — reduces confidence in output
    AntiPattern(
        name="might_possibly",
        category="hedging",
        pattern=r"\bmight possibly\b",
        is_regex=True,
        severity="medium",
        description="Double hedge. Either it might or it's possible, not both.",
        replacement_hint="Pick one: 'might' or 'possibly'.",
    ),
    AntiPattern(
        name="i_think_maybe",
        category="hedging",
        pattern=r"\bi think maybe\b",
        is_regex=True,
        severity="medium",
        description="Triple hedge. Be direct.",
        replacement_hint="State the thing directly or say 'I'm not sure about X'.",
    ),

    # Over-promising
    AntiPattern(
        name="comprehensive",
        category="over_promise",
        pattern=r"\bcomprehensive\b",
        is_regex=True,
        severity="low",
        description="Claims comprehensiveness rarely deliver it.",
        replacement_hint="Be specific about what's covered.",
    ),

    # Style issues
    AntiPattern(
        name="em_dash_in_prose",
        category="style",
        pattern="\u2014",  # em dash character
        severity="low",
        description="Em dashes in email prose can look AI-generated.",
        replacement_hint="Use colons, commas, or rewrite the sentence.",
    ),
    AntiPattern(
        name="exclamation_overuse",
        category="style",
        pattern=r"[!]\s*[A-Z].*[!]",
        is_regex=True,
        severity="low",
        description="Multiple exclamation points in close proximity.",
        replacement_hint="Use at most one exclamation per paragraph.",
    ),
]

# Flat list of anti-pattern descriptions for briefing export
DEFAULT_ANTI_PATTERNS: list[str] = [
    f"{p.description} ({p.replacement_hint})" for p in DEFAULT_PATTERNS
]


class AntiPatternDetector:
    """Detects anti-patterns in AI output text.

    Uses the default library plus any custom patterns added at runtime.
    Custom patterns can come from graduated negative rules in the
    correction pipeline.
    """

    def __init__(
        self,
        patterns: list[AntiPattern] | None = None,
        include_defaults: bool = True,
    ) -> None:
        self._patterns: list[AntiPattern] = []
        if include_defaults:
            self._patterns.extend(DEFAULT_PATTERNS)
        if patterns:
            self._patterns.extend(patterns)

        # Pre-compile regex patterns
        self._compiled: list[tuple[AntiPattern, re.Pattern]] = []
        for p in self._patterns:
            if p.is_regex:
                self._compiled.append((p, re.compile(p.pattern, re.IGNORECASE)))
            else:
                self._compiled.append((p, re.compile(re.escape(p.pattern), re.IGNORECASE)))

    def check(self, text: str) -> list[Detection]:
        """Check text for anti-patterns.

        Args:
            text: The AI output to check.

        Returns:
            List of Detection objects for each match found.
        """
        if not text:
            return []

        detections: list[Detection] = []
        for pattern, compiled in self._compiled:
            match = compiled.search(text)
            if match:
                detections.append(Detection(
                    pattern_name=pattern.name,
                    category=pattern.category,
                    severity=pattern.severity,
                    matched_text=match.group(),
                    position=match.start(),
                    replacement_hint=pattern.replacement_hint,
                ))

        return detections

    def score(self, text: str) -> float:
        """Score text quality based on anti-pattern density.

        Returns a score from 0.0 (terrible, many anti-patterns) to
        1.0 (clean, no anti-patterns detected).
        """
        detections = self.check(text)
        if not detections:
            return 1.0

        # Weight by severity
        severity_weights = {"high": 3.0, "medium": 2.0, "low": 1.0}
        total_weight = sum(
            severity_weights.get(d.severity, 1.0) for d in detections
        )

        # Normalize: 10 severity-weighted detections = 0.0 score
        return max(0.0, 1.0 - total_weight / 10.0)

    def add_pattern(self, pattern: AntiPattern) -> None:
        """Add a custom anti-pattern at runtime."""
        self._patterns.append(pattern)
        if pattern.is_regex:
            self._compiled.append((pattern, re.compile(pattern.pattern, re.IGNORECASE)))
        else:
            self._compiled.append((pattern, re.compile(re.escape(pattern.pattern), re.IGNORECASE)))

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    def stats(self) -> dict[str, Any]:
        """Return detector statistics."""
        by_category: dict[str, int] = {}
        for p in self._patterns:
            by_category[p.category] = by_category.get(p.category, 0) + 1
        return {
            "total_patterns": self.pattern_count,
            "by_category": by_category,
        }
