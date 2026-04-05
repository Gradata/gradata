"""Backward compatibility shim — patterns moved to gradata.contrib.patterns.

Usage (new canonical path):
    from gradata.contrib.patterns import Pipeline, SmartRAG, Guard
    from gradata.rules import RuleApplication, AudienceTier, TaskType

Usage (backward compat, still works):
    from gradata.patterns import Pipeline, SmartRAG, Guard
"""


def __getattr__(name: str):
    """Forward attribute lookups to contrib.patterns and rules lazily."""
    import importlib

    # Try contrib.patterns first (where most things live)
    contrib = importlib.import_module("gradata.contrib.patterns")
    try:
        return getattr(contrib, name)
    except AttributeError:
        pass

    # Fall through to gradata.rules (RuleApplication, AudienceTier, etc.)
    rules = importlib.import_module("gradata.rules")
    try:
        return getattr(rules, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
