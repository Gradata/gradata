"""
Brain Manifest Generator (SDK Layer).
======================================
Generates brain.manifest.json — machine-readable brain spec.
Portable — uses _paths instead of hardcoded paths.

Functions promoted from brain shim (S39+):
- _quality_metrics(): date-prefix regex for accurate lesson counting
- _behavioral_contract(): counts CARL rules (any brain with CARL)
- generate_manifest(): DB session cross-check, full paths/bootstrap/api_requirements
- validate_manifest(): checks for "paths" key
- write_manifest(): convenience writer
- MANIFEST_PATH: constant
"""

import json
import re
import sqlite3
from datetime import UTC, datetime

# Use module reference so set_brain_dir() updates propagate at call time
import gradata._paths as _p
from gradata._paths import BrainContext


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
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT type, COUNT(*) as cnt FROM events GROUP BY type").fetchall()
        for row in rows:
            result["by_type"][row["type"]] = row["cnt"]
            result["total"] += row["cnt"]
        conn.close()
    except Exception:
        pass
    return result


def _get_tables(ctx: "BrainContext | None" = None) -> list[str]:
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _compute_fda(ctx: "BrainContext | None" = None, window: int = 20) -> float | None:
    """Compute First Draft Acceptance rate from OUTPUT/CORRECTION correlation.

    FDA = sessions where outputs had no major corrections / total measured sessions.

    Returns None if fewer than 3 sessions with outputs (insufficient data).
    Excludes system sessions to avoid inflation.
    as-is/minor corrections still count as "accepted".
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))

        # Get the most recent N real sessions with outputs (exclude system sessions)
        # Uses HAVING COUNT >= 2 to skip phantom sessions with stray events
        sessions_with_outputs = conn.execute("""
            SELECT e.session FROM events e
            LEFT JOIN session_metrics sm ON e.session = sm.session
            WHERE e.type = 'OUTPUT'
              AND typeof(e.session) = 'integer'
              AND (sm.session_type IS NULL OR sm.session_type != 'systems')
            GROUP BY e.session HAVING COUNT(*) >= 2
            ORDER BY e.session DESC LIMIT ?
        """, (window,)).fetchall()

        if len(sessions_with_outputs) < 3:
            conn.close()
            return None

        accepted = 0
        for (session,) in sessions_with_outputs:
            # Check for corrections — use severity if available, otherwise any correction counts
            has_severity = conn.execute("""
                SELECT COUNT(*) FROM events
                WHERE type = 'CORRECTION' AND session = ?
                  AND json_extract(data_json, '$.severity') IS NOT NULL
            """, (session,)).fetchone()[0]

            if has_severity > 0:
                # Severity data exists: only major/moderate/discarded count against acceptance
                major_corrections = conn.execute("""
                    SELECT COUNT(*) FROM events
                    WHERE type = 'CORRECTION' AND session = ?
                      AND json_extract(data_json, '$.severity') IN ('moderate', 'major', 'discarded')
                """, (session,)).fetchone()[0]
            else:
                # No severity data: any correction counts against acceptance
                major_corrections = conn.execute("""
                    SELECT COUNT(*) FROM events
                    WHERE type = 'CORRECTION' AND session = ?
                """, (session,)).fetchone()[0]

            if major_corrections == 0:
                accepted += 1

        conn.close()
        total = len(sessions_with_outputs)
        return round(accepted / total, 3) if total > 0 else None
    except Exception:
        return None


def _categories_extinct(ctx: "BrainContext | None" = None, window: int = 20) -> list[str]:
    """Find correction categories with zero corrections in the last N sessions.

    These are error types the brain has eliminated — strongest proof of learning.
    Uses correction recency (not lesson state) per adversary review.
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        max_session = conn.execute(
            "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
        ).fetchone()[0] or 0
        min_session = max(1, max_session - window + 1)

        # All categories ever
        all_cats = {r[0] for r in conn.execute("""
            SELECT DISTINCT json_extract(data_json, '$.category')
            FROM events WHERE type = 'CORRECTION'
              AND json_extract(data_json, '$.category') IS NOT NULL
        """).fetchall()}

        # Categories in recent window
        recent_cats = {r[0] for r in conn.execute("""
            SELECT DISTINCT json_extract(data_json, '$.category')
            FROM events WHERE type = 'CORRECTION' AND session >= ?
              AND json_extract(data_json, '$.category') IS NOT NULL
        """, (min_session,)).fetchall()}

        conn.close()
        extinct = sorted(all_cats - recent_cats)
        return extinct
    except Exception:
        return []


