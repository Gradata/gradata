"""
Brain Manifest Helpers.
=======================
Shared constants and utility functions for manifest generation.
Split from _brain_manifest.py for file size compliance (<500 lines).
"""
import logging

import re
from typing import TYPE_CHECKING

import gradata._paths as _p
from gradata._db import get_connection
logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from gradata._paths import BrainContext

# ── Severity constants (single source of truth) ───────────────────────
LOW_SEVERITY = frozenset({"as-is", "minor"})
HIGH_SEVERITY = frozenset({"moderate", "major", "discarded"})


def _session_window(conn, window: int = 20) -> tuple[int, int]:
    """Return (max_session, min_session) for a recent window. Shared helper."""
    max_session = (
        conn.execute("SELECT MAX(session) FROM events WHERE typeof(session)='integer'").fetchone()[
            0
        ]
        or 0
    )
    return max_session, max(1, max_session - window + 1)


def _read_version(ctx: "BrainContext | None" = None) -> dict:
    result = {"version": "unknown", "sessions_trained": 0, "maturity_phase": "INFANT"}
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    vfile = brain_dir / "VERSION.md"
    if not vfile.exists():
        return result
    text = vfile.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"v(\d+\.\d+\.\d+)", text)
    if m:
        result["version"] = f"v{m.group(1)}"
    m = re.search(r"[Ss]ession\s+(\d+)", text)
    if m:
        result["sessions_trained"] = int(m.group(1))
    for phase in ("STABLE", "MATURE", "ADOLESCENT", "INFANT"):
        if phase in text.upper():
            result["maturity_phase"] = phase
            break
    return result


def _count_events(ctx: "BrainContext | None" = None) -> dict:
    result = {"total": 0, "by_type": {}}
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        rows = conn.execute("SELECT type, COUNT(*) as cnt FROM events GROUP BY type").fetchall()
        for row in rows:
            result["by_type"][row["type"]] = row["cnt"]
            result["total"] += row["cnt"]
        conn.close()
    except Exception:
        logger.warning('Suppressed exception in _count_events', exc_info=True)
    return result


def _get_tables(ctx: "BrainContext | None" = None) -> list[str]:
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _sdk_capabilities() -> dict:
    """Enumerate SDK capabilities from adapted modules.

    Probes each module for availability without importing heavy deps.
    Returns a dict of capability_name -> {available, version, source}.
    """
    capabilities: dict[str, dict] = {}

    # Adapted from ChristopherKahler/paul
    _paul_modules = [
        ("context_brackets", "gradata.contrib.patterns.context_brackets", "ChristopherKahler/paul"),
        ("reconciliation", "gradata.contrib.patterns.reconciliation", "ChristopherKahler/paul"),
        ("task_escalation", "gradata.contrib.patterns.task_escalation", "ChristopherKahler/paul"),
        ("execute_qualify", "gradata.contrib.patterns.execute_qualify", "ChristopherKahler/paul"),
    ]
    # Adapted from ruflo
    _ruflo_modules = [
        ("q_learning_router", "gradata.contrib.patterns.q_learning_router", "ruflo"),
    ]
    # Adapted from deer-flow
    _deerflow_modules = [
        ("loop_detection", "gradata.contrib.patterns.loop_detection", "deer-flow"),
        ("middleware_chain", "gradata.contrib.patterns.middleware", "deer-flow"),
    ]
    # Adapted from everything-claude-code
    _ecc_modules = [
        ("observation_hooks", "gradata.enhancements.observation_hooks", "ecc"),
        ("install_manifest", "gradata.contrib.enhancements.install_manifest", "ecc"),
    ]
    # Adapted from EverOS
    _everos_modules = [
        ("memory_taxonomy", "gradata.enhancements.memory_taxonomy", "everos"),
        ("cluster_manager", "gradata.enhancements.cluster_manager", "everos"),
        ("lesson_discriminator", "gradata.enhancements.lesson_discriminator", "everos"),
    ]
    # Core enhancements
    _core_modules = [
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
        (
            "quality_monitoring",
            "gradata.enhancements.quality_monitoring",
            "jarvis-inspired+gradata",
        ),
    ]

    all_modules = (
        _paul_modules
        + _ruflo_modules
        + _deerflow_modules
        + _ecc_modules
        + _everos_modules
        + _core_modules
    )

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


def _tag_taxonomy() -> dict:
    try:
        from gradata._tag_taxonomy import get_taxonomy_summary

        return get_taxonomy_summary()
    except ImportError:
        return {}
