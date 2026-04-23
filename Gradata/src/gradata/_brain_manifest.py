"""
Brain Manifest Generator (SDK Layer).
======================================
Generates brain.manifest.json -- machine-readable brain spec.
Portable -- uses _paths instead of hardcoded paths.

Functions promoted from brain shim (S39+):
- _quality_metrics(): date-prefix regex for accurate lesson counting
- _behavioral_contract(): counts CARL rules (any brain with CARL)
- generate_manifest(): DB session cross-check, full paths/bootstrap/api_requirements
- validate_manifest(): checks for "paths" key
- write_manifest(): convenience writer
- MANIFEST_PATH: constant

Split into 4 files for maintainability (<500 lines each):
- _manifest_helpers.py: constants, _session_window, _read_version, _count_events, _get_tables
- _manifest_quality.py: quality scoring (_compound_score, _compute_fda, etc.)
- _manifest_metrics.py: lesson/correction metrics, brain introspection
- _brain_manifest.py: public API (this file)
"""

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import gradata._paths as _p
from gradata._db import get_connection

_log = logging.getLogger(__name__)

# Re-export helpers so existing imports from _brain_manifest still work
from gradata._manifest_helpers import (
    _count_events,
    _get_tables,
    _read_version,
    _sdk_capabilities,
    _tag_taxonomy,
)
from gradata._manifest_metrics import (
    _behavioral_contract,
    _memory_composition,
    _quality_metrics,
    _rag_status,
)

if TYPE_CHECKING:
    from gradata._paths import BrainContext


def generate_manifest(*, domain: str = "General", ctx: "BrainContext | None" = None) -> dict:
    """Generate the complete brain manifest.

    Includes DB session cross-check, behavioral_contract, full paths,
    bootstrap steps, and api_requirements. Promoted from brain shim S39.

    Args:
        domain: Domain label for the manifest metadata (default "General").
    """
    version_info = _read_version(ctx=ctx)
    events = _count_events(ctx=ctx)

    # Cross-check session count: prefer DB max if higher than VERSION.md
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        db_max = (
            conn.execute(
                "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
            ).fetchone()[0]
            or 0
        )
        conn.close()
        if db_max > version_info["sessions_trained"]:
            version_info["sessions_trained"] = db_max
    except Exception as e:
        _log.debug("Session count DB cross-check failed (non-fatal): %s", e)

    quality = _quality_metrics(ctx=ctx)
    memory = _memory_composition(ctx=ctx)
    rag = _rag_status(ctx=ctx)
    contract = _behavioral_contract(ctx=ctx)
    tables = _get_tables(ctx=ctx)

    manifest = {
        "schema_version": "1.0.0",
        "metadata": {
            "brain_version": version_info["version"],
            "domain": domain,
            "maturity_phase": version_info["maturity_phase"],
            "sessions_trained": version_info["sessions_trained"],
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "quality": quality,
        "memory_composition": memory,
        "database": {
            "engine": "sqlite3",
            "path": "system.db",
            "tables": tables,
            "event_types": len(events["by_type"]),
            "total_events": events["total"],
        },
        "rag": rag,
        "behavioral_contract": contract,
        "tag_taxonomy": _tag_taxonomy(),
        "paths": {
            "brain_dir": "$BRAIN_DIR",
            "domain_dir": "$DOMAIN_DIR",
            "working_dir": "$WORKING_DIR",
        },
        "api_requirements": {
            "gemini": {
                "env_var": "GEMINI_API_KEY",
                "required": rag.get("provider") == "gemini",
                "tier": "free",
            },
        },
        "bootstrap": [
            {
                "step": "set_env_vars",
                "desc": "Set BRAIN_DIR, WORKING_DIR, DOMAIN_DIR",
                "required": True,
            },
            {"step": "init_db", "command": "python start.py init", "required": True},
            {
                "step": "embed_brain",
                "command": "python embed.py --full",
                "required": rag.get("active", False),
            },
            {
                "step": "rebuild_fts",
                "command": 'python -c "from query import fts_rebuild; fts_rebuild()"',
                "required": True,
            },
            {"step": "validate", "command": "python config_validator.py", "required": False},
        ],
        "compatibility": {
            "python": ">=3.11",
            "search": "FTS5 (sqlite-vec planned)",
            "platform": "any",
        },
        # A2A Agent Card (Google Agent-to-Agent protocol, Linux Foundation)
        # Near-zero cost metadata -- keeps interface boundary clean for future
        # multi-brain orchestration (Phase 5: Avengers vision)
        "sdk_capabilities": _sdk_capabilities(),
        "agent_card": {
            "name": f"gradata-{domain.lower()}",
            "description": f"Trained AI brain for {domain} domain",
            "version": version_info["version"],
            "protocol": "a2a/1.0",
            "capabilities": {
                "search": True,
                "correct": True,
                "generate_context": True,
                "apply_rules": True,
                "export": True,
                "rl_routing": True,
                "context_degradation": True,
                "observation_capture": True,
                "correction_clustering": True,
                "lesson_discrimination": True,
                "memory_taxonomy": True,
                "plan_reconciliation": True,
            },
            "quality_summary": {
                "maturity": version_info["maturity_phase"],
                "sessions": version_info["sessions_trained"],
                "correction_rate": quality.get("correction_rate"),
                "first_draft_acceptance": quality.get("first_draft_acceptance"),
                "lessons_active": quality.get("lessons_active", 0),
                "lessons_graduated": quality.get("lessons_graduated", 0),
            },
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or task description"},
                    "draft": {"type": "string", "description": "AI draft for correction"},
                    "final": {"type": "string", "description": "User-edited final version"},
                },
            },
        },
    }
    return manifest


def write_manifest(manifest: dict | None = None, ctx: "BrainContext | None" = None):
    """Write manifest to brain/brain.manifest.json."""
    if manifest is None:
        manifest = generate_manifest(ctx=ctx)
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    (brain_dir / "brain.manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
    return brain_dir / "brain.manifest.json"


# Module-level constant for backward compat (resolves at import time)
MANIFEST_PATH = _p.BRAIN_DIR / "brain.manifest.json"


def validate_manifest(ctx: "BrainContext | None" = None) -> list[str]:
    """Validate existing manifest against current state."""
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    manifest_path = brain_dir / "brain.manifest.json"
    issues = []
    if not manifest_path.exists():
        return ["brain.manifest.json does not exist"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    required_keys = ["schema_version", "metadata", "quality", "database", "rag", "paths", "proof"]
    for k in required_keys:
        if k not in manifest:
            issues.append(f"Missing required key: {k}")

    if manifest.get("schema_version") != "1.0.0":
        issues.append(f"Unknown schema version: {manifest.get('schema_version')}")

    return issues
