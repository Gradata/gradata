"""
Metrics — Rolling window quality metrics from events.
=====================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Provides MetricsWindow for snapshotting quality over a session window,
compute_blandness using inverted Type-Token Ratio (TTR), and
compute_metrics for aggregating event data into actionable numbers.

SPEC Section 5: correction density, edit distance, acceptance distribution,
rule success/misfire rates, blandness score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MetricsWindow:
    """Snapshot of quality metrics over a session window."""

    sessions: list = field(default_factory=list)
    window_size: int = 10
    sample_size: int = 0
    rewrite_rate: float = 0.0
    blandness_score: float = 0.0
    edit_distance_avg: float = 0.0
    correction_density: float = 0.0
    rule_success_rate: float = 0.0
    rule_misfire_rate: float = 0.0
    acceptance_distribution: dict = field(default_factory=dict)


def compute_blandness(text_list: list[str]) -> float:
    """Compute blandness using inverted Type-Token Ratio (TTR).

    TTR = unique_words / total_words. Blandness = 1 - TTR.
    0.0 = maximally diverse, 1.0 = maximally repetitive.

    SPEC Section 5: blandness threshold is 0.70 (inverted TTR = 0.30).
    McCarthy & Jarvis 2010, JSLHR: MTLD segmentation cutoff.

    Args:
        text_list: List of text strings to analyze.

    Returns:
        Blandness score in [0.0, 1.0]. Returns 0.0 for empty input.
    """
    if not text_list:
        return 0.0

    all_words: list[str] = []
    for text in text_list:
        words = re.findall(r"\b[a-z]+\b", text.lower())
        all_words.extend(words)

    if not all_words:
        return 0.0

    unique = len(set(all_words))
    total = len(all_words)
    ttr = unique / total  # 0.0 = all same word, 1.0 = all unique
    return round(1.0 - ttr, 4)  # invert: high = bland


def compute_metrics(
    db_path=None,
    window: int = 20,
    ctx=None,
) -> dict:
    """Compute rolling window metrics from events database.

    Returns dict with keys matching MetricsWindow fields.
    Returns empty dict if database is unavailable.
    """
    try:
        import sqlite3
        from pathlib import Path

        if ctx:
            db = Path(ctx.brain_dir) / "system.db"
        elif db_path:
            db = Path(db_path)
        else:
            return {}

        if not db.exists():
            return {}

        conn = sqlite3.connect(str(db))

        # Get last N sessions
        max_session = (
            conn.execute(
                "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
            ).fetchone()[0]
            or 0
        )
        min_session = max(1, max_session - window + 1)

        # Correction density
        outputs = (
            conn.execute(
                "SELECT COUNT(*) FROM events WHERE type='OUTPUT' AND session >= ?", (min_session,)
            ).fetchone()[0]
            or 0
        )
        corrections = (
            conn.execute(
                "SELECT COUNT(*) FROM events WHERE type='CORRECTION' AND session >= ?",
                (min_session,),
            ).fetchone()[0]
            or 0
        )
        density = corrections / outputs if outputs > 0 else 0.0

        conn.close()

        return {
            "window_size": window,
            "sample_size": outputs,
            "correction_density": round(density, 4),
            "sessions_covered": max_session - min_session + 1,
        }
    except Exception:
        return {}


def format_metrics(m) -> str:
    """Format a metrics result (MetricsWindow or dict) as human-readable summary.

    Accepts either a MetricsWindow dataclass instance or a dict with the same
    keys (as returned by compute_metrics).
    """
    from typing import Any

    def get(key: str, default: Any = 0) -> Any:
        if isinstance(m, dict):
            return m.get(key, default)
        return getattr(m, key, default)

    sample_size = int(get("sample_size", 0))
    window_size = int(get("window_size", 0))

    if sample_size == 0:
        return f"MetricsWindow (window={window_size})\n  No data — no OUTPUT events in window.\n"

    acceptance = get("acceptance_distribution", {}) or {}
    dist_parts = ", ".join(f"{k}: {v}" for k, v in sorted(acceptance.items()))

    blandness = float(get("blandness_score", 0.0))
    edit_avg = float(get("edit_distance_avg", get("avg_edit_distance", 0.0)))

    lines = [
        f"MetricsWindow (window={window_size}, outputs={sample_size})",
        f"  Rewrite rate:           {float(get('rewrite_rate', 0.0)):.1%}",
        f"  Avg edit distance:      {edit_avg:.2f}",
        f"  Acceptance dist:        {dist_parts or 'none'}",
        f"  Rule success rate:      {float(get('rule_success_rate', 0.0)):.1%}",
        f"  Rule misfire rate:      {float(get('rule_misfire_rate', 0.0)):.1%}",
        f"  Blandness score:        {blandness:.3f} ({'generic' if blandness > 0.7 else 'varied'})",
    ]
    return "\n".join(lines)