def _compound_score(
    correction_rate: float | None,
    fda: float | None,
    lessons_graduated: int,
    lessons_active: int,
    sessions: int,
    total_corrections: int = 0,
) -> float:
    """Compute weighted brain health score (0-100).

    Requires min 5 corrections in history before awarding CRO points
    (prevents gaming by never correcting).
    """
    score = 0.0
    # Correction improvement (0-25 pts)
    if correction_rate is not None and total_corrections >= 5:
        score += max(0.0, 1.0 - correction_rate) * 25
    # FDA (0-30 pts)
    if fda is not None:
        score += fda * 30
    # Graduation (0-20 pts)
    total_lessons = lessons_graduated + lessons_active
    if total_lessons > 0:
        score += min(1.0, lessons_graduated / max(20, total_lessons)) * 20
    # Active lessons (0-15 pts)
    score += min(1.0, lessons_active / 10) * 15
    # Maturity (0-10 pts)
    score += min(1.0, sessions / 200) * 10
    return round(score, 1)


def _lesson_distribution(ctx: "BrainContext | None" = None) -> dict[str, int]:
    """Count lessons by state from lessons.md."""
    dist: dict[str, int] = {}
    working_dir = ctx.working_dir if ctx else _p.WORKING_DIR
    lessons_file = working_dir / ".claude" / "lessons.md"
    try:
        if lessons_file.exists():
            text = lessons_file.read_text(encoding="utf-8")
            for state in ("INSTINCT", "PATTERN", "RULE", "UNTESTABLE"):
                count = len(re.findall(
                    rf"^\[20\d{{2}}-\d{{2}}-\d{{2}}\]\s+\[{state}",
                    text, re.MULTILINE
                ))
                if count > 0:
                    dist[state] = count
    except Exception:
        pass
    return dist


def _correction_rate_trend(ctx: "BrainContext | None" = None, window: int = 10) -> dict | None:
    """Compare current CRO window to baseline window."""
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        max_session = conn.execute(
            "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
        ).fetchone()[0] or 0

        if max_session < window * 2:
            conn.close()
            return None

        def _cro(min_s, max_s):
            outputs = conn.execute(
                "SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session BETWEEN ? AND ?",
                (min_s, max_s)
            ).fetchone()[0] or 0
            corrections = conn.execute(
                "SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session BETWEEN ? AND ?",
                (min_s, max_s)
            ).fetchone()[0] or 0
            return round(corrections / outputs, 4) if outputs > 0 else None

        current = _cro(max_session - window + 1, max_session)
        baseline = _cro(max_session - window * 2 + 1, max_session - window)
        conn.close()

        if current is None or baseline is None:
            return None

        direction = "improving" if current < baseline else ("stable" if current == baseline else "degrading")
        return {
            "current_window": current,
            "baseline_window": baseline,
            "direction": direction,
            "sessions_in_window": window,
        }
    except Exception:
        return None


