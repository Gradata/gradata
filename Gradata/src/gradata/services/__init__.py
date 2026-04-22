"""Internal services — embedding computation, session history tracking.

These modules were previously at ``gradata.integrations.embeddings`` and
``gradata.integrations.session_history``. They were never framework
integrations; they are core infrastructure used by :class:`gradata.Brain`.
Moved here in 0.7.0 to leave ``gradata.integrations`` as a pure legacy
namespace scheduled for removal in v0.9.0 (per the two-minor-version
carry rule in ``docs/contributing/deprecation-policy.md``).
"""
