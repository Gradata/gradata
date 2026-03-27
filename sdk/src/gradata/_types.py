"""
Shared type definitions for the Gradata SDK.
=============================================
SDK LAYER: Layer 0 (patterns-safe). These types are used across both
patterns/ and enhancements/ and must live outside both layers to avoid
circular imports and layer violations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LessonState(Enum):
    """Maturity tiers for a learned lesson."""
    INSTINCT = "INSTINCT"       # 0.00 - 0.59
    PATTERN = "PATTERN"         # 0.60 - 0.89
    RULE = "RULE"               # 0.90+
    UNTESTABLE = "UNTESTABLE"   # 20+ sessions with 0 fires


@dataclass
class Lesson:
    """A single learned lesson with confidence tracking."""
    date: str                          # ISO date when the lesson was created
    state: LessonState                 # Current maturity tier
    confidence: float                  # 0.00 - 1.00
    category: str                      # e.g. DRAFTING, ACCURACY, PROCESS
    description: str                   # Full text after "CATEGORY: "
    root_cause: str = ""               # Root cause analysis (after "Root cause:")
    fire_count: int = 0                # Times the lesson was triggered/applied
    sessions_since_fire: int = 0       # Sessions since last application
    misfire_count: int = 0             # Times applied but made output worse
    scope_json: str = ""               # JSON-serialized RuleScope; empty = universal
    example_draft: str | None = None      # Before: what the AI produced
    example_corrected: str | None = None  # After: what Oliver changed it to

    def __post_init__(self) -> None:
        self.confidence = round(max(0.0, min(1.0, self.confidence)), 2)
