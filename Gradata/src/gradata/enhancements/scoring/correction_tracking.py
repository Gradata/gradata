"""
Correction Tracking — detailed analytics for brain improvement measurement.
===========================================================================
Queries CORRECTION events from the brain's events table and produces a
CorrectionProfile that quantifies whether the brain is learning from its
mistakes.  All computations are domain-agnostic: no domain-specific constants,
no references to external tools or CRM systems.

Stdlib only: sqlite3, dataclasses, math.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from gradata._correction_metrics import correction_rate as _correction_rate

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CorrectionProfile:
    """Comprehensive analytics for CORRECTION events emitted by a brain.

    Attributes:
        total_corrections: Absolute count of CORRECTION events in the window.
        total_outputs: Absolute count of OUTPUT events in the same window.
        correction_rate: Corrections divided by outputs (0.0 when outputs == 0).
        density_per_session: Per-session correction density values
            (corrections / outputs for each session that had at least one event).
        density_trend: One of "improving", "stable", or "degrading" based on
            a split-half comparison of density_per_session.
        density_pct_change: Percentage change from the first half (baseline)
            to the second half (recent) of density_per_session.  Negative
            means fewer corrections per output (improving).
        half_life_sessions: Estimated sessions until the correction rate would
            halve, assuming exponential decay.  ``math.inf`` when the trend is
            flat or worsening.
        mtbf: Mean sessions between individual correction events across the
            full session range.
        mttr: Mean length (in sessions) of consecutive correction streaks
            (sessions where at least one correction occurred).
        category_breakdown: Mapping of correction category label to count.
            Uses the ``category`` key from the event's data_json, falling back
            to ``"UNKNOWN"``.
    """

    total_corrections: int
    total_outputs: int
    correction_rate: float
    density_per_session: list[float]
    density_trend: str
    density_pct_change: float
    half_life_sessions: float
    mtbf: float
    mttr: float
    category_breakdown: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open a brain database in read-only WAL mode.

    Args:
        db_path: Absolute path to ``system.db``.

    Returns:
        An open sqlite3 connection with ``row_factory`` set to
        ``sqlite3.Row``.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


# Shared SQL used by both correction_tracking and brain_scores fallback.
_SQL_CORRECTION_OUTPUT_TOTALS = """
    SELECT
        SUM(CASE WHEN type = 'CORRECTION' THEN 1 ELSE 0 END),
        SUM(CASE WHEN type = 'OUTPUT'     THEN 1 ELSE 0 END)
    FROM events
    WHERE session >= ?
    """


def _session_densities(
    conn: sqlite3.Connection,
    min_session: int,
) -> dict[int, float]:
    """Compute per-session correction density for sessions >= min_session.

    Density for a session = corrections / outputs.  Sessions with zero
    outputs are assigned density 0.0 when they have corrections (worst
    case assumed) or excluded entirely when they have neither.

    Args:
        conn: Open database connection.
        min_session: Lower bound for session numbers (inclusive).

    Returns:
        Dict mapping session number to density value, ordered by session.
    """
    rows = conn.execute(
        """
        SELECT
            session,
            SUM(CASE WHEN type = 'CORRECTION' THEN 1 ELSE 0 END) AS corrections,
            SUM(CASE WHEN type = 'OUTPUT'     THEN 1 ELSE 0 END) AS outputs
        FROM events
        WHERE session >= ?
          AND type IN ('CORRECTION', 'OUTPUT')
        GROUP BY session
        ORDER BY session
        """,
        (min_session,),
    ).fetchall()

    densities: dict[int, float] = {}
    for r in rows:
        session = r["session"]
        corrections = r["corrections"] or 0
        outputs = r["outputs"] or 0
        if outputs > 0:
            densities[session] = corrections / outputs
        elif corrections > 0:
            # Corrections without outputs: density treated as 1.0 (all bad)
            densities[session] = 1.0
        # Sessions with neither event type are omitted
    return densities


def _split_half_trend(values: list[float]) -> tuple[str, float]:
    """Detect trend direction by comparing the first and second halves.

    Args:
        values: Ordered list of numeric values (oldest → newest).

    Returns:
        Tuple of (trend_label, pct_change) where trend_label is one of
        ``"improving"``, ``"stable"``, or ``"degrading"``, and pct_change
        is the percentage change from the first-half average to the
        second-half average.  For correction density, *lower is better*,
        so a negative pct_change is labelled "improving".
    """
    if len(values) < 4:
        return "stable", 0.0

    mid = len(values) // 2
    first_half = values[:mid]
    second_half = values[mid:]

    baseline = sum(first_half) / len(first_half)
    recent = sum(second_half) / len(second_half)

    if baseline == 0.0:
        pct_change = 0.0 if recent == 0.0 else 100.0
    else:
        pct_change = ((recent - baseline) / baseline) * 100.0

    if abs(pct_change) < 5.0:
        trend = "stable"
    elif pct_change < 0.0:
        # Density fell — fewer corrections per output — brain is improving
        trend = "improving"
    else:
        trend = "degrading"

    return trend, round(pct_change, 2)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def compute_half_life(densities: list[float]) -> float:
    """Estimate sessions until the correction rate halves using exponential decay.

    Fits ``d(t) = d0 * exp(-lambda * t)`` to the density series, then
    solves for ``t`` such that ``d(t) == d0 / 2`` giving
    ``half_life = ln(2) / lambda``.

    The fit uses ordinary least-squares on the log-transformed series.
    Sessions with density 0.0 are skipped (log undefined), so the fit
    requires at least two non-zero observations.

    Args:
        densities: Ordered list of per-session correction densities.

    Returns:
        Estimated half-life in sessions.  Returns ``math.inf`` when the
        trend is flat or worsening, or when fewer than two non-zero
        observations are present.
    """
    if len(densities) < 2:
        return math.inf

    # Build (t, ln(d)) pairs, skipping zero densities
    log_pairs: list[tuple[float, float]] = [
        (float(i), math.log(d)) for i, d in enumerate(densities) if d > 0.0
    ]

    if len(log_pairs) < 2:
        return math.inf

    n = float(len(log_pairs))
    sum_t = sum(p[0] for p in log_pairs)
    sum_y = sum(p[1] for p in log_pairs)
    sum_tt = sum(p[0] ** 2 for p in log_pairs)
    sum_ty = sum(p[0] * p[1] for p in log_pairs)

    denom = n * sum_tt - sum_t**2
    if denom == 0.0:
        return math.inf

    # OLS slope is -lambda (decay constant)
    slope = (n * sum_ty - sum_t * sum_y) / denom

    if slope >= 0.0:
        # No decay — rate is flat or increasing
        return math.inf

    lambda_decay = -slope
    return math.log(2.0) / lambda_decay


def compute_mtbf_mttr(
    correction_sessions: list[int],
    total_sessions: int,
) -> tuple[float, float]:
    """Compute mean-time-between-failures and mean-time-to-repair.

    Definitions used here:
    - **MTBF**: average gap (in sessions) between consecutive sessions that
      contain at least one correction.  Calculated as
      ``total_sessions / number_of_correction_sessions`` when there is only
      one correction session, or as the mean inter-event gap when there are
      multiple.
    - **MTTR**: mean length of consecutive correction streaks.  A streak is
      a maximal run of sessions where at least one correction occurred.  A
      single isolated correction session has streak length 1.

    Args:
        correction_sessions: Sorted list of session numbers that contain at
            least one CORRECTION event.  Duplicates are ignored.
        total_sessions: Total number of sessions in the analysis window.

    Returns:
        ``(mtbf, mttr)`` as floats.  Returns ``(float(total_sessions), 1.0)``
        when there are no correction sessions.
    """
    if not correction_sessions or total_sessions <= 0:
        return float(total_sessions), 1.0

    # Deduplicate and sort
    unique_sessions = sorted(set(correction_sessions))
    n = len(unique_sessions)

    # MTBF
    if n == 1:
        mtbf = float(total_sessions)
    else:
        gaps = [unique_sessions[i + 1] - unique_sessions[i] for i in range(n - 1)]
        mtbf = sum(gaps) / len(gaps)

    # MTTR: identify maximal consecutive streaks
    streaks: list[int] = []
    streak_len = 1
    for i in range(1, n):
        if unique_sessions[i] == unique_sessions[i - 1] + 1:
            streak_len += 1
        else:
            streaks.append(streak_len)
            streak_len = 1
    streaks.append(streak_len)

    mttr = sum(streaks) / len(streaks)

    return round(mtbf, 2), round(mttr, 2)


def compute_correction_profile(
    db_path: Path,
    window: int = 20,
) -> CorrectionProfile:
    """Build a full CorrectionProfile from CORRECTION events in the database.

    Queries the events table for the most recent ``window`` sessions, then
    computes all CorrectionProfile fields.

    Args:
        db_path: Path to the brain's ``system.db`` SQLite database.
        window: Number of sessions to include in the analysis (most recent).

    Returns:
        A populated CorrectionProfile.  All fields default to safe values
        (0, empty lists, "stable") when the database contains no events.
    """
    conn = _open_db(db_path)

    try:
        # --- Determine the session window ---
        max_row = conn.execute(
            "SELECT COALESCE(MAX(CAST(session AS INTEGER)), 0) FROM events"
        ).fetchone()
        max_session: int = int(max_row[0]) if max_row and max_row[0] else 0
        min_session = max(0, max_session - (window - 1))

        # --- Total corrections and outputs in window ---
        totals = conn.execute(_SQL_CORRECTION_OUTPUT_TOTALS, (min_session,)).fetchone()
        total_corrections: int = int(totals[0] or 0)
        total_outputs: int = int(totals[1] or 0)

        # --- Per-session densities ---
        session_density_map = _session_densities(conn, min_session)
        density_per_session = [session_density_map[s] for s in sorted(session_density_map)]

        # --- Trend ---
        density_trend, density_pct_change = _split_half_trend(density_per_session)

        # --- Half-life ---
        half_life_sessions = compute_half_life(density_per_session)

        # --- MTBF / MTTR ---
        correction_session_rows = conn.execute(
            """
            SELECT DISTINCT session FROM events
            WHERE type = 'CORRECTION' AND session >= ?
            ORDER BY session
            """,
            (min_session,),
        ).fetchall()
        correction_session_list = [r[0] for r in correction_session_rows]
        total_sessions_in_window = max(1, max_session - min_session + 1)
        mtbf, mttr = compute_mtbf_mttr(correction_session_list, total_sessions_in_window)

        # --- Category breakdown ---
        import json

        category_rows = conn.execute(
            """
            SELECT data_json FROM events
            WHERE type = 'CORRECTION' AND session >= ?
            """,
            (min_session,),
        ).fetchall()
        category_breakdown: dict[str, int] = {}
        for row in category_rows:
            try:
                data = json.loads(row[0]) if row[0] else {}
            except (ValueError, TypeError):
                data = {}
            cat = str(data.get("category", "UNKNOWN"))
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

    finally:
        conn.close()

    return CorrectionProfile(
        total_corrections=total_corrections,
        total_outputs=total_outputs,
        correction_rate=_correction_rate(total_corrections, total_outputs, ndigits=4),
        density_per_session=density_per_session,
        density_trend=density_trend,
        density_pct_change=density_pct_change,
        half_life_sessions=half_life_sessions,
        mtbf=mtbf,
        mttr=mttr,
        category_breakdown=category_breakdown,
    )


def format_correction_profile(profile: CorrectionProfile) -> str:
    """Render a CorrectionProfile as a human-readable report string.

    Args:
        profile: A CorrectionProfile returned by compute_correction_profile.

    Returns:
        Multi-line string suitable for logging or terminal display.
    """
    lines: list[str] = [
        "Correction Profile",
        "==================",
        f"Total corrections : {profile.total_corrections}",
        f"Total outputs     : {profile.total_outputs}",
        f"Correction rate   : {profile.correction_rate:.1%}",
        "",
        f"Density trend     : {profile.density_trend.upper()}",
        f"Density pct change: {profile.density_pct_change:+.1f}%",
    ]

    if profile.half_life_sessions == math.inf:
        lines.append("Half-life         : N/A (no decay detected)")
    else:
        lines.append(f"Half-life         : {profile.half_life_sessions:.1f} sessions")

    lines += [
        f"MTBF              : {profile.mtbf:.1f} sessions",
        f"MTTR              : {profile.mttr:.1f} sessions",
    ]

    if profile.density_per_session:
        recent = profile.density_per_session[-5:]
        formatted = ", ".join(f"{v:.2f}" for v in recent)
        lines.append(f"Recent densities  : [{formatted}]")

    if profile.category_breakdown:
        lines.append("")
        lines.append("Categories:")
        for cat, count in sorted(
            profile.category_breakdown.items(),
            key=lambda kv: kv[1],
            reverse=True,
        ):
            lines.append(f"  {cat:<20} {count}")

    return "\n".join(lines)


def compute_density(db_path: Path | None = None, window: int = 20) -> float:
    """Compute current correction density (corrections per session in recent window).

    Convenience shortcut for ``compute_correction_profile(...).correction_rate``.
    """
    if db_path is None:
        from gradata._paths import resolve_brain_dir

        db_path = resolve_brain_dir() / "system.db"
    profile = compute_correction_profile(db_path=db_path, window=window)
    return profile.correction_rate
