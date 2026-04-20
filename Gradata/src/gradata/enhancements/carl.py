"""Backward-compatibility shim — all code moved to behavioral_engine.py."""

from gradata.enhancements.behavioral_engine import (
    BehavioralContract,
    ConstraintViolation,
    ContractRegistry,
    Directive,
    DirectiveRegistry,
    PrioritizedConstraint,
    RulePriority,
)

__all__ = [
    "BehavioralContract",
    "ConstraintViolation",
    "ContractRegistry",
    "Directive",
    "DirectiveRegistry",
    "PrioritizedConstraint",
    "RulePriority",
]
