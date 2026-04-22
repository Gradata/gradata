"""DEPRECATED namespace — ``gradata.integrations`` is going away.

.. deprecated:: 0.7.0
    Adapter modules (``anthropic_adapter``, ``openai_adapter``,
    ``langchain_adapter``, ``crewai_adapter``) were removed in 0.7.0 after
    their deprecation warnings fired since 0.6.x. Use
    :mod:`gradata.middleware` instead::

        from gradata.middleware import wrap_anthropic, wrap_openai
        from gradata.middleware import LangChainCallback, CrewAIGuard

    ``gradata.integrations.embeddings`` and
    ``gradata.integrations.session_history`` now live in
    :mod:`gradata.services` and are kept here as forwarding shims through
    v0.9.0 (two-minor-version carry per
    ``docs/contributing/deprecation-policy.md``).
"""
