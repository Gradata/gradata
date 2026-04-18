"""Gradata Rules — Core rule injection, tracking, and context system.

These are NOT generic patterns. They're the mechanism by which graduated
lessons become active rules that shape agent behavior.

- rule_engine: Inject graduated rules into prompts
- rule_context: Query graduated rules for pattern matching
- rule_tracker: Track rule applications and misfires
- scope: Task classification for context-appropriate rule injection
"""

from .rule_tracker import RuleApplication
from .scope import AudienceTier, TaskType

__all__ = [
    "AudienceTier",
    "RuleApplication",
    "TaskType",
]
