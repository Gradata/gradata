"""
Brain Manifest Generator (SDK Layer).
======================================
Generates brain.manifest.json -- machine-readable brain spec.
Portable -- uses _paths instead of hardcoded paths.

Functions promoted from brain shim (S39+):
- _quality_metrics(): date-prefix regex for accurate lesson counting
- generate_manifest(): DB session cross-check, full paths/bootstrap/api_requirements
- validate_manifest(): checks for "paths" key
- write_manifest(): convenience writer
- MANIFEST_PATH: constant
"""

import json
import math
import re
import statistics
from datetime import UTC, datetime

from . import _paths as _p
from ._db import get_connection
from ._manifest_helpers import (
    _sdk_capabilities,
    _session_window,
)
from ._manifest_quality import (
    _categories_extinct,
    _compound_score,
    _compute_fda,
    _counterfactual_percentile,
    _per_session_density,
    _severity_difficulty_weight,
    _severity_ratio,
    _transfer_score,
)
from ._stats import trend_analysis as _trend_analysis


def _correction_rate_trend(ctx: "_p.BrainContext | None" = None, window: int = 10) -> dict | None:
    """Compare current CRO window to baseline window."""
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        max_session, _ = _session_window(conn, window)

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


def _temporal_provenance(ctx: "_p.BrainContext | None" = None) -> dict:
    """Measure temporal authenticity of brain training via 3rd-party signals."""
    result = {
        "distinct_days": 0,
        "external_sources": [],
        "session_spread_days": 0,
        "avg_gap_hours": 0.0,
        "external_event_ratio": 0.0,
        "provenance_score": 0.0,
    }
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)

        agg = conn.execute("""
            SELECT COUNT(DISTINCT DATE(ts)), MIN(ts), MAX(ts), COUNT(*)
            FROM events WHERE typeof(session)='integer'
        """).fetchone()
        days = agg[0] or 0
        total_events = agg[3] or 0
        result["distinct_days"] = days
        if agg[1] and agg[2]:
            try:
                t0 = datetime.fromisoformat(str(agg[1]).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(agg[2]).replace("Z", "+00:00"))
                result["session_spread_days"] = max(0, (t1 - t0).days)
            except (ValueError, TypeError):
                pass

        internal_prefixes = ("event:", "correction_detector", "brain", "session", "gate", "supersede")
        source_rows = conn.execute("""
            SELECT source, COUNT(*) as cnt FROM events
            WHERE source IS NOT NULL AND source != ''
            GROUP BY source
        """).fetchall()
        external = []
        ext_count = 0
        for r in source_rows:
            if r[0] and not any(r[0].startswith(p) for p in internal_prefixes):
                external.append(r[0])
                ext_count += r[1]
        result["external_sources"] = sorted(external)
        if total_events > 0 and ext_count > 0:
            result["external_event_ratio"] = round(ext_count / total_events, 3)

        session_starts = conn.execute("""
            SELECT MIN(ts) as first_ts FROM events
            WHERE typeof(session)='integer'
            GROUP BY session
            ORDER BY session
        """).fetchall()
        if len(session_starts) >= 2:

            gaps = []
            for i in range(1, len(session_starts)):
                try:
                    t0 = datetime.fromisoformat(str(session_starts[i - 1][0]).replace("Z", "+00:00"))
                    t1 = datetime.fromisoformat(str(session_starts[i][0]).replace("Z", "+00:00"))
                    gaps.append((t1 - t0).total_seconds() / 3600)
                except (ValueError, TypeError):
                    continue
            if gaps:
                result["avg_gap_hours"] = round(statistics.mean(gaps), 1)

        conn.close()

        day_score = min(1.0, days / 30)
        spread_score = min(1.0, result["session_spread_days"] / 60)
        external_score = min(1.0, len(external) / 3)
        ratio_score = min(1.0, result["external_event_ratio"] / 0.10)
        gap_score = min(1.0, result["avg_gap_hours"] / 8) if result["avg_gap_hours"] > 0 else 0.0

        result["provenance_score"] = round(
            0.25 * day_score + 0.20 * spread_score + 0.20 * external_score
            + 0.15 * ratio_score + 0.20 * gap_score, 3
        )

    except Exception:
        pass
    return result


