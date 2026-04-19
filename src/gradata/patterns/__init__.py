"""DEPRECATED — patterns moved to ``gradata.contrib.patterns``.

.. deprecated:: 0.6.1
    ``gradata.patterns`` is deprecated and will be removed in v0.8.0.
    Update imports::

        from gradata.contrib.patterns import Pipeline, SmartRAG, Guard
        from gradata.rules import RuleApplication, AudienceTier, TaskType

First access through the shim emits a ``DeprecationWarning`` so downstream
users notice at runtime rather than discovering the move when v0.8.0 removes
this module entirely.
"""

import warnings

_WARNED = False


def __getattr__(name: str):
    global _WARNED
    if not _WARNED:
        warnings.warn(
            "gradata.patterns is deprecated and will be removed in v0.8.0. "
            "Import from gradata.contrib.patterns or gradata.rules instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        _WARNED = True

    import importlib

    contrib = importlib.import_module("gradata.contrib.patterns")
    try:
        return getattr(contrib, name)
    except AttributeError:
        pass

    rules = importlib.import_module("gradata.rules")
    try:
        return getattr(rules, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
