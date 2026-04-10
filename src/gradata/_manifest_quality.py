"""
Brain Manifest Quality Scoring.
================================
Quality scoring functions for brain manifest generation.
Split from _brain_manifest.py for file size compliance (<500 lines).
"""

import math
import re
import statistics
from typing import TYPE_CHECKING

import gradata._paths as _p
from gradata._db import get_connection
from gradata._manifest_helpers import LOW_SEVERITY, _session_window
from gradata._stats import trend_analysis as _trend_analysis

if TYPE_CHECKING:
    from gradata._paths import BrainContext


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
        try:
            # Get the most recent N real sessions with outputs (exclude system sessions)
            # Uses HAVING COUNT >= 2 to skip phantom sessions with stray events
            sessions_with_outputs = conn.execute(
                """
                SELECT e.session FROM events e
                LEFT JOIN session_metrics sm ON e.session = sm.session
                WHERE e.type = 'OUTPUT'
                  AND typeof(e.session) = 'integer'
                  AND (sm.session_type IS NULL OR sm.session_type != 'systems')
                GROUP BY e.session HAVING COUNT(*) >= 2
                ORDER BY e.session DESC LIMIT ?
            """,
                (window,),
            ).fetchall()

            if len(sessions_with_outputs) < 3:
                return None

            # Single aggregate query replacing N+1 per-session queries
            session_ids = [s[0] for s in sessions_with_outputs]
            placeholders = ",".join("?" * len(session_ids))
            correction_stats = conn.execute(
                f"""
                SELECT session,
                       SUM(CASE WHEN json_extract(data_json, '$.severity') IS NOT NULL THEN 1 ELSE 0 END) as has_sev,
                       SUM(CASE WHEN json_extract(data_json, '$.severity') IN ('moderate', 'major', 'discarded') THEN 1 ELSE 0 END) as major,
                       COUNT(*) as total_corr
                FROM events
                WHERE type = 'CORRECTION' AND session IN ({placeholders})
                GROUP BY session
            """,
                session_ids,
            ).fetchall()

            # Build lookup: session -> (has_severity, major_count, total_count)
            corr_by_session = {row[0]: (row[1], row[2], row[3]) for row in correction_stats}

            accepted = 0
            for (session,) in sessions_with_outputs:
                has_sev, major, total_corr = corr_by_session.get(session, (0, 0, 0))
                if has_sev > 0:
                    # Severity data: only major/moderate/discarded count against acceptance
                    if major == 0:
                        accepted += 1
                else:
                    # No severity data: any correction counts against acceptance
                    if total_corr == 0:
                        accepted += 1

            total = len(sessions_with_outputs)
            return round(accepted / total, 3) if total > 0 else None
        finally:
            conn.close()
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
        try:
            _, min_session = _session_window(conn, window)

            all_cats = {
                r[0]
                for r in conn.execute("""
                SELECT DISTINCT json_extract(data_json, '$.category')
                FROM events WHERE type = 'CORRECTION'
                  AND json_extract(data_json, '$.category') IS NOT NULL
            """).fetchall()
            }

            recent_cats = {
                r[0]
                for r in conn.execute(
                    """
                SELECT DISTINCT json_extract(data_json, '$.category')
                FROM events WHERE type = 'CORRECTION' AND session >= ?
                  AND json_extract(data_json, '$.category') IS NOT NULL
            """,
                    (min_session,),
                ).fetchall()
            }

            tested_cats = {
                r[0]
                for r in conn.execute(
                    """
                SELECT DISTINCT json_extract(data_json, '$.category')
                FROM events WHERE type = 'OUTPUT' AND session >= ?
                  AND json_extract(data_json, '$.category') IS NOT NULL
            """,
                    (min_session,),
                ).fetchall()
            }

            extinct = sorted((all_cats - recent_cats) & tested_cats)
            return extinct
        finally:
            conn.close()
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
        try:
            # DB-side windowing: fetch last N sessions, then reverse in Python
            rows = conn.execute(
                """
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
            """,
                (limit,),
            ).fetchall()
            return [r[1] / r[2] for r in reversed(rows)]
        finally:
            conn.close()
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
        try:
            _, min_session = _session_window(conn, window)
            rows = conn.execute(
                """
                SELECT json_extract(data_json, '$.severity') as sev, COUNT(*) as cnt
                FROM events WHERE type = 'CORRECTION' AND session >= ?
                GROUP BY sev
            """,
                (min_session,),
            ).fetchall()
            total = sum(r[1] for r in rows)
            if total < 5:
                return None
            low = sum(r[1] for r in rows if r[0] in LOW_SEVERITY)
            return low / total
        finally:
            conn.close()
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
        rule_cats = set(
            re.findall(
                r"^\[20\d{2}-\d{2}-\d{2}\]\s+\[RULE:.*?category:\s*(\w+)", text, re.MULTILINE
            )
        )
        if not rule_cats:
            return None

        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        try:
            _, min_session = _session_window(conn, window)

            # Count corrections vs outputs in RULE categories in recent sessions
            cats_list = list(rule_cats)
            ph = ",".join("?" * len(cats_list))
            corrections = (
                conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session >= ? "
                    f"AND json_extract(data_json, '$.category') IN ({ph})",
                    [min_session, *cats_list],
                ).fetchone()[0]
                or 0
            )
            outputs = (
                conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session >= ? "
                    f"AND json_extract(data_json, '$.category') IN ({ph})",
                    [min_session, *cats_list],
                ).fetchone()[0]
                or 0
            )

            if outputs < 3:
                return None
            # Invert: low correction rate = high transfer score
            return max(0.0, 1.0 - (corrections / outputs))
        finally:
            conn.close()
    except Exception:
        return None


