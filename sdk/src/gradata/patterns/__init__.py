"""
Layer 0: Base Agentic Patterns (v1 — core only).

patterns/ never imports from enhancements/.
Pure logic, no external dependencies.

v1 ships: rule_engine, rule_tracker, scope, rule_context.
Commodity patterns (pipeline, rag, reflection, etc.) removed for v1.
"""

from gradata.patterns.rule_engine import apply_rules, format_rules_for_prompt
from gradata.patterns.rule_tracker import RuleApplication
from gradata.patterns.scope import AudienceTier, TaskType, classify_scope

__all__ = [
    "RuleApplication",
    "AudienceTier",
    "TaskType",
    "apply_rules",
    "classify_scope",
    "format_rules_for_prompt",
]