def _outcome_correlation(ctx: "_p.BrainContext | None" = None, window: int = 20) -> dict | None:
    """Correlate compound score trend with user-reported outcome metrics."""
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        rows = conn.execute("""
            SELECT session, json_extract(data_json, '$.value') as val
            FROM events WHERE type = 'OUTCOME_METRIC'
              AND typeof(session) = 'integer'
              AND json_extract(data_json, '$.value') IS NOT NULL
            ORDER BY session
        """).fetchall()
        conn.close()

        if len(rows) < 5:
            return None

        [r[0] for r in rows]
        values = [float(r[1]) for r in rows]

        slope, p_value = _trend_analysis(values)

        n = len(values)
        x = list(range(n))
        mx = sum(x) / n
        my = sum(values) / n
        sx = (sum((xi - mx) ** 2 for xi in x) / (n - 1)) ** 0.5
        sy = (sum((vi - my) ** 2 for vi in values) / (n - 1)) ** 0.5
        if sx == 0 or sy == 0:
            r = 0.0
        else:
            r = sum((xi - mx) * (vi - my) for xi, vi in zip(x, values, strict=False)) / ((n - 1) * sx * sy)

        return {
            "outcome_trend_slope": round(slope, 4),
            "outcome_trend_p": round(p_value, 4),
            "outcome_score_correlation": round(r, 3),
            "data_points": n,
            "improving": slope < 0 and p_value < 0.10,
        }
    except Exception:
        return None


def _quality_metrics(ctx: "_p.BrainContext | None" = None) -> dict:
    """Compute quality metrics from events."""
    result: dict = {
        "correction_rate": None,
        "lessons_graduated": 0,
        "lessons_active": 0,
        "first_draft_acceptance": None,
        "compound_score": None,
        "categories_extinct": [],
        "lesson_distribution": {},
        "correction_rate_trend": None,
        "severity_ratio": None,
        "transfer_score": None,
        "density_trend_length": 0,
        "score_confidence": None,
        "temporal_provenance": None,
        "difficulty_weight": None,
        "outcome_correlation": None,
        "counterfactual": None,
    }

    total_corrections = 0
    sessions_trained = 0
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
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

    result["first_draft_acceptance"] = _compute_fda(ctx=ctx)
    result["categories_extinct"] = _categories_extinct(ctx=ctx)
    result["correction_rate_trend"] = _correction_rate_trend(ctx=ctx)

    lessons_file = ctx.lessons_file if ctx else _p.LESSONS_FILE
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    archive_file = brain_dir / "lessons-archive.md"
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

    result["lesson_distribution"] = {}
    _ld_lf = ctx.lessons_file if ctx else _p.LESSONS_FILE
    try:
        if _ld_lf.exists():
            _ld_text = _ld_lf.read_text(encoding="utf-8")
            for _ld_state in ("INSTINCT", "PATTERN", "RULE", "UNTESTABLE"):
                _ld_count = len(re.findall(
                    rf"^\[20\d{{2}}-\d{{2}}-\d{{2}}\]\s+\[{_ld_state}",
                    _ld_text, re.MULTILINE,
                ))
                if _ld_count > 0:
                    result["lesson_distribution"][_ld_state] = _ld_count
    except Exception:
        pass

    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
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

    density_trend = _per_session_density(ctx=ctx)
    severity = _severity_ratio(ctx=ctx)
    transfer = _transfer_score(ctx=ctx)

    result["severity_ratio"] = severity
    result["transfer_score"] = transfer
    result["density_trend_length"] = len(density_trend)
    result["temporal_provenance"] = _temporal_provenance(ctx=ctx)
    result["difficulty_weight"] = _severity_difficulty_weight(ctx=ctx)

    result["compound_score"] = _compound_score(
        correction_rate=result["correction_rate"],
        severity_ratio=severity,
        lessons_graduated=result["lessons_graduated"],
        lessons_active=result["lessons_active"],
        sessions=sessions_trained,
        total_corrections=total_corrections,
        correction_density_trend=density_trend,
        categories_extinct=len(result.get("categories_extinct", [])),
        transfer=transfer,
    )

    _sc_score = result["compound_score"]
    if sessions_trained < 3:
        result["score_confidence"] = {
            "score": round(_sc_score, 1),
            "ci_low": 0.0,
            "ci_high": 100.0,
            "confidence": "insufficient_data",
        }
    else:
        _sc_margin = 30.0 / math.sqrt(max(1, sessions_trained))
        result["score_confidence"] = {
            "score": round(_sc_score, 1),
            "ci_low": round(max(0.0, _sc_score - _sc_margin), 1),
            "ci_high": round(min(100.0, _sc_score + _sc_margin), 1),
            "confidence": "high" if sessions_trained >= 50 else "medium" if sessions_trained >= 20 else "low",
        }
    result["outcome_correlation"] = _outcome_correlation(ctx=ctx)
    result["counterfactual"] = _counterfactual_percentile(
        result["compound_score"], sessions_trained, ctx=ctx
    )

    return result


def _memory_composition(ctx: "_p.BrainContext | None" = None) -> dict:
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


