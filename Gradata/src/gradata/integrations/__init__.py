"""Framework Integrations — DEPRECATED namespace.

.. deprecated::
    ``gradata.integrations`` is deprecated and will be removed in v0.8.0.
    The canonical adapters now live in ``gradata.middleware``::

        from gradata.middleware import wrap_anthropic, wrap_openai
        from gradata.middleware import LangChainCallback, CrewAIGuard

    ``gradata.integrations.embeddings`` and
    ``gradata.integrations.session_history`` are NOT deprecated — those
    remain in this namespace (they have no middleware equivalent).

    Adapter modules (anthropic_adapter, openai_adapter, langchain_adapter,
    crewai_adapter) emit their own ``DeprecationWarning`` on import.
"""

import importlib as _importlib

# Short-name aliases: gradata.integrations.openai -> gradata.integrations.openai_adapter
_ADAPTER_ALIASES = {
    "openai": "openai_adapter",
    "anthropic": "anthropic_adapter",
    "langchain": "langchain_adapter",
    "crewai": "crewai_adapter",
}


def __getattr__(name: str):
    """Lazy-load integration adapters with short-name aliases."""
    target = _ADAPTER_ALIASES.get(name)
    if target is not None:
        return _importlib.import_module(f".{target}", __package__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
