"""
Context Brackets — Explicit context degradation management.
============================================================
Adapted from: paul (ChristopherKahler/paul) context-management.md

Models context capacity as four brackets (FRESH/MODERATE/DEEP/CRITICAL)
and provides actionable guidance for each bracket. Prevents late-session
context rot by making degradation explicit and prescriptive.

Usage::

    from gradata.contrib.patterns.context_brackets import (
        ContextBracket, BracketConfig, get_bracket,
        get_bracket_guidance, estimate_remaining_capacity,
    )

    bracket = get_bracket(remaining_ratio=0.35)
    assert bracket == ContextBracket.DEEP

    guidance = get_bracket_guidance(bracket)
    print(guidance.strategy)  # "Complete current task, prepare handoff"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "BRACKET_CONFIGS",
    "BracketConfig",
    "ContextBracket",
    "ContextTracker",
    "estimate_remaining_capacity",
    "format_bracket_prompt",
    "get_bracket",
    "get_bracket_guidance",
    "is_action_allowed",
]


class ContextBracket(Enum):
    """Context capacity brackets based on remaining token budget."""
    FRESH = "fresh"          # >70% remaining
    MODERATE = "moderate"    # 40-70% remaining
    DEEP = "deep"            # 20-40% remaining
    CRITICAL = "critical"    # <20% remaining


@dataclass(frozen=True)
class BracketConfig:
    """Configuration and guidance for a context bracket.

    Attributes:
        bracket: The bracket this config applies to.
        min_ratio: Minimum remaining ratio (inclusive).
        max_ratio: Maximum remaining ratio (exclusive for upper brackets).
        strategy: High-level strategy description.
        allowed_actions: Actions permitted in this bracket.
        prohibited_actions: Actions that should be avoided.
        plan_sizing: Recommended plan size as fraction of remaining capacity.
        should_handoff: Whether to prepare a session handoff.
    """
    bracket: ContextBracket
    min_ratio: float
    max_ratio: float
    strategy: str
    allowed_actions: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    plan_sizing: float = 0.5
    should_handoff: bool = False


# ---------------------------------------------------------------------------
# Bracket definitions
# ---------------------------------------------------------------------------

BRACKET_CONFIGS: dict[ContextBracket, BracketConfig] = {
    ContextBracket.FRESH: BracketConfig(
        bracket=ContextBracket.FRESH,
        min_ratio=0.70,
        max_ratio=1.0,
        strategy="Full capacity. Load files freely, run parallel operations.",
        allowed_actions=(
            "load_full_files",
            "parallel_operations",
            "new_complex_work",
            "spawn_subagents",
            "deep_research",
        ),
        prohibited_actions=(),
        plan_sizing=0.5,
    ),
    ContextBracket.MODERATE: BracketConfig(
        bracket=ContextBracket.MODERATE,
        min_ratio=0.40,
        max_ratio=0.70,
        strategy="Re-read key files. Prefer summaries. Single-concern plans.",
        allowed_actions=(
            "load_full_files",
            "single_concern_plans",
            "targeted_research",
        ),
        prohibited_actions=(
            "new_complex_work",
            "multi_concern_plans",
        ),
        plan_sizing=0.4,
    ),
    ContextBracket.DEEP: BracketConfig(
        bracket=ContextBracket.DEEP,
        min_ratio=0.20,
        max_ratio=0.40,
        strategy="Complete current task, prepare handoff. Read summaries not full files.",
        allowed_actions=(
            "complete_current_task",
            "read_summaries",
            "prepare_handoff",
        ),
        prohibited_actions=(
            "new_complex_work",
            "load_full_files",
            "spawn_subagents",
            "deep_research",
        ),
        plan_sizing=0.3,
        should_handoff=True,
    ),
    ContextBracket.CRITICAL: BracketConfig(
        bracket=ContextBracket.CRITICAL,
        min_ratio=0.0,
        max_ratio=0.20,
        strategy="Finish current action only. Write comprehensive handoff. No new reads.",
        allowed_actions=(
            "finish_current_action",
            "write_handoff",
            "update_state",
        ),
        prohibited_actions=(
            "new_work",
            "load_files",
            "spawn_subagents",
            "research",
            "multi_step_plans",
        ),
        plan_sizing=0.0,
        should_handoff=True,
    ),
}


# ---------------------------------------------------------------------------
# Bracket detection
# ---------------------------------------------------------------------------

def get_bracket(remaining_ratio: float) -> ContextBracket:
    """Determine the context bracket from remaining capacity ratio.

    Args:
        remaining_ratio: Fraction of context window remaining (0.0 to 1.0).

    Returns:
        The applicable ContextBracket.

    Raises:
        ValueError: If remaining_ratio is outside [0.0, 1.0].
    """
    if not (0.0 <= remaining_ratio <= 1.0):
        raise ValueError(
            f"remaining_ratio must be in [0.0, 1.0], got {remaining_ratio}"
        )

    if remaining_ratio >= 0.70:
        return ContextBracket.FRESH
    elif remaining_ratio >= 0.40:
        return ContextBracket.MODERATE
    elif remaining_ratio >= 0.20:
        return ContextBracket.DEEP
    else:
        return ContextBracket.CRITICAL


def get_bracket_guidance(bracket: ContextBracket) -> BracketConfig:
    """Get the full guidance config for a bracket.

    Args:
        bracket: The context bracket to get guidance for.

    Returns:
        The BracketConfig with strategy, allowed/prohibited actions, etc.
    """
    return BRACKET_CONFIGS[bracket]


def estimate_remaining_capacity(
    tokens_used: int,
    max_tokens: int,
) -> float:
    """Estimate remaining capacity as a ratio.

    Args:
        tokens_used: Number of tokens consumed so far.
        max_tokens: Maximum context window size.

    Returns:
        Remaining ratio in [0.0, 1.0].

    Raises:
        ValueError: If max_tokens <= 0 or tokens_used < 0.
    """
    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be > 0, got {max_tokens}")
    if tokens_used < 0:
        raise ValueError(f"tokens_used must be >= 0, got {tokens_used}")

    remaining = max(0.0, 1.0 - (tokens_used / max_tokens))
    return min(1.0, remaining)


def is_action_allowed(bracket: ContextBracket, action: str) -> bool:
    """Check whether an action is allowed in the given bracket.

    An action is allowed if it appears in allowed_actions and does NOT
    appear in prohibited_actions. If an action is in neither list, it
    is allowed by default.

    Args:
        bracket: The current context bracket.
        action: The action name to check.

    Returns:
        True if the action is permitted.
    """
    config = BRACKET_CONFIGS[bracket]
    return action not in config.prohibited_actions


def format_bracket_prompt(bracket: ContextBracket) -> str:
    """Generate a prompt injection block describing the current bracket.

    Returns a multi-line string suitable for system prompt injection
    that informs the agent of its current context capacity state.
    """
    config = BRACKET_CONFIGS[bracket]
    lines = [
        f'<context-bracket level="{bracket.value}">',
        f"  Strategy: {config.strategy}",
        f"  Plan sizing: {config.plan_sizing:.0%} of remaining capacity",
    ]

    if config.prohibited_actions:
        lines.append(
            f"  AVOID: {', '.join(config.prohibited_actions)}"
        )

    if config.should_handoff:
        lines.append("  ACTION REQUIRED: Prepare session handoff before context exhaustion.")

    lines.append("</context-bracket>")
    return "\n".join(lines)


@dataclass
class ContextTracker:
    """Tracks context usage and provides bracket-aware guidance.

    Usage::

        tracker = ContextTracker(max_tokens=200_000)
        tracker.consume(15_000)
        print(tracker.bracket)         # ContextBracket.FRESH
        print(tracker.remaining_ratio) # 0.925
        print(tracker.prompt_block)    # XML injection block
    """

    max_tokens: int
    tokens_used: int = 0
    _transitions: list[tuple[int, ContextBracket]] = field(
        default_factory=list, repr=False
    )

    def __post_init__(self) -> None:
        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be > 0, got {self.max_tokens}")
        self._transitions.append((0, self.bracket))

    @property
    def remaining_ratio(self) -> float:
        """Current remaining capacity ratio."""
        return estimate_remaining_capacity(self.tokens_used, self.max_tokens)

    @property
    def bracket(self) -> ContextBracket:
        """Current context bracket."""
        return get_bracket(self.remaining_ratio)

    @property
    def guidance(self) -> BracketConfig:
        """Current bracket guidance."""
        return get_bracket_guidance(self.bracket)

    @property
    def prompt_block(self) -> str:
        """Current bracket as prompt injection XML."""
        return format_bracket_prompt(self.bracket)

    def consume(self, tokens: int) -> ContextBracket:
        """Record token consumption and return the (possibly new) bracket.

        Args:
            tokens: Number of tokens consumed in this operation.

        Returns:
            The current bracket after consumption.

        Raises:
            ValueError: If tokens < 0.
        """
        if tokens < 0:
            raise ValueError(f"tokens must be >= 0, got {tokens}")

        old_bracket = self.bracket
        self.tokens_used = min(self.tokens_used + tokens, self.max_tokens)
        new_bracket = self.bracket

        if new_bracket != old_bracket:
            self._transitions.append((self.tokens_used, new_bracket))

        return new_bracket

    @property
    def transitions(self) -> list[tuple[int, ContextBracket]]:
        """Return the history of bracket transitions."""
        return list(self._transitions)

    def should_handoff(self) -> bool:
        """Whether the current bracket recommends preparing a handoff."""
        return self.guidance.should_handoff

    @property
    def rules_budget(self) -> int:
        """Max rules to inject based on current degradation bracket.

        Throttles rule injection to save context tokens:
        FRESH=10, MODERATE=5, DEEP=2, CRITICAL=0
        """
        budgets = {
            ContextBracket.FRESH: 10,
            ContextBracket.MODERATE: 5,
            ContextBracket.DEEP: 2,
            ContextBracket.CRITICAL: 0,
        }
        return budgets.get(self.bracket, 10)