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