def _score_confidence(score: float, sessions: int) -> dict:
    """Heuristic confidence interval that narrows with more data.

    Margin = 30 / sqrt(sessions). At 5 sessions: +/-13.4. At 50: +/-4.2.
    """
    if sessions < 3:
        return {
            "score": round(score, 1),
            "ci_low": 0.0,
            "ci_high": 100.0,
            "confidence": "insufficient_data",
        }
    margin = 30.0 / math.sqrt(max(1, sessions))
    return {
        "score": round(score, 1),
        "ci_low": round(max(0.0, score - margin), 1),
        "ci_high": round(min(100.0, score + margin), 1),
        "confidence": "high" if sessions >= 50 else "medium" if sessions >= 20 else "low",
    }


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
            correction_rate=max(0.05, min(1.0, _rng.gauss(0.4, 0.15))),
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
            "strong"
            if percentile >= 80
            else "above_average"
            if percentile >= 60
            else "average"
            if percentile >= 40
            else "below_average"
        ),
    }


def _severity_difficulty_weight(ctx: "BrainContext | None" = None) -> float | None:
    """IRT-inspired difficulty weighting for corrections.

    Corrections on hard tasks (major severity) should count more toward
    the brain quality score than corrections on easy tasks (minor).
    This computes a weighted correction rate where harder corrections
    get higher weight -- analogous to Item Response Theory difficulty
    parameters in psychometrics.

    Returns a difficulty-weighted score (0.0-1.0) or None if insufficient data.
    """
    try:
        db = ctx.db_path if ctx else _p.DB_PATH
        conn = get_connection(db)
        try:
            _, min_session = _session_window(conn, 20)

            rows = conn.execute(
                """
                SELECT json_extract(data_json, '$.severity') as sev,
                       json_extract(data_json, '$.fire_count') as fires
                FROM events WHERE type = 'CORRECTION' AND session >= ?
            """,
                (min_session,),
            ).fetchall()
        finally:
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
            try:
                if fire_count and int(fire_count) > 0:
                    survived_weight += w
            except (ValueError, TypeError):
                pass

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
    cross_domain_rules: int = 0,
    total_rules: int = 0,
    severity_trend_improving: bool = False,
) -> float:
    """Compute weighted brain health score (0-100).

    v3 formula informed by MiroFish expert panel (S101 sims 101-103):
    - Replaced FDA (permanently 0 for most LLMs) with severity improvement
    - Added cross-domain universality (rules that apply across 3+ domains)
    - Added severity trend (reducing severity = deeper learning)
    - Reduced active lessons weight (quantity != quality)

    Components:
      1. Correction improvement: 0-20 pts
      2. Severity improvement:   0-20 pts (was 25, rebalanced)
      3. Graduation rate:        0-15 pts
      4. Active lessons:         0-5 pts  (was 8, reduced per MiroFish)
      5. Maturity/sessions:      0-3 pts
      6. Density slope:          0-15 pts (Theil-Sen + Mann-Kendall)
      7. Category extinction:    0-9 pts  (task-frequency verified)
      8. Transfer score:         0-5 pts
      9. Cross-domain rules:     0-5 pts  (NEW: universal pattern discovery)
     10. Severity trend:         0-3 pts  (NEW: corrections getting less severe)
    """
    score = 0.0
    max_achievable = 100.0

    # Component 1: Correction improvement (0-20 pts)
    if correction_rate is not None and total_corrections >= 5:
        score += max(0.0, 1.0 - correction_rate) * 20
    elif correction_rate is None or total_corrections < 5:
        # Insufficient data: exclude from achievable maximum so the
        # score isn't deflated by a zero-contribution component.
        max_achievable -= 20

    # Component 2: Severity improvement (0-20 pts, was 25 — rebalanced for new components)
    if severity_ratio is not None:
        score += severity_ratio * 20
    else:
        max_achievable -= 20

    # Component 3: Graduation rate (0-15 pts)
    total_lessons = lessons_graduated + lessons_active
    if total_lessons > 0:
        grad_rate = lessons_graduated / total_lessons
        # Scale down bonus for very small sample sizes to avoid inflation
        # from e.g. 1 graduated out of 1 total = 100% rate.
        sample_factor = min(1.0, total_lessons / 10)
        score += grad_rate * sample_factor * 15

    # Component 4: Active lessons (0-5 pts, was 8 — MiroFish: quantity != quality)
    score += min(1.0, lessons_active / 10) * 5

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
            cv = (
                (statistics.stdev(second_data) / max(0.01, second_half))
                if len(second_data) >= 2
                else 0
            )
            volatility_penalty = max(0.3, 1.0 - max(0.0, cv - 0.35))
            reduction = max(0.0, min(1.0, (first_half - second_half) / first_half))
            slope_pts = reduction * 15 * volatility_penalty

    # Anti-gaming: discount front-loaded corrections (>60% in first 20%)
    # Only applies when there are enough total corrections to be meaningful.
    # A brain with very few sparse corrections can legitimately have them
    # concentrated early without it being gaming behavior.
    if correction_density_trend and len(correction_density_trend) >= 6:
        early_n = max(1, len(correction_density_trend) // 5)
        total_density = sum(correction_density_trend)
        if total_density > 1.0:  # need meaningful volume, not just 1 stray correction
            early_share = sum(correction_density_trend[:early_n]) / total_density
            if early_share > 0.60:
                slope_pts *= 0.3

    # Low-absolute-error bonus: don't penalize already-good brains.
    # Only award if the brain actually started higher and improved (or was
    # always near zero from the start).  Prevents gaming by a brain that
    # never had corrections and therefore never learned anything.
    if correction_density_trend and len(correction_density_trend) >= 5:
        recent_mean = statistics.mean(correction_density_trend[-5:])
        early_mean = statistics.mean(correction_density_trend[:5])
        if recent_mean < 0.10:
            # Genuine improvement if started high, modest bonus if always low
            slope_pts = max(slope_pts, 10.0) if early_mean >= 0.1 else max(slope_pts, 5.0)

    score += slope_pts

    # Component 7: Category extinction (0-9 pts, verified against task frequency)
    if categories_extinct > 0:
        score += min(1.0, categories_extinct / 3) * 9

    # Component 8: Transfer score (0-5 pts, NEW)
    if transfer is not None:
        score += max(0.0, min(1.0, transfer)) * 5
    else:
        max_achievable -= 5

    # Component 9: Cross-domain universality (0-5 pts, NEW)
    # Rewards brains that discover rules applicable across 3+ domains.
    if total_rules > 0 and cross_domain_rules > 0:
        universality = min(1.0, cross_domain_rules / max(3, total_rules * 0.2))
        score += universality * 5

    # Component 10: Severity trend (0-3 pts, NEW)
    # Corrections getting less severe over time = deeper learning.
    if severity_trend_improving:
        score += 3.0

    # Normalize to achievable range when optional components are inactive.
    # Floor of 20 prevents extreme inflation when most components are missing.
    if max_achievable < 100.0 and max_achievable > 20.0:
        score = (score / max_achievable) * 100.0

    final = round(min(100.0, score), 1)
    return 0.0 if math.isnan(final) else final
