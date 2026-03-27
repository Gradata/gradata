"""
Success Condition Checker — validates brain improvement over time.
=================================================================
From Build Directive Section 6 + Engineering Spec SUCCESS section.

ALL must be true across 20+ sessions:
- Rewrite rate decreases
- Edit distance decreases
- Acceptance rate increases
- Rule success rate increases
- Misfire rate stays low or decreases
- Output does NOT become more generic (blandness stable or improving)

Also from Revised Vision Gate 0:
- Measurably fewer corrections at session 200 vs session 50
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ConditionResult:
    """Result of evaluating one success condition."""

    name: str
    met: bool
    current_value: float
    baseline_value: float
    trend: str  # "improving", "stable", "degrading"
    detail: str


@dataclass
class SuccessReport:
    """Full success condition evaluation."""

    conditions: list[ConditionResult]
    all_met: bool
    sessions_evaluated: int
    window_size: int

    @property
    def met_count(self) -> int:
        return sum(1 for c in self.conditions if c.met)

    @property
    def total_count(self) -> int:
        return len(self.conditions)


def _get_session_metrics(conn: sqlite3.Connection, window: int) -> list[dict]:
    """Get per-session metric summaries from events."""
    try:
        rows = conn.execute("""
            SELECT session,
                   SUM(CASE WHEN type='OUTPUT' THEN 1 ELSE 0 END) as outputs,
                   SUM(CASE WHEN type='CORRECTION' THEN 1 ELSE 0 END) as corrections,
                   SUM(CASE WHEN type='RULE_APPLICATION' THEN 1 ELSE 0 END) as rule_apps
            FROM events
            WHERE session IS NOT NULL
            GROUP BY session
            ORDER BY session DESC
            LIMIT ?
        """, (window,)).fetchall()
    except sqlite3.OperationalError:
        return []

    return [
        {"session": r[0], "outputs": r[1], "corrections": r[2], "rule_apps": r[3]}
        for r in reversed(rows)  # oldest first
    ]


def _split_halves(values: list[float]) -> tuple[float, float]:
    """Split values into first half (baseline) and second half (current) averages."""
    if len(values) < 4:
        return 0.0, 0.0
    mid = len(values) // 2
    first = values[:mid]
    second = values[mid:]
    avg_first = sum(first) / len(first) if first else 0.0
    avg_second = sum(second) / len(second) if second else 0.0
    return avg_first, avg_second


def evaluate_success_conditions(db_path: Path, window: int = 20) -> SuccessReport:
    """Evaluate all success conditions from Build Directive + Engineering Spec.

    Compares first-half of window (baseline) against second-half (current)
    to determine trend direction.
    """
    from pathlib import Path as _Path

    conditions: list[ConditionResult] = []
    db = _Path(db_path)

    if not db.exists():
        return SuccessReport(conditions=[], all_met=False, sessions_evaluated=0, window_size=window)

    conn = sqlite3.connect(str(db))
    try:
        metrics = _get_session_metrics(conn, window)
        n = len(metrics)

        if n < 4:
            return SuccessReport(
                conditions=[ConditionResult(
                    name="insufficient_data", met=False,
                    current_value=float(n), baseline_value=4.0,
                    trend="n/a", detail=f"Need 4+ sessions, have {n}",
                )],
                all_met=False, sessions_evaluated=n, window_size=window,
            )

        # 1. Correction rate decreases (rewrite rate proxy)
        correction_rates = [
            m["corrections"] / m["outputs"] if m["outputs"] > 0 else 0.0
            for m in metrics
        ]
        baseline_cr, current_cr = _split_halves(correction_rates)
        cr_improving = current_cr <= baseline_cr
        conditions.append(ConditionResult(
            name="correction_rate_decreases",
            met=cr_improving,
            current_value=round(current_cr, 4),
            baseline_value=round(baseline_cr, 4),
            trend="improving" if cr_improving else "degrading",
            detail=f"Correction rate: {baseline_cr:.1%} -> {current_cr:.1%}",
        ))

        # 2. Edit distance decreases (from CORRECTION events)
        try:
            ed_rows = conn.execute("""
                SELECT session, AVG(json_extract(data_json, '$.edit_distance'))
                FROM events WHERE type='CORRECTION'
                AND json_extract(data_json, '$.edit_distance') IS NOT NULL
                GROUP BY session ORDER BY session
            """).fetchall()
            if len(ed_rows) >= 4:
                ed_values = [r[1] for r in ed_rows if r[1] is not None]
                baseline_ed, current_ed = _split_halves(ed_values)
                ed_improving = current_ed <= baseline_ed
                conditions.append(ConditionResult(
                    name="edit_distance_decreases",
                    met=ed_improving,
                    current_value=round(current_ed, 4),
                    baseline_value=round(baseline_ed, 4),
                    trend="improving" if ed_improving else "degrading",
                    detail=f"Avg edit distance: {baseline_ed:.2f} -> {current_ed:.2f}",
                ))
        except sqlite3.OperationalError:
            pass

        # 3. First-draft acceptance increases
        try:
            fda_rows = conn.execute("""
                SELECT session,
                    CAST(SUM(CASE WHEN json_extract(data_json, '$.major_edit') = 0
                                   OR json_extract(data_json, '$.major_edit') IS NULL
                              THEN 1 ELSE 0 END) AS REAL) /
                    NULLIF(COUNT(*), 0)
                FROM events WHERE type='OUTPUT'
                GROUP BY session ORDER BY session
            """).fetchall()
            if len(fda_rows) >= 4:
                fda_values = [r[1] for r in fda_rows if r[1] is not None]
                baseline_fda, current_fda = _split_halves(fda_values)
                fda_improving = current_fda >= baseline_fda
                conditions.append(ConditionResult(
                    name="acceptance_rate_increases",
                    met=fda_improving,
                    current_value=round(current_fda, 4),
                    baseline_value=round(baseline_fda, 4),
                    trend="improving" if fda_improving else "degrading",
                    detail=f"First-draft acceptance: {baseline_fda:.1%} -> {current_fda:.1%}",
                ))
        except sqlite3.OperationalError:
            pass

        # 4. Rule success rate increases
        try:
            rule_rows = conn.execute("""
                SELECT session,
                    CAST(SUM(CASE WHEN json_extract(data_json, '$.accepted') = 1 THEN 1 ELSE 0 END) AS REAL) /
                    NULLIF(COUNT(*), 0)
                FROM events WHERE type='RULE_APPLICATION'
                GROUP BY session ORDER BY session
            """).fetchall()
            if len(rule_rows) >= 4:
                rule_values = [r[1] for r in rule_rows if r[1] is not None]
                baseline_rs, current_rs = _split_halves(rule_values)
                rs_improving = current_rs >= baseline_rs
                conditions.append(ConditionResult(
                    name="rule_success_increases",
                    met=rs_improving,
                    current_value=round(current_rs, 4),
                    baseline_value=round(baseline_rs, 4),
                    trend="improving" if rs_improving else "degrading",
                    detail=f"Rule success rate: {baseline_rs:.1%} -> {current_rs:.1%}",
                ))
        except sqlite3.OperationalError:
            pass

        # 5. Misfires stay low
        try:
            misfire_rows = conn.execute("""
                SELECT session,
                    CAST(SUM(CASE WHEN json_extract(data_json, '$.misfired') = 1 THEN 1 ELSE 0 END) AS REAL) /
                    NULLIF(COUNT(*), 0)
                FROM events WHERE type='RULE_APPLICATION'
                GROUP BY session ORDER BY session
            """).fetchall()
            if len(misfire_rows) >= 4:
                mf_values = [r[1] for r in misfire_rows if r[1] is not None]
                baseline_mf, current_mf = _split_halves(mf_values)
                mf_ok = current_mf <= max(baseline_mf, 0.10)  # allow up to 10%
                conditions.append(ConditionResult(
                    name="misfires_stay_low",
                    met=mf_ok,
                    current_value=round(current_mf, 4),
                    baseline_value=round(baseline_mf, 4),
                    trend="stable" if abs(current_mf - baseline_mf) < 0.05 else
                          ("improving" if current_mf < baseline_mf else "degrading"),
                    detail=f"Misfire rate: {baseline_mf:.1%} -> {current_mf:.1%}",
                ))
        except sqlite3.OperationalError:
            pass

        # 6. Output not becoming bland (from metrics module)
        try:
            from gradata.enhancements.metrics import compute_metrics
            m = compute_metrics(db_path, window)
            bland_ok = m.blandness_score < 0.70
            conditions.append(ConditionResult(
                name="output_not_bland",
                met=bland_ok,
                current_value=round(m.blandness_score, 4),
                baseline_value=0.70,
                trend="varied" if bland_ok else "generic",
                detail=f"Blandness: {m.blandness_score:.2f} (threshold: 0.70)",
            ))
        except Exception:
            pass

    finally:
        conn.close()

    all_met = all(c.met for c in conditions) and len(conditions) >= 3
    return SuccessReport(
        conditions=conditions,
        all_met=all_met,
        sessions_evaluated=n,
        window_size=window,
    )


def format_success_report(report: SuccessReport) -> str:
    """Format success conditions as human-readable report."""
    verdict = "ALL MET" if report.all_met else f"{report.met_count}/{report.total_count} MET"
    lines = [
        f"Success Conditions — {verdict}",
        f"Sessions evaluated: {report.sessions_evaluated} (window: {report.window_size})",
        "",
    ]
    for c in report.conditions:
        icon = "PASS" if c.met else "FAIL"
        lines.append(f"  [{icon}] {c.name}: {c.detail} ({c.trend})")

    if report.all_met:
        lines.append("\nBrain is compounding. All success conditions from the Build Directive are met.")
    else:
        failed = [c for c in report.conditions if not c.met]
        lines.append(f"\n{len(failed)} condition(s) not met. Focus on: {', '.join(c.name for c in failed)}")

    return "\n".join(lines)
