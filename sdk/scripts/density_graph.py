#!/usr/bin/env python3
"""
density_graph.py — Correction density analysis for Gradata.

Reads from system.db, computes correction density per session,
outputs CSV and ASCII chart. Zero external dependencies (pure stdlib).

Usage:
    python density_graph.py [--db PATH] [--csv PATH] [--full-only]

Arguments:
    --db PATH       Path to system.db (default: C:/Users/olive/SpritesWork/brain/system.db)
    --csv PATH      Path to write CSV output (default: density_report.csv)
    --full-only     Only include full/sales sessions, exclude systems sessions
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any


DEFAULT_DB = "C:/Users/olive/SpritesWork/brain/system.db"
DEFAULT_CSV = "density_report.csv"


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

def load_corrections_from_db(conn: sqlite3.Connection) -> dict[int, int]:
    """Return {session: correction_count} from events table."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session, COUNT(*) AS cnt
        FROM events
        WHERE type = 'CORRECTION'
          AND typeof(session) = 'integer'
        GROUP BY session
        """
    )
    return {int(r[0]): int(r[1]) for r in cur.fetchall()}


def load_session_metrics(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    """Return session_metrics rows keyed by session number."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session, session_type, corrections, correction_density,
               outputs_produced, first_draft_acceptance
        FROM session_metrics
        ORDER BY session
        """
    )
    result: dict[int, dict[str, Any]] = {}
    for row in cur.fetchall():
        s = row[0]
        if s is None:
            continue
        result[int(s)] = {
            "session_type": row[1],
            "corrections_sm": row[2],
            "correction_density_sm": row[3],
            "outputs": row[4],
            "first_draft_acceptance": row[5],
        }
    return result


def load_audit_scores(conn: sqlite3.Connection) -> dict[int, float]:
    """Return {session: combined_avg_score} from AUDIT_SCORE events."""
    cur = conn.cursor()
    cur.execute(
        "SELECT session, data_json FROM events WHERE type = 'AUDIT_SCORE' ORDER BY session"
    )
    scores: dict[int, float] = {}
    for row in cur.fetchall():
        if row[0] is None or not isinstance(row[0], int):
            continue
        try:
            data = json.loads(row[1]) if row[1] else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        score = data.get("combined_avg") or data.get("self_score")
        if score is not None:
            scores[int(row[0])] = float(score)
    return scores


def build_session_records(
    corrections: dict[int, int],
    metrics: dict[int, dict[str, Any]],
    scores: dict[int, float],
) -> list[dict[str, Any]]:
    """Merge all sources into one record per session (sessions 1-50)."""
    all_sessions = sorted(
        {s for s in set(corrections) | set(metrics) | set(scores) if 1 <= s <= 50}
    )
    records: list[dict[str, Any]] = []
    for s in all_sessions:
        m = metrics.get(s, {})
        record: dict[str, Any] = {
            "session": s,
            "session_type": m.get("session_type", "unknown"),
            # events table is authoritative for corrections
            "corrections": corrections.get(s, 0),
            "outputs": m.get("outputs", 0) or 0,
            "first_draft_acceptance": m.get("first_draft_acceptance"),
            "audit_score": scores.get(s),
        }
        # Compute corrections per output (only meaningful when outputs > 0)
        outputs = record["outputs"]
        corr = record["corrections"]
        record["corrections_per_output"] = (
            round(corr / outputs, 4) if outputs > 0 else None
        )
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def rolling_average(values: list[float], window: int = 5) -> list[float]:
    """Compute trailing rolling average with given window size."""
    result = []
    for i in range(len(values)):
        window_slice = values[max(0, i - window + 1) : i + 1]
        result.append(sum(window_slice) / len(window_slice))
    return result


def linear_regression(
    xs: list[float], ys: list[float]
) -> tuple[float, float, float]:
    """Return (slope, intercept, r_squared) via OLS."""
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    ss_xy = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    ss_xx = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if ss_xx == 0:
        return 0.0, y_mean, 0.0
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    ss_res = sum((ys[i] - (slope * xs[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((ys[i] - y_mean) ** 2 for i in range(n))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return round(slope, 6), round(intercept, 4), round(r_squared, 4)


def period_stats(
    records: list[dict[str, Any]], lo: int, hi: int
) -> dict[str, float]:
    """Return descriptive stats for sessions in [lo, hi] inclusive."""
    subset = [r for r in records if lo <= r["session"] <= hi]
    if not subset:
        return {"n": 0, "total": 0, "mean": 0.0, "max": 0}
    corrections = [r["corrections"] for r in subset]
    return {
        "n": len(subset),
        "total": sum(corrections),
        "mean": round(sum(corrections) / len(corrections), 3),
        "max": max(corrections),
    }


# ---------------------------------------------------------------------------
# ASCII chart
# ---------------------------------------------------------------------------

def ascii_bar_chart(
    labels: list[str],
    values: list[float],
    rolling: list[float],
    title: str = "Corrections per Session",
    width: int = 60,
) -> str:
    """Render a horizontal ASCII bar chart with rolling average markers."""
    max_val = max(max(values), 0.1)
    lines = [f"\n  {title}", "  " + "=" * (width + 20), ""]
    for i, (label, val, roll) in enumerate(zip(labels, values, rolling)):
        bar_len = int((val / max_val) * width)
        roll_pos = int((roll / max_val) * width)
        bar = "#" * bar_len
        # Append rolling average marker
        if roll_pos > bar_len:
            bar = bar + "." * (roll_pos - bar_len) + "|"
        elif roll_pos == bar_len:
            if bar:
                bar = bar[:-1] + "|"
            else:
                bar = "|"
        lines.append(f"  S{label:>3} [{val:>4.1f}] {bar:<{width + 2}}  roll={roll:.2f}")
    lines.append("")
    lines.append("  # = corrections this session   | = 5-session rolling avg")
    lines.append("  . = gap between bar and rolling avg marker")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_csv(records: list[dict[str, Any]], rolling: list[float], path: str) -> None:
    """Write session-level data to CSV."""
    fieldnames = [
        "session", "session_type", "corrections", "corrections_rolling5",
        "outputs", "corrections_per_output", "first_draft_acceptance",
        "audit_score",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for i, r in enumerate(records):
            writer.writerow(
                {
                    "session": r["session"],
                    "session_type": r["session_type"],
                    "corrections": r["corrections"],
                    "corrections_rolling5": round(rolling[i], 4),
                    "outputs": r["outputs"],
                    "corrections_per_output": r.get("corrections_per_output", ""),
                    "first_draft_acceptance": r.get("first_draft_acceptance", ""),
                    "audit_score": r.get("audit_score", ""),
                }
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to system.db")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path for CSV output")
    parser.add_argument(
        "--full-only",
        action="store_true",
        help="Restrict analysis to full/sales sessions only",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    try:
        corrections = load_corrections_from_db(conn)
        metrics = load_session_metrics(conn)
        scores = load_audit_scores(conn)
    finally:
        conn.close()

    all_records = build_session_records(corrections, metrics, scores)

    if args.full_only:
        records = [
            r for r in all_records if r["session_type"] in ("full", "unknown", "?")
        ]
        track_label = "full/sales sessions"
    else:
        records = all_records
        track_label = "all sessions"

    if not records:
        print("No session records found.", file=sys.stderr)
        sys.exit(1)

    correction_counts = [float(r["corrections"]) for r in records]
    session_nums = [r["session"] for r in records]
    rolling = rolling_average(correction_counts, window=5)

    # Linear regression
    slope, intercept, r2 = linear_regression(
        [float(s) for s in session_nums], correction_counts
    )

    # Period stats (on whatever subset we are analysing)
    s_min = min(session_nums)
    s_max = max(session_nums)
    s_third = s_min + (s_max - s_min) // 3
    s_twothird = s_min + 2 * (s_max - s_min) // 3

    early_stats = period_stats(records, s_min, s_third)
    mid_stats = period_stats(records, s_third + 1, s_twothird)
    recent_stats = period_stats(records, s_twothird + 1, s_max)

    # ASCII chart
    labels = [str(r["session"]) for r in records]
    chart = ascii_bar_chart(labels, correction_counts, rolling, title=f"Corrections per Session ({track_label})")

    # Print report
    print("=" * 70)
    print(f"  Gradata — Correction Density Report")
    print(f"  Database: {db_path}")
    print(f"  Track: {track_label}")
    print("=" * 70)
    print(chart)
    print()
    print(f"  SUMMARY STATISTICS")
    print(f"  Session range: S{s_min} – S{s_max}  ({len(records)} sessions)")
    print(f"  Total corrections: {int(sum(correction_counts))}")
    print(f"  Mean corrections/session: {sum(correction_counts)/len(records):.3f}")
    print()
    print(f"  Early  (S{s_min:>2}-{s_third:>2}): n={early_stats['n']:>2}, mean={early_stats['mean']:.2f}, max={early_stats['max']}")
    print(f"  Mid    (S{s_third+1:>2}-{s_twothird:>2}): n={mid_stats['n']:>2}, mean={mid_stats['mean']:.2f}, max={mid_stats['max']}")
    print(f"  Recent (S{s_twothird+1:>2}-{s_max:>2}): n={recent_stats['n']:>2}, mean={recent_stats['mean']:.2f}, max={recent_stats['max']}")
    print()
    print(f"  LINEAR REGRESSION (OLS)")
    print(f"  Slope:     {slope:+.4f} corrections/session")
    print(f"  Intercept: {intercept:.4f}")
    print(f"  R²:        {r2:.4f}  (values near 0 = trend not statistically significant)")
    trend_word = "DECREASING" if slope < -0.01 else ("INCREASING" if slope > 0.01 else "FLAT")
    print(f"  Trend:     {trend_word}")
    print()

    # Write CSV
    write_csv(records, rolling, args.csv)
    print(f"  CSV written to: {args.csv}")
    print()


if __name__ == "__main__":
    main()