def generate_manifest(*, domain: str = "General", ctx: "_p.BrainContext | None" = None) -> dict:
    """Generate the complete brain manifest.

    Includes DB session cross-check, behavioral_contract, full paths,
    bootstrap steps, and api_requirements. Promoted from brain shim S39.

    Args:
        domain: Domain label for the manifest metadata (default "General").
    """
    version_info: dict = {"version": "unknown", "sessions_trained": 0, "maturity_phase": "INFANT"}
    _bd = ctx.brain_dir if ctx else _p.BRAIN_DIR
    _vf = _bd / "VERSION.md"
    if _vf.exists():
        _vt = _vf.read_text(encoding="utf-8", errors="replace")
        _m = re.search(r"v(\d+\.\d+\.\d+)", _vt)
        if _m:
            version_info["version"] = f"v{_m.group(1)}"
        _m = re.search(r"[Ss]ession\s+(\d+)", _vt)
        if _m:
            version_info["sessions_trained"] = int(_m.group(1))
        for _phase in ("STABLE", "MATURE", "ADOLESCENT", "INFANT"):
            if _phase in _vt.upper():
                version_info["maturity_phase"] = _phase
                break
    events: dict = {"total": 0, "by_type": {}}
    try:
        _ce_conn = get_connection(ctx.db_path if ctx else _p.DB_PATH)
        for _ce_row in _ce_conn.execute("SELECT type, COUNT(*) as cnt FROM events GROUP BY type").fetchall():
            events["by_type"][_ce_row["type"]] = _ce_row["cnt"]
            events["total"] += _ce_row["cnt"]
        _ce_conn.close()
    except Exception:
        pass

    # Cross-check session count: prefer DB max if higher than VERSION.md
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
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
    rag = {"active": False, "provider": "unknown", "model": "unknown",
           "dimensions": 0, "chunks_indexed": 0, "fts5_enabled": True}
    try:
        from ._config import EMBEDDING_DIMS, EMBEDDING_MODEL, EMBEDDING_PROVIDER, RAG_ACTIVE
        rag["active"] = RAG_ACTIVE
        rag["provider"] = EMBEDDING_PROVIDER
        rag["model"] = EMBEDDING_MODEL
        rag["dimensions"] = EMBEDDING_DIMS
    except Exception:
        pass
    try:
        _rs_conn = get_connection(ctx.db_path if ctx else _p.DB_PATH)
        _rs_row = _rs_conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()
        rag["chunks_indexed"] = _rs_row[0] if _rs_row else 0
        _rs_conn.close()
    except Exception:
        pass
    contract = {"safety_rules": 0, "global_rules": 0, "domain_rules": 0, "total": 0}
    _bc_wd = ctx.working_dir if ctx else _p.WORKING_DIR
    _bc_carl = _bc_wd / ".carl"
    if _bc_carl.exists():
        for _bc_f in _bc_carl.iterdir():
            if _bc_f.is_file() and not _bc_f.name.startswith("."):
                _bc_count = len(re.findall(r"_RULE_\d+=", _bc_f.read_text(encoding="utf-8", errors="replace")))
                if "safety" in _bc_f.name.lower():
                    contract["safety_rules"] = _bc_count
                elif "global" in _bc_f.name.lower():
                    contract["global_rules"] = _bc_count
                contract["total"] += _bc_count
    _bc_dcarl = _bc_wd / "domain" / "carl"
    if _bc_dcarl.exists():
        for _bc_f in _bc_dcarl.iterdir():
            if _bc_f.is_file():
                _bc_count = len(re.findall(r"_RULE_\d+=", _bc_f.read_text(encoding="utf-8", errors="replace")))
                contract["domain_rules"] += _bc_count
                contract["total"] += _bc_count
    try:
        from ._tag_taxonomy import get_taxonomy_summary
        _tt_summary = get_taxonomy_summary()
    except ImportError:
        _tt_summary = {}
    try:
        _gt_conn = get_connection(ctx.db_path if ctx else _p.DB_PATH)
        tables = [_r[0] for _r in _gt_conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        _gt_conn.close()
    except Exception:
        tables = []

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
        "tag_taxonomy": _tt_summary,
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


def write_manifest(manifest: dict | None = None, ctx: "_p.BrainContext | None" = None):
    """Write manifest to brain/brain.manifest.json."""
    if manifest is None:
        manifest = generate_manifest(ctx=ctx)
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    (brain_dir / "brain.manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
    return brain_dir / "brain.manifest.json"


MANIFEST_PATH = _p.BRAIN_DIR / "brain.manifest.json"


def validate_manifest(ctx: "_p.BrainContext | None" = None) -> list[str]:
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
