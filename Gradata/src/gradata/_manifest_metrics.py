"""
Brain Manifest Metrics.
========================
Lesson/correction metrics and brain introspection functions.
Split from _brain_manifest.py for file size compliance (<500 lines).
"""

import re
import statistics
from datetime import datetime
from typing import TYPE_CHECKING

import gradata._paths as _p
from gradata._db import get_connection
from gradata._manifest_helpers import _session_window
from gradata._manifest_quality import (
    _categories_extinct,
    _compound_score,
    _compute_fda,
    _counterfactual_percentile,
    _per_session_density,
    _score_confidence,
    _severity_difficulty_weight,
    _severity_ratio,
    _transfer_score,
)
from gradata._stats import trend_analysis as _trend_analysis

if TYPE_CHECKING:
    from gradata._paths import BrainContext


def _lesson_distribution(
    ctx: "BrainContext | None" = None,
    lessons_text: str | None = None,
) -> dict[str, int]:
    """Count lessons by state from lessons.md.

    If ``lessons_text`` is provided, it is used directly — avoids a second
    read_text() in the manifest generation path (see _quality_metrics).
    """
    dist: dict[str, int] = {}
    try:
        text = lessons_text
        if text is None:
            lessons_file = ctx.lessons_file if ctx else _p.LESSONS_FILE
            if lessons_file.exists():
                text = lessons_file.read_text(encoding="utf-8")
        if text:
            for state in ("INSTINCT", "PATTERN", "RULE", "UNTESTABLE"):
                count = len(
                    re.findall(rf"^\[20\d{{2}}-\d{{2}}-\d{{2}}\]\s+\[{state}", text, re.MULTILINE)
                )
                if count > 0:
                    dist[state] = count
    except Exception:
        pass
    return dist


def _correction_rate_trend(ctx: "BrainContext | None" = None, window: int = 10) -> dict | None:
    """Compare current CRO window to baseline window."""
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        max_session, _ = _session_window(conn, window)

        if max_session < window * 2:
            conn.close()
            return None

        def _cro(min_s, max_s):
            outputs = (
                conn.execute(
                    "SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session BETWEEN ? AND ?",
                    (min_s, max_s),
                ).fetchone()[0]
                or 0
            )
            corrections = (
                conn.execute(
                    "SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session BETWEEN ? AND ?",
                    (min_s, max_s),
                ).fetchone()[0]
                or 0
            )
            return round(corrections / outputs, 4) if outputs > 0 else None

        current = _cro(max_session - window + 1, max_session)
        baseline = _cro(max_session - window * 2 + 1, max_session - window)
        conn.close()

        if current is None or baseline is None:
            return None

        direction = (
            "improving"
            if current < baseline
            else ("stable" if current == baseline else "degrading")
        )
        return {
            "current_window": current,
            "baseline_window": baseline,
            "direction": direction,
            "sessions_in_window": window,
        }
    except Exception:
        return None


def _temporal_provenance(ctx: "BrainContext | None" = None) -> dict:
    """Measure temporal authenticity of brain training via 3rd-party signals.

    Checks that the brain's correction/learning history correlates with
    real-world activity -- external API calls, tool usage, deliverables
    pushed to 3rd-party systems (CRM, Gmail, Sheets, etc.).

    A genuine brain has corrections spread across calendar days with
    external integration activity. A gamed brain has corrections crammed
    into a few sessions with no external signals.

    Returns a dict with:
      - distinct_days: number of unique calendar days with events
      - external_sources: set of unique non-internal event sources
      - session_spread_days: calendar span from first to last session
      - avg_gap_hours: average hours between sessions
      - external_event_ratio: external events / total events
      - provenance_score: 0.0-1.0 composite authenticity signal
    """
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

        # Query 1: days, span, total in one pass
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

        # Query 2: source counts grouped -- filter in Python, no second query
        internal_prefixes = (
            "event:",
            "correction_detector",
            "brain",
            "session",
            "gate",
            "supersede",
        )
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

        # Average gap between sessions (hours)
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
                    t0 = datetime.fromisoformat(
                        str(session_starts[i - 1][0]).replace("Z", "+00:00")
                    )
                    t1 = datetime.fromisoformat(str(session_starts[i][0]).replace("Z", "+00:00"))
                    gaps.append((t1 - t0).total_seconds() / 3600)
                except (ValueError, TypeError):
                    continue
            if gaps:
                result["avg_gap_hours"] = round(statistics.mean(gaps), 1)

        conn.close()

        # Composite provenance score (0.0-1.0)
        # Rewards: many distinct days, wide calendar span, external sources, steady gaps
        day_score = min(1.0, days / 30)  # 30+ days = full credit
        spread_score = min(1.0, result["session_spread_days"] / 60)  # 60+ day span = full
        external_score = min(1.0, len(external) / 3)  # 3+ external sources = full
        ratio_score = min(1.0, result["external_event_ratio"] / 0.10)  # 10%+ external = full
        # Penalize cramming: if avg gap < 1 hour, likely automated/gamed
        gap_score = min(1.0, result["avg_gap_hours"] / 8) if result["avg_gap_hours"] > 0 else 0.0

        result["provenance_score"] = round(
            0.25 * day_score
            + 0.20 * spread_score
            + 0.20 * external_score
            + 0.15 * ratio_score
            + 0.20 * gap_score,
            3,
        )

    except Exception:
        pass
    return result


