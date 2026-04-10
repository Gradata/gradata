"""Gradata Rules — Core rule injection, tracking, and context system.

These are NOT generic patterns. They're the mechanism by which graduated
lessons become active rules that shape agent behavior.

- rule_engine: Inject graduated rules into prompts
- rule_context: Query graduated rules for pattern matching
- rule_tracker: Track rule applications and misfires
- scope: Task classification for context-appropriate rule injection
"""

from gradata.rules.rule_context import GraduatedRule, get_rule_context
from gradata.rules.rule_engine import apply_rules, format_rules_for_prompt
from gradata.rules.rule_tracker import RuleApplication, log_application
from gradata.rules.scope import AudienceTier, TaskType, classify_scope

__all__ = [
    "AudienceTier",
    "GraduatedRule",
    "RuleApplication",
    "TaskType",
    "apply_rules",
    "classify_scope",
    "format_rules_for_prompt",
    "get_rule_context",
    "log_application",
]