def _quality_metrics(ctx: "BrainContext | None" = None) -> dict:
    """Compute quality metrics from events.

    Uses date-prefix regex for lesson counting to avoid matching format
    descriptions. This is the S39-fixed version promoted from brain shim.
    """
    result: dict = {
        "correction_rate": None,
        "lessons_graduated": 0,
        "lessons_active": 0,
        "first_draft_acceptance": None,
        "compound_score": None,
        "categories_extinct": [],
        "lesson_distribution": {},
        "correction_rate_trend": None,
    }

    total_corrections = 0
    sessions_trained = 0
    try:
        # Compute correction rate directly from DB (ctx-aware)
        # Use top-N real sessions (by event count) to avoid phantom session IDs
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        recent_sessions = [r[0] for r in conn.execute("""
            SELECT session FROM events
            WHERE typeof(session)='integer'
            GROUP BY session HAVING COUNT(*) >= 2
            ORDER BY session DESC LIMIT 10
        """).fetchall()]
        if recent_sessions:
            placeholders = ",".join("?" * len(recent_sessions))
            total_corrections = conn.execute(
                f"SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session IN ({placeholders})",
                recent_sessions
            ).fetchone()[0] or 0
            total_outputs = conn.execute(
                f"SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session IN ({placeholders})",
                recent_sessions
            ).fetchone()[0] or 0
            if total_outputs > 0:
                result["correction_rate"] = round(total_corrections / total_outputs, 3)
        conn.close()
    except Exception:
        pass

    # FDA (fixed: correlation-based, excludes system sessions)
    result["first_draft_acceptance"] = _compute_fda(ctx=ctx)

    # Categories extinct (correction recency, not lesson state)
    result["categories_extinct"] = _categories_extinct(ctx=ctx)

    # Correction rate trend
    result["correction_rate_trend"] = _correction_rate_trend(ctx=ctx)

    # Count lessons — date-prefix pattern avoids matching format descriptions
    working_dir = ctx.working_dir if ctx else _p.WORKING_DIR
    lessons_file = working_dir / ".claude" / "lessons.md"
    archive_file = working_dir / ".claude" / "lessons-archive.md"
    try:
        if lessons_file.exists():
            text = lessons_file.read_text(encoding="utf-8")
            result["lessons_active"] = len(re.findall(
                r"^\[20\d{2}-\d{2}-\d{2}\]\s+\[(?:PATTERN|INSTINCT):", text, re.MULTILINE
            ))
        if archive_file.exists():
            text = archive_file.read_text(encoding="utf-8")
            result["lessons_graduated"] = len(re.findall(
                r"^\[20\d{2}-\d{2}-\d{2}\]", text, re.MULTILINE
            ))
    except Exception:
        pass

    # Lesson distribution
    result["lesson_distribution"] = _lesson_distribution(ctx=ctx)

    # Get sessions count for compound score
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        sessions_trained = conn.execute(
            "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
        ).fetchone()[0] or 0
        if total_corrections == 0:
            total_corrections = conn.execute(
                "SELECT COUNT(*) FROM events WHERE type='CORRECTION'"
            ).fetchone()[0] or 0
        conn.close()
    except Exception:
        pass

    # Compound score
    result["compound_score"] = _compound_score(
        correction_rate=result["correction_rate"],
        fda=result["first_draft_acceptance"],
        lessons_graduated=result["lessons_graduated"],
        lessons_active=result["lessons_active"],
        sessions=sessions_trained,
        total_corrections=total_corrections,
    )

    return result


def _behavioral_contract(ctx: "BrainContext | None" = None) -> dict:
    """Count CARL rules. Works for any brain with CARL directory structure.

    Looks for .carl/ relative to WORKING_DIR and domain/carl/ for domain rules.
    """
    result = {"safety_rules": 0, "global_rules": 0, "domain_rules": 0, "total": 0}
    working_dir = ctx.working_dir if ctx else _p.WORKING_DIR
    carl_dir = working_dir / ".carl"
    if carl_dir.exists():
        for f in carl_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                text = f.read_text(encoding="utf-8", errors="replace")
                count = len(re.findall(r"_RULE_\d+=", text))
                if "safety" in f.name.lower():
                    result["safety_rules"] = count
                elif "global" in f.name.lower():
                    result["global_rules"] = count
                result["total"] += count

    # Domain CARL rules
    domain_carl = working_dir / "domain" / "carl"
    if domain_carl.exists():
        for f in domain_carl.iterdir():
            if f.is_file():
                text = f.read_text(encoding="utf-8", errors="replace")
                count = len(re.findall(r"_RULE_\d+=", text))
                result["domain_rules"] += count
                result["total"] += count
    return result