def _outcome_correlation(ctx: "BrainContext | None" = None, window: int = 20) -> dict | None:
    """Correlate compound score trend with user-reported outcome metrics.

    Users log external KPIs via OUTCOME_METRIC events (e.g., draft-to-approval
    time, edit cycles, user satisfaction). This function computes Pearson
    correlation between compound score improvement and outcome improvement.

    Returns None if fewer than 5 OUTCOME_METRIC events exist.
    """
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

        values = [float(r[1]) for r in rows]

        # Compute trend direction for outcomes
        slope, p_value = _trend_analysis(values)

        # Pearson correlation between session index and outcome value
        n = len(values)
        x = list(range(n))
        mx = sum(x) / n
        my = sum(values) / n
        sx = (sum((xi - mx) ** 2 for xi in x) / (n - 1)) ** 0.5
        sy = (sum((vi - my) ** 2 for vi in values) / (n - 1)) ** 0.5
        if sx == 0 or sy == 0:
            r = 0.0
        else:
            r = sum((xi - mx) * (vi - my) for xi, vi in zip(x, values, strict=False)) / (
                (n - 1) * sx * sy
            )

        return {
            "outcome_trend_slope": round(slope, 4),
            "outcome_trend_p": round(p_value, 4),
            "outcome_score_correlation": round(r, 3),
            "data_points": n,
            "improving": slope < 0 and p_value < 0.10,  # negative slope = fewer edits = better
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
        # Compute correction rate directly from DB (ctx-aware)
        # Use top-N real sessions (by event count) to avoid phantom session IDs
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        recent_sessions = [
            r[0]
            for r in conn.execute("""
            SELECT session FROM events
            WHERE typeof(session)='integer'
            GROUP BY session HAVING COUNT(*) >= 2
            ORDER BY session DESC LIMIT 10
        """).fetchall()
        ]
        if recent_sessions:
            placeholders = ",".join("?" * len(recent_sessions))
            total_corrections = (
                conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session IN ({placeholders})",
                    recent_sessions,
                ).fetchone()[0]
                or 0
            )
            total_outputs = (
                conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session IN ({placeholders})",
                    recent_sessions,
                ).fetchone()[0]
                or 0
            )
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

    # Count lessons -- date-prefix pattern avoids matching format descriptions.
    # Read lessons.md once and reuse the text for _lesson_distribution below.
    lessons_file = ctx.lessons_file if ctx else _p.LESSONS_FILE
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    archive_file = brain_dir / "lessons-archive.md"
    lessons_text: str | None = None
    try:
        if lessons_file.exists():
            lessons_text = lessons_file.read_text(encoding="utf-8")
            result["lessons_active"] = len(
                re.findall(
                    r"^\[20\d{2}-\d{2}-\d{2}\]\s+\[(?:PATTERN|INSTINCT):",
                    lessons_text,
                    re.MULTILINE,
                )
            )
        if archive_file.exists():
            text = archive_file.read_text(encoding="utf-8")
            result["lessons_graduated"] = len(
                re.findall(r"^\[20\d{2}-\d{2}-\d{2}\]", text, re.MULTILINE)
            )
    except Exception:
        pass

    # Lesson distribution — reuse already-read text (avoids second disk read).
    result["lesson_distribution"] = _lesson_distribution(ctx=ctx, lessons_text=lessons_text)

    # Get sessions count for compound score
    try:
        import contextlib as _ctxlib

        db = ctx.db_path if ctx else _p.DB_PATH
        with _ctxlib.closing(get_connection(db)) as conn:
            sessions_trained = (
                conn.execute(
                    "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
                ).fetchone()[0]
                or 0
            )
            if total_corrections == 0:
                total_corrections = (
                    conn.execute("SELECT COUNT(*) FROM events WHERE type='CORRECTION'").fetchone()[
                        0
                    ]
                    or 0
                )
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

    result["score_confidence"] = _score_confidence(result["compound_score"], sessions_trained)
    result["outcome_correlation"] = _outcome_correlation(ctx=ctx)
    result["counterfactual"] = _counterfactual_percentile(
        result["compound_score"], sessions_trained, ctx=ctx
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
        "active": False,
        "provider": "unknown",
        "model": "unknown",
        "dimensions": 0,
        "chunks_indexed": 0,
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
        conn = get_connection(db)
        row = conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()
        result["chunks_indexed"] = row[0] if row else 0
        conn.close()
    except Exception:
        pass
    return result
