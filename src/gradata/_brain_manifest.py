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
import math
import re
import statistics
from datetime import UTC, datetime

# Use module reference so set_brain_dir() updates propagate at call time
import gradata._paths as _p
from gradata._db import get_connection
from gradata._paths import BrainContext
from gradata._stats import trend_analysis as _trend_analysis

# ── Severity constants (single source of truth) ───────────────────────
LOW_SEVERITY = frozenset({"as-is", "minor"})
HIGH_SEVERITY = frozenset({"moderate", "major", "discarded"})
ALL_SEVERITY = LOW_SEVERITY | HIGH_SEVERITY


def _session_window(conn, window: int = 20) -> tuple[int, int]:
    """Return (max_session, min_session) for a recent window. Shared helper."""
    max_session = conn.execute(
        "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
    ).fetchone()[0] or 0
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
        pass
    return result


def _get_tables(ctx: "BrainContext | None" = None) -> list[str]:
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
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
        conn = get_connection(db)

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
                      AND json_extract(data_json, '$.severity') IN ('moderate', 'major', 'discarded')  -- HIGH_SEVERITY
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
    """Find correction categories with zero corrections in recent window.

    Only counts a category as extinct if it was TESTED (appeared in OUTPUT
    events recently) but had zero corrections. Prevents false positives
    from task distribution shift.
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        _, min_session = _session_window(conn, window)

        all_cats = {r[0] for r in conn.execute("""
            SELECT DISTINCT json_extract(data_json, '$.category')
            FROM events WHERE type = 'CORRECTION'
              AND json_extract(data_json, '$.category') IS NOT NULL
        """).fetchall()}

        recent_cats = {r[0] for r in conn.execute("""
            SELECT DISTINCT json_extract(data_json, '$.category')
            FROM events WHERE type = 'CORRECTION' AND session >= ?
              AND json_extract(data_json, '$.category') IS NOT NULL
        """, (min_session,)).fetchall()}

        tested_cats = {r[0] for r in conn.execute("""
            SELECT DISTINCT json_extract(data_json, '$.category')
            FROM events WHERE type = 'OUTPUT' AND session >= ?
              AND json_extract(data_json, '$.category') IS NOT NULL
        """, (min_session,)).fetchall()}

        conn.close()
        extinct = sorted((all_cats - recent_cats) & tested_cats)
        return extinct
    except Exception:
        return []


def _per_session_density(ctx: "BrainContext | None" = None, limit: int = 100) -> list[float]:
    """Correction density per session (corrections/outputs), ordered by session.

    Returns a real time-series suitable for Theil-Sen + Mann-Kendall trend
    detection. Excludes system sessions for consistency with FDA filtering.
    Windowed to last `limit` sessions so the DB query stays O(limit).
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        # DB-side windowing: fetch last N sessions, then reverse in Python
        rows = conn.execute("""
            SELECT e.session,
                   SUM(CASE WHEN e.type='CORRECTION' THEN 1 ELSE 0 END) as corr,
                   SUM(CASE WHEN e.type='OUTPUT' THEN 1 ELSE 0 END) as out_cnt
            FROM events e
            LEFT JOIN session_metrics sm ON e.session = sm.session
            WHERE typeof(e.session)='integer'
              AND (sm.session_type IS NULL OR sm.session_type != 'systems')
            GROUP BY e.session
            HAVING SUM(CASE WHEN e.type='OUTPUT' THEN 1 ELSE 0 END) >= 1
            ORDER BY e.session DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [r[1] / r[2] for r in reversed(rows)]
    except Exception:
        return []


def _severity_ratio(ctx: "BrainContext | None" = None, window: int = 20) -> float | None:
    """Ratio of low-severity corrections to total in recent window.

    Replaces FDA (which is always 0% for DeepSeek). A brain making smaller
    mistakes over time = real quality improvement.
    Returns None if fewer than 5 corrections in window.
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        _, min_session = _session_window(conn, window)
        rows = conn.execute("""
            SELECT json_extract(data_json, '$.severity') as sev, COUNT(*) as cnt
            FROM events WHERE type = 'CORRECTION' AND session >= ?
            GROUP BY sev
        """, (min_session,)).fetchall()
        conn.close()
        total = sum(r[1] for r in rows)
        if total < 5:
            return None
        low = sum(r[1] for r in rows if r[0] in LOW_SEVERITY)
        return low / total
    except Exception:
        return None


def _transfer_score(ctx: "BrainContext | None" = None, window: int = 10) -> float | None:
    """Correction rate on categories with RULE-level lessons.

    Measures whether graduated rules actually generalize. Low correction
    rate on RULE categories = strong transfer. Returns None if no RULE
    lessons exist yet.
    """
    try:
        lessons_file = ctx.lessons_file if ctx else _p.LESSONS_FILE
        if not lessons_file.exists():
            return None
        text = lessons_file.read_text(encoding="utf-8")
        rule_cats = set(re.findall(
            r"^\[20\d{2}-\d{2}-\d{2}\]\s+\[RULE:.*?category:\s*(\w+)",
            text, re.MULTILINE
        ))
        if not rule_cats:
            return None

        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        _, min_session = _session_window(conn, window)

        # Count corrections vs outputs in RULE categories in recent sessions
        cats_list = list(rule_cats)
        ph = ",".join("?" * len(cats_list))
        corrections = conn.execute(
            f"SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session >= ? "
            f"AND json_extract(data_json, '$.category') IN ({ph})",
            [min_session, *cats_list],
        ).fetchone()[0] or 0
        outputs = conn.execute(
            f"SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session >= ? "
            f"AND json_extract(data_json, '$.category') IN ({ph})",
            [min_session, *cats_list],
        ).fetchone()[0] or 0
        conn.close()

        if outputs < 3:
            return None
        # Invert: low correction rate = high transfer score
        return max(0.0, 1.0 - (corrections / outputs))
    except Exception:
        return None


def _score_confidence(score: float, sessions: int) -> dict:
    """Heuristic confidence interval that narrows with more data.

    Margin = 30 / sqrt(sessions). At 5 sessions: ±13.4. At 50: ±4.2.
    """
    if sessions < 3:
        return {"score": round(score, 1), "ci_low": 0.0, "ci_high": 100.0, "confidence": "insufficient_data"}
    margin = 30.0 / math.sqrt(max(1, sessions))
    return {
        "score": round(score, 1),
        "ci_low": round(max(0.0, score - margin), 1),
        "ci_high": round(min(100.0, score + margin), 1),
        "confidence": "high" if sessions >= 50 else "medium" if sessions >= 20 else "low",
    }


def _temporal_provenance(ctx: "BrainContext | None" = None) -> dict:
    """Measure temporal authenticity of brain training via 3rd-party signals.

    Checks that the brain's correction/learning history correlates with
    real-world activity — external API calls, tool usage, deliverables
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

        # Query 2: source counts grouped — filter in Python, no second query
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
                    t0 = datetime.fromisoformat(str(session_starts[i - 1][0]).replace("Z", "+00:00"))
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
            0.25 * day_score + 0.20 * spread_score + 0.20 * external_score
            + 0.15 * ratio_score + 0.20 * gap_score, 3
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

        sessions = [r[0] for r in rows]
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
            r = sum((xi - mx) * (vi - my) for xi, vi in zip(x, values)) / ((n - 1) * sx * sy)

        return {
            "outcome_trend_slope": round(slope, 4),
            "outcome_trend_p": round(p_value, 4),
            "outcome_score_correlation": round(r, 3),
            "data_points": n,
            "improving": slope < 0 and p_value < 0.10,  # negative slope = fewer edits = better
        }
    except Exception:
        return None


def _counterfactual_percentile(
    score: float, sessions: int, ctx: "BrainContext | None" = None
) -> dict | None:
    """Compare brain score against a synthetic null distribution.

    Generates random correction trajectories matching the brain's session
    count to estimate what percentile the actual score falls in.
    A genuine learner should rank well above 50th percentile.

    Returns None if fewer than 10 sessions.
    """
    if sessions < 10:
        return None

    import random as _rng
    _rng.seed(sessions * 7919)  # deterministic for reproducibility

    null_scores = []
    for _ in range(200):
        # Random density trend: uniform noise around 0.5
        trend = [max(0.01, 0.5 + _rng.gauss(0, 0.15)) for _ in range(min(sessions, 50))]
        null_score = _compound_score(
            correction_rate=max(0.05, _rng.gauss(0.4, 0.15)),
            severity_ratio=max(0.0, min(1.0, _rng.gauss(0.5, 0.2))),
            lessons_graduated=max(0, int(_rng.gauss(sessions * 0.3, sessions * 0.1))),
            lessons_active=max(0, int(_rng.gauss(5, 2))),
            sessions=sessions,
            total_corrections=max(5, int(sessions * _rng.gauss(2, 0.5))),
            correction_density_trend=trend,
            categories_extinct=max(0, int(_rng.gauss(1, 1))),
            transfer=max(0.0, min(1.0, _rng.gauss(0.4, 0.2))),
        )
        null_scores.append(null_score)

    null_scores.sort()
    # Percentile: how many null brains score below the real brain
    below = sum(1 for ns in null_scores if ns < score)
    percentile = round(below / len(null_scores) * 100, 1)

    return {
        "percentile": percentile,
        "null_mean": round(statistics.mean(null_scores), 1),
        "null_median": round(statistics.median(null_scores), 1),
        "null_p95": round(null_scores[int(len(null_scores) * 0.95)], 1),
        "interpretation": (
            "strong" if percentile >= 80 else
            "above_average" if percentile >= 60 else
            "average" if percentile >= 40 else
            "below_average"
        ),
    }


def _severity_difficulty_weight(ctx: "BrainContext | None" = None) -> float | None:
    """IRT-inspired difficulty weighting for corrections.

    Corrections on hard tasks (major severity) should count more toward
    the brain quality score than corrections on easy tasks (minor).
    This computes a weighted correction rate where harder corrections
    get higher weight — analogous to Item Response Theory difficulty
    parameters in psychometrics.

    Returns a difficulty-weighted score (0.0-1.0) or None if insufficient data.
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        _, min_session = _session_window(conn, 20)

        rows = conn.execute("""
            SELECT json_extract(data_json, '$.severity') as sev,
                   json_extract(data_json, '$.fire_count') as fires
            FROM events WHERE type = 'CORRECTION' AND session >= ?
        """, (min_session,)).fetchall()
        conn.close()

        if len(rows) < 5:
            return None

        # Difficulty weights: harder corrections = more valuable when survived
        difficulty = {"as-is": 0.2, "minor": 0.4, "moderate": 0.7, "major": 1.0, "discarded": 1.0}
        total_weight = 0.0
        survived_weight = 0.0

        for r in rows:
            sev = r[0] or "minor"
            fire_count = r[1] or 0
            w = difficulty.get(sev, 0.5)
            total_weight += w
            # "Survived" = correction was processed and lesson was reused (fire_count > 0)
            if fire_count and int(fire_count) > 0:
                survived_weight += w

        if total_weight == 0:
            return None

        return round(survived_weight / total_weight, 3)
    except Exception:
        return None


def _compound_score(
    correction_rate: float | None,
    severity_ratio: float | None,
    lessons_graduated: int,
    lessons_active: int,
    sessions: int,
    total_corrections: int = 0,
    correction_density_trend: list[float] | None = None,
    categories_extinct: int = 0,
    transfer: float | None = None,
) -> float:
    """Compute weighted brain health score (0-100).

    Uses Theil-Sen + Mann-Kendall for robust slope detection, severity
    improvement ratio, task-verified category extinction, transfer score
    for generalization, and anti-gaming floor for front-loaded patterns.

    Components:
      1. Correction improvement: 0-20 pts
      2. Severity improvement:   0-25 pts
      3. Graduation rate:        0-15 pts
      4. Active lessons:         0-8 pts
      5. Maturity/sessions:      0-3 pts
      6. Density slope:          0-15 pts (Theil-Sen + Mann-Kendall)
      7. Category extinction:    0-9 pts  (task-frequency verified)
      8. Transfer score:         0-5 pts
    """
    score = 0.0
    max_achievable = 100.0

    # Component 1: Correction improvement (0-20 pts)
    if correction_rate is not None and total_corrections >= 5:
        score += max(0.0, 1.0 - correction_rate) * 20

    # Component 2: Severity improvement (0-25 pts)
    if severity_ratio is not None:
        score += severity_ratio * 25
    elif total_corrections < 5:
        max_achievable -= 25

    # Component 3: Graduation rate (0-15 pts)
    total_lessons = lessons_graduated + lessons_active
    if total_lessons > 0:
        score += min(1.0, lessons_graduated / max(20, total_lessons)) * 15

    # Component 4: Active lessons (0-8 pts)
    score += min(1.0, lessons_active / 10) * 8

    # Component 5: Maturity (0-3 pts)
    score += min(1.0, sessions / 200) * 3

    # Component 6: Correction density slope (0-15 pts)
    # Theil-Sen + Mann-Kendall for n>=10, half-split fallback for 4<=n<10
    slope_pts = 0.0
    if correction_density_trend and len(correction_density_trend) >= 10:
        slope, p_value = _trend_analysis(correction_density_trend)
        if p_value < 0.10 and slope < 0:
            first_val = statistics.mean(correction_density_trend[:3])
            if first_val > 0:
                reduction = min(1.0, abs(slope) / first_val)
                slope_pts = reduction * 15
    elif correction_density_trend and len(correction_density_trend) >= 4:
        mid = len(correction_density_trend) // 2
        first_half = statistics.mean(correction_density_trend[:mid])
        second_half = statistics.mean(correction_density_trend[mid:])
        if first_half > 0:
            second_data = correction_density_trend[mid:]
            cv = (statistics.stdev(second_data) / max(0.01, second_half)) if len(second_data) >= 2 else 0
            volatility_penalty = max(0.3, 1.0 - max(0.0, cv - 0.35))
            reduction = max(0.0, min(1.0, (first_half - second_half) / first_half))
            slope_pts = reduction * 15 * volatility_penalty

    # Anti-gaming: discount front-loaded corrections (>60% in first 20%)
    if correction_density_trend and len(correction_density_trend) >= 6:
        early_n = max(1, len(correction_density_trend) // 5)
        total_density = sum(correction_density_trend)
        if total_density > 0:
            early_share = sum(correction_density_trend[:early_n]) / total_density
            if early_share > 0.60:
                slope_pts *= 0.3

    # Low-absolute-error bonus: don't penalize already-good brains
    if correction_density_trend and len(correction_density_trend) >= 5:
        recent_mean = statistics.mean(correction_density_trend[-5:])
        if recent_mean < 0.10:
            slope_pts = max(slope_pts, 10.0)

    score += slope_pts

    # Component 7: Category extinction (0-9 pts, verified against task frequency)
    if categories_extinct > 0:
        score += min(1.0, categories_extinct / 3) * 9

    # Component 8: Transfer score (0-5 pts, NEW)
    if transfer is not None:
        score += transfer * 5
    else:
        max_achievable -= 5

    # Normalize to achievable range when optional components are inactive.
    # Floor of 20 prevents extreme inflation when most components are missing.
    if max_achievable < 100.0 and max_achievable > 20.0:
        score = (score / max_achievable) * 100.0

    return round(min(100.0, score), 1)


def _lesson_distribution(ctx: "BrainContext | None" = None) -> dict[str, int]:
    """Count lessons by state from lessons.md."""
    dist: dict[str, int] = {}
    lessons_file = ctx.lessons_file if ctx else _p.LESSONS_FILE
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

    # Lesson distribution
    result["lesson_distribution"] = _lesson_distribution(ctx=ctx)

    # Get sessions count for compound score
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

    result["score_confidence"] = _score_confidence(
        result["compound_score"], sessions_trained
    )
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
        conn = get_connection(db)
        row = conn.execute("SELECT COUNT(*) FROM brain_embeddings").fetchone()
        result["chunks_indexed"] = row[0] if row else 0
        conn.close()
    except Exception:
        pass
    return result


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
        ("carl_priority_tiers", "gradata.enhancements.carl", "ChristopherKahler/paul+gradata"),
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
        ("rule_evolution", "gradata.enhancements.rule_evolution", "jarvis-inspired+gradata"),
    ]

    all_modules = _paul_modules + _ruflo_modules + _deerflow_modules + _ecc_modules + _everos_modules + _core_modules

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

    required_keys = ["schema_version", "metadata", "quality", "database", "rag", "paths"]
    for k in required_keys:
        if k not in manifest:
            issues.append(f"Missing required key: {k}")

    if manifest.get("schema_version") != "1.0.0":
        issues.append(f"Unknown schema version: {manifest.get('schema_version')}")

    return issues