def _memory_composition(ctx: "BrainContext | None" = None) -> dict:
    result = {"episodic": 0, "semantic": 0, "procedural": 0, "strategic": 0}
    mappings = {
        "episodic": ["sessions", "metrics", "pipeline", "demos"],
        "semantic": ["prospects", "personas", "competitors", "objections"],
        "procedural": ["emails", "messages", "templates"],
        "strategic": ["learnings", "vault"],
    }
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    for mem_type, dirs in mappings.items():
        for d in dirs:
            dp = brain_dir / d
            if dp.exists():
                result[mem_type] += len(list(dp.glob("*.md")))
    return result


def _rag_status(ctx: "BrainContext | None" = None) -> dict:
    """RAG status. Chunks counted from SQLite brain_embeddings table."""
    result = {
        "active": False, "provider": "unknown", "model": "unknown",
        "dimensions": 0, "chunks_indexed": 0,
        "fts5_enabled": True,
    }
    try:
        from gradata._config import EMBEDDING_DIMS, EMBEDDING_MODEL, EMBEDDING_PROVIDER, RAG_ACTIVE
        result["active"] = RAG_ACTIVE
        result["provider"] = EMBEDDING_PROVIDER
        result["model"] = EMBEDDING_MODEL
        result["dimensions"] = EMBEDDING_DIMS
    except Exception:
        pass
    # Count embeddings from SQLite
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()
        result["chunks_indexed"] = row[0] if row else 0
        conn.close()
    except Exception:
        pass
    return result


def _tag_taxonomy() -> dict:
    try:
        from gradata._tag_taxonomy import get_taxonomy_summary
        return get_taxonomy_summary()
    except ImportError:
        return {}


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
        conn = sqlite3.connect(str(db))
        db_max = conn.execute(
            "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
        ).fetchone()[0] or 0
        conn.close()
        if db_max > version_info["sessions_trained"]:
            version_info["sessions_trained"] = db_max
    except Exception:
        pass

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
            # Add domain-specific API keys here, e.g.:
            # "crm": {"env_var": "CRM_API_KEY", "required": False},
            # "outreach": {"env_var": "OUTREACH_API_KEY", "required": False},
        },
        "bootstrap": [
            {"step": "set_env_vars", "desc": "Set BRAIN_DIR, WORKING_DIR, DOMAIN_DIR", "required": True},
            {"step": "init_db", "command": "python start.py init", "required": True},
            {"step": "embed_brain", "command": "python embed.py --full", "required": rag.get("active", False)},
            {"step": "rebuild_fts", "command": "python -c \"from query import fts_rebuild; fts_rebuild()\"", "required": True},
            {"step": "validate", "command": "python config_validator.py", "required": False},
        ],
        "compatibility": {
            "python": ">=3.11",
            "search": "FTS5 (sqlite-vec planned)",
            "platform": "any",
        },
        # A2A Agent Card (Google Agent-to-Agent protocol, Linux Foundation)
        # Near-zero cost metadata — keeps interface boundary clean for future
        # multi-brain orchestration (Phase 5: Avengers vision)
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

    required_keys = ["schema_version", "metadata", "quality", "database", "rag", "paths"]
    for k in required_keys:
        if k not in manifest:
            issues.append(f"Missing required key: {k}")

    if manifest.get("schema_version") != "1.0.0":
        issues.append(f"Unknown schema version: {manifest.get('schema_version')}")

    return issues
