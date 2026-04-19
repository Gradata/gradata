"""Core rule injection, tracking, and context — the mechanism by which
graduated lessons become active rules. ``rule_engine`` injects into prompts;
``rule_context`` queries for pattern matching; ``rule_tracker`` records
applications/misfires; ``scope`` classifies tasks for context-appropriate injection.
"""

from .rule_tracker import RuleApplication
from .scope import AudienceTier, TaskType

__all__ = [
    "AudienceTier",
    "RuleApplication",
    "TaskType",
]
