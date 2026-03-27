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


class RuleTransferScope(Enum):
    """How transferable a rule is across users/teams."""
    PERSONAL = "personal"    # One user's style (email tone, formatting preference)
    TEAM = "team"            # Org-specific workflow (Pipedrive naming, Calendly format)
    UNIVERSAL = "universal"  # Everyone benefits (no AI tells, verify data, don't fabricate)


class LessonState(Enum):
    """Maturity tiers for a learned lesson."""
    INSTINCT = "INSTINCT"       # 0.00 - 0.59
    PATTERN = "PATTERN"         # 0.60 - 0.89
    RULE = "RULE"               # 0.90+
    UNTESTABLE = "UNTESTABLE"   # 20+ sessions with 0 fires
    ARCHIVED = "ARCHIVED"       # graduated out (moved to lessons-archive.md)
    KILLED = "KILLED"           # failed ablation or untestable 20+ sessions


# States eligible for rule injection (shared across rule_engine and meta_rules).
ELIGIBLE_STATES: frozenset[LessonState] = frozenset(
    {LessonState.RULE, LessonState.PATTERN}
)


# ---------------------------------------------------------------------------
# Lesson Lifecycle State Machine (Optio pattern: explicit transitions)
# ---------------------------------------------------------------------------

TRANSITIONS: dict[LessonState, dict[str, LessonState]] = {
    LessonState.INSTINCT: {
        "promote": LessonState.PATTERN,    # confidence >= 0.60
        "kill": LessonState.KILLED,        # confidence <= 0.0 or untestable 20+ sessions
    },
    LessonState.PATTERN: {
        "promote": LessonState.RULE,       # confidence >= 0.90
        "demote": LessonState.INSTINCT,    # confidence < 0.60 after penalty
        "kill": LessonState.KILLED,        # confidence <= 0.0
    },
    LessonState.RULE: {
        "archive": LessonState.ARCHIVED,   # moved to lessons-archive.md
        "demote": LessonState.PATTERN,     # failed ablation
    },
    LessonState.UNTESTABLE: {
        "kill": LessonState.KILLED,        # untestable 20+ sessions
        "promote": LessonState.INSTINCT,   # got testable evidence
    },
    LessonState.ARCHIVED: {},              # terminal state
    LessonState.KILLED: {},                # terminal state
}


def transition(current: LessonState, action: str) -> LessonState:
    """Validate and execute a lesson state transition.

    Args:
        current: The lesson's current state.
        action: The transition action (e.g. "promote", "demote", "kill", "archive").

    Returns:
        The new LessonState after the transition.

    Raises:
        ValueError: If the action is not valid for the current state.
    """
    valid_actions = TRANSITIONS.get(current, {})
    if action not in valid_actions:
        valid = list(valid_actions.keys()) if valid_actions else []
        raise ValueError(
            f"Invalid transition: {current.value} + '{action}'. "
            f"Valid actions from {current.value}: {valid}"
        )
    return valid_actions[action]


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
    transfer_scope: RuleTransferScope = RuleTransferScope.PERSONAL  # How transferable
    example_draft: str | None = None      # Before: what the AI produced
    example_corrected: str | None = None  # After: what Oliver changed it to

    def __post_init__(self) -> None:
        self.confidence = round(max(0.0, min(1.0, self.confidence)), 2)
