"""
Quality Monitoring — Anti-pattern detection + failure/regression alerts.
========================================================================
Merged from: anti_patterns.py + failure_detectors.py (S79 consolidation)

Two concerns, one module:
  1. Anti-Pattern Detection: Proactive negative rules for output quality.
     Checks AI outputs against known anti-patterns BEFORE the user corrects.
  2. Failure Detectors: 4 automated regression alerts (SPEC Section 5).
     Detects when brain is ignored, playing safe, overfitting, or regressing.

Usage::

    from gradata.enhancements.quality_monitoring import (
        AntiPatternDetector, Detection, DEFAULT_ANTI_PATTERNS,
        detect_failures, format_alerts, Alert,
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gradata.enhancements.metrics import MetricsWindow

__all__ = [
    "BLANDNESS_THRESHOLD",
    "DEFAULT_ANTI_PATTERNS",
    "DEFAULT_PATTERNS",
    # Failure detection
    "Alert",
    # Anti-pattern detection
    "AntiPattern",
    "AntiPatternDetector",
    "Detection",
    "detect_being_ignored",
    "detect_failures",
    "detect_overfitting",
    "detect_playing_safe",
    "detect_regression_to_mean",
    "format_alerts",
]


# ═══════════════════════════════════════════════════════════════════════
# Anti-Pattern Detection
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class AntiPattern:
    """A single anti-pattern to detect."""
    name: str
    category: str
    pattern: str
    is_regex: bool = False
    severity: str = "medium"
    description: str = ""
    replacement_hint: str = ""


@dataclass
class Detection:
    """A detected anti-pattern in output text."""
    pattern_name: str
    category: str
    severity: str
    matched_text: str = ""
    position: int = 0
    replacement_hint: str = ""


DEFAULT_PATTERNS: list[AntiPattern] = [
    # AI tells
    AntiPattern(name="as_an_ai", category="ai_tell", pattern=r"\bas an ai\b", is_regex=True, severity="high", description="Explicitly identifies as AI.", replacement_hint="Remove the phrase entirely."),
    AntiPattern(name="happy_to_help", category="ai_tell", pattern="i'd be happy to", severity="medium", description="Filler phrase.", replacement_hint="Start with the actual answer."),
    AntiPattern(name="absolutely", category="ai_tell", pattern=r"\babsolutely[!.]", is_regex=True, severity="low", description="Over-enthusiastic agreement.", replacement_hint="Just agree normally."),
    AntiPattern(name="great_question", category="ai_tell", pattern="great question", severity="medium", description="Patronizing.", replacement_hint="Just answer the question."),
    AntiPattern(name="certainly", category="ai_tell", pattern=r"\bcertainly[!,.]", is_regex=True, severity="low", description="Formal filler.", replacement_hint="Drop it."),
    AntiPattern(name="delve_into", category="ai_tell", pattern="delve into", severity="medium", description="Wikipedia-identified AI tell.", replacement_hint="Use 'look at' or 'explore'."),
    AntiPattern(name="leverage", category="ai_tell", pattern=r"\bleverage\b", is_regex=True, severity="low", description="Corporate jargon.", replacement_hint="Use 'use'."),
    AntiPattern(name="in_conclusion", category="ai_tell", pattern="in conclusion", severity="medium", description="Essay structure marker.", replacement_hint="End naturally."),
    # Hedging
    AntiPattern(name="might_possibly", category="hedging", pattern=r"\bmight possibly\b", is_regex=True, severity="medium", description="Double hedge.", replacement_hint="Pick one."),
    AntiPattern(name="i_think_maybe", category="hedging", pattern=r"\bi think maybe\b", is_regex=True, severity="medium", description="Triple hedge.", replacement_hint="State directly."),
    # Over-promising
    AntiPattern(name="comprehensive", category="over_promise", pattern=r"\bcomprehensive\b", is_regex=True, severity="low", description="Rarely delivered.", replacement_hint="Be specific."),
    # Style
    AntiPattern(name="em_dash_in_prose", category="style", pattern="\u2014", severity="low", description="Em dashes look AI-generated.", replacement_hint="Use colons, commas, or rewrite."),
    AntiPattern(name="exclamation_overuse", category="style", pattern=r"[!]\s*[A-Z].*[!]", is_regex=True, severity="low", description="Multiple exclamation points.", replacement_hint="At most one per paragraph."),
]

DEFAULT_ANTI_PATTERNS: list[str] = [
    f"{p.description} ({p.replacement_hint})" for p in DEFAULT_PATTERNS
]


class AntiPatternDetector:
    """Detects anti-patterns in AI output text."""

    def __init__(self, patterns: list[AntiPattern] | None = None, include_defaults: bool = True) -> None:
        self._patterns: list[AntiPattern] = []
        if include_defaults:
            self._patterns.extend(DEFAULT_PATTERNS)
        if patterns:
            self._patterns.extend(patterns)
        self._compiled: list[tuple[AntiPattern, re.Pattern]] = []
        for p in self._patterns:
            if p.is_regex:
                self._compiled.append((p, re.compile(p.pattern, re.IGNORECASE)))
            else:
                self._compiled.append((p, re.compile(re.escape(p.pattern), re.IGNORECASE)))

    def check(self, text: str) -> list[Detection]:
        if not text:
            return []
        detections: list[Detection] = []
        for pattern, compiled in self._compiled:
            match = compiled.search(text)
            if match:
                detections.append(Detection(
                    pattern_name=pattern.name, category=pattern.category,
                    severity=pattern.severity, matched_text=match.group(),
                    position=match.start(), replacement_hint=pattern.replacement_hint,
                ))
        return detections

    def score(self, text: str) -> float:
        detections = self.check(text)
        if not detections:
            return 1.0
        severity_weights = {"high": 3.0, "medium": 2.0, "low": 1.0}
        total_weight = sum(severity_weights.get(d.severity, 1.0) for d in detections)
        return max(0.0, 1.0 - total_weight / 10.0)

    def add_pattern(self, pattern: AntiPattern) -> None:
        self._patterns.append(pattern)
        if pattern.is_regex:
            self._compiled.append((pattern, re.compile(pattern.pattern, re.IGNORECASE)))
        else:
            self._compiled.append((pattern, re.compile(re.escape(pattern.pattern), re.IGNORECASE)))

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    def stats(self) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        for p in self._patterns:
            by_category[p.category] = by_category.get(p.category, 0) + 1
        return {"total_patterns": self.pattern_count, "by_category": by_category}


# ═══════════════════════════════════════════════════════════════════════
# Failure Detectors (SPEC Section 5)
# ═══════════════════════════════════════════════════════════════════════

BLANDNESS_THRESHOLD = 0.70


@dataclass
class Alert:
    """A detected quality regression alert."""
    detector: str = ""
    severity: str = "warning"
    message: str = ""


def detect_being_ignored(current: MetricsWindow, previous: MetricsWindow | None = None) -> list[Alert]:
    if previous is None:
        return []
    if (current.correction_density < previous.correction_density * 0.5
            and current.edit_distance_avg >= previous.edit_distance_avg * 0.9):
        return [Alert(detector="being_ignored", severity="warning",
                      message=f"Corrections dropped {current.correction_density:.2f} → {previous.correction_density:.2f} but edit distance unchanged ({current.edit_distance_avg:.2f}). Brain may be ignored.")]
    return []


def detect_playing_safe(current: MetricsWindow, previous: MetricsWindow | None = None) -> list[Alert]:
    if previous is None:
        return []
    if (current.rule_success_rate > previous.rule_success_rate + 0.1
            and abs(current.edit_distance_avg - previous.edit_distance_avg) < 0.02):
        return [Alert(detector="playing_safe", severity="warning",
                      message="Acceptance rate improved but output quality is flat. Brain may be playing safe.")]
    return []


def detect_overfitting(current: MetricsWindow, previous: MetricsWindow | None = None) -> list[Alert]:
    if previous is None:
        return []
    if (current.rule_misfire_rate > previous.rule_misfire_rate + 0.05
            and current.rule_success_rate < previous.rule_success_rate):
        return [Alert(detector="overfitting", severity="warning",
                      message=f"Misfire rate increased ({previous.rule_misfire_rate:.2f} → {current.rule_misfire_rate:.2f}) while success rate dropped. Brain may be overfitting.")]
    return []


def detect_regression_to_mean(current: MetricsWindow, previous: MetricsWindow | None = None) -> list[Alert]:
    if current.blandness_score > BLANDNESS_THRESHOLD:
        return [Alert(detector="regression_to_mean", severity="warning",
                      message=f"Output blandness score {current.blandness_score:.2f} exceeds threshold {BLANDNESS_THRESHOLD}. Brain may be regressing to generic outputs.")]
    return []


def detect_failures(current: MetricsWindow, previous: MetricsWindow | None = None) -> list[Alert]:
    alerts: list[Alert] = []
    alerts.extend(detect_being_ignored(current, previous))
    alerts.extend(detect_playing_safe(current, previous))
    alerts.extend(detect_overfitting(current, previous))
    alerts.extend(detect_regression_to_mean(current, previous))
    return alerts


def format_alerts(alerts: list[Alert]) -> str:
    if not alerts:
        return "No alerts."
    return "\n".join(f"[{a.severity.upper()}] {a.detector}: {a.message}" for a in alerts)