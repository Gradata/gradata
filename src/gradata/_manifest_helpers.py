"""
Brain Manifest Helpers.
=======================
Shared constants and utility functions for manifest generation.
Split from _brain_manifest.py for file size compliance (<500 lines).
"""

# ── Severity constants (single source of truth) ───────────────────────
LOW_SEVERITY = frozenset({"as-is", "minor"})


def _session_window(conn, window: int = 20) -> tuple[int, int]:
    """Return (max_session, min_session) for a recent window. Shared helper."""
    max_session = (
        conn.execute("SELECT MAX(session) FROM events WHERE typeof(session)='integer'").fetchone()[
            0
        ]
        or 0
    )
    return max_session, max(1, max_session - window + 1)


def _sdk_capabilities() -> dict:
    """Enumerate SDK capabilities from adapted modules.

    Probes each module for availability without importing heavy deps.
    Returns a dict of capability_name -> {available, version, source}.
    """
    capabilities: dict[str, dict] = {}

    # (name, module_path, source) triples grouped by upstream provenance.
    all_modules = [
        # ChristopherKahler/paul
        ("context_brackets", "gradata.contrib.patterns.context_brackets", "ChristopherKahler/paul"),
        ("reconciliation", "gradata.contrib.patterns.reconciliation", "ChristopherKahler/paul"),
        ("execute_qualify", "gradata.contrib.patterns.execute_qualify", "ChristopherKahler/paul"),
        # ruflo
        ("q_learning_router", "gradata.contrib.patterns.q_learning_router", "ruflo"),
        # deer-flow
        ("loop_detection", "gradata.contrib.patterns.loop_detection", "deer-flow"),
        ("middleware_chain", "gradata.contrib.patterns.middleware", "deer-flow"),
        # everything-claude-code
        ("observation_hooks", "gradata.enhancements.observation_hooks", "ecc"),
        ("install_manifest", "gradata.contrib.enhancements.install_manifest", "ecc"),
        # EverOS
        ("memory_taxonomy", "gradata.enhancements.memory_taxonomy", "everos"),
        ("cluster_manager", "gradata.enhancements.cluster_manager", "everos"),
        ("lesson_discriminator", "gradata.enhancements.lesson_discriminator", "everos"),
        # Core enhancements
        ("behavioral_engine", "gradata.enhancements.behavioral_engine", "gradata"),
        ("learning_pipeline", "gradata.enhancements.learning_pipeline", "gradata"),
        ("self_improvement", "gradata.enhancements.self_improvement", "gradata"),
        ("quality_gates", "gradata.contrib.enhancements.quality_gates", "gradata"),
        ("truth_protocol", "gradata.contrib.enhancements.truth_protocol", "gradata"),
        ("meta_rules", "gradata.enhancements.meta_rules", "gradata"),
        ("eval_benchmark", "gradata.contrib.enhancements.eval_benchmark", "gradata"),
        ("router_warmstart", "gradata.enhancements.router_warmstart", "gradata"),
        ("git_backfill", "gradata.enhancements.git_backfill", "gradata"),
        ("auto_correct_hook", "gradata.hooks.auto_correct", "gradata"),
        ("reporting", "gradata.enhancements.reporting", "fest.build-inspired+gradata"),
        ("quality_monitoring", "gradata.enhancements.quality_monitoring", "jarvis-inspired+gradata"),
    ]

    for name, module_path, source in all_modules:
        try:
            __import__(module_path)
            capabilities[name] = {"available": True, "source": source}
        except ImportError:
            capabilities[name] = {"available": False, "source": source}

    return {
        "total": len(capabilities),
        "available": sum(1 for c in capabilities.values() if c["available"]),
        "modules": capabilities,
    }
