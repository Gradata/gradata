"""
Rolling-window metrics engine for Gradata.
===================================================
Event-sourced: computes quality signals from OUTPUT, CORRECTION, and
RULE_APPLICATION events in the events table. No domain tables needed.

Public API
----------
compute_metrics(db_path, window) -> MetricsWindow
compute_blandness(texts)          -> float
format_metrics(m)                 -> str
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MetricsWindow:
    """Snapshot of brain quality signals over the last N sessions.

    Attributes:
        window_size: Number of sessions included in this snapshot.
        rewrite_rate: Fraction of outputs that were heavily edited (0.0 - 1.0).
        avg_edit_distance: Mean edit_distance from OUTPUT events (if tracked).
        acceptance_distribution: Counts of edit severity labels.
        rule_success_rate: Fraction of RULE_APPLICATION events accepted (0.0 - 1.0).
        rule_misfire_rate: Fraction of RULE_APPLICATION events misfired (0.0 - 1.0).
        blandness_score: Vocabulary diversity inverted (0.0 = unique, 1.0 = generic).
        sample_size: Number of OUTPUT events in the window.
        correction_count: Number of CORRECTION events in the window.
        first_draft_acceptance: Fraction of outputs not edited by user.
    """

    window_size: int = 20
    rewrite_rate: float = 0.0
    avg_edit_distance: float = 0.0
    acceptance_distribution: dict[str, int] = field(default_factory=dict)
    rule_success_rate: float = 0.0
    rule_misfire_rate: float = 0.0
    blandness_score: float = 0.0
    sample_size: int = 0
    correction_count: int = 0
    first_draft_acceptance: float = 0.0


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def compute_blandness(texts: list[str]) -> float:
    """Compute blandness via inverted type-token ratio.

    TTR = unique_words / total_words. Blandness = 1.0 - TTR.
    Returns 0.0 when texts is empty.
    """
    if not texts:
        return 0.0

    all_words: list[str] = []
    for text in texts:
        tokens = [w for w in re.split(r"[^a-z]+", text.lower()) if w]
        all_words.extend(tokens)

    total = len(all_words)
    if total == 0:
        return 0.0

    unique = len(set(all_words))
    ttr = unique / total
    return round(1.0 - ttr, 4)


# ---------------------------------------------------------------------------
# Event query helpers
# ---------------------------------------------------------------------------

def _query_output_events(
    conn: sqlite3.Connection, window: int
) -> tuple[list[dict], list[str]]:
    """Fetch OUTPUT events from the last N sessions.

    Returns (event_data_list, output_texts).
    """
    try:
        rows = conn.execute(
            """
            SELECT data_json FROM events
            WHERE type = 'OUTPUT'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            ORDER BY id DESC
            """,
            (window - 1,),
        ).fetchall()
    except sqlite3.OperationalError:
        return [], []

    dicts: list[dict] = []
    texts: list[str] = []
    for (data_json,) in rows:
        data = json.loads(data_json) if data_json else {}
        dicts.append(data)
        # Collect output text for blandness scoring
        for key in ("output_text", "draft_text", "text", "content"):
            if data.get(key):
                texts.append(str(data[key]))
                break

    return dicts, texts


def _query_correction_events(
    conn: sqlite3.Connection, window: int
) -> list[dict]:
    """Fetch CORRECTION events from the last N sessions."""
    try:
        rows = conn.execute(
            """
            SELECT data_json FROM events
            WHERE type = 'CORRECTION'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            ORDER BY id DESC
            """,
            (window - 1,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    return [json.loads(r[0]) if r[0] else {} for r in rows]


def _query_rule_application_events(
    conn: sqlite3.Connection, window: int
) -> tuple[int, int, int]:
    """Fetch RULE_APPLICATION event stats from the last N sessions.

    Returns (total, accepted_count, misfire_count).
    """
    try:
        rows = conn.execute(
            """
            SELECT data_json FROM events
            WHERE type = 'RULE_APPLICATION'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            ORDER BY id DESC
            """,
            (window - 1,),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0, 0, 0

    total = len(rows)
    accepted = 0
    misfired = 0
    for (data_json,) in rows:
        data = json.loads(data_json) if data_json else {}
        if data.get("accepted"):
            accepted += 1
        if data.get("misfired"):
            misfired += 1

    return total, accepted, misfired


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_metrics(db_path: Path, window: int = 20) -> MetricsWindow:
    """Compute rolling-window quality metrics from event data.

    Queries OUTPUT, CORRECTION, and RULE_APPLICATION events from the
    events table. If the table doesn't exist, returns zero-state.
    """
    from pathlib import Path as _Path
    result = MetricsWindow(window_size=window)

    if not _Path(db_path).exists():
        return result

    conn = sqlite3.connect(str(db_path))
    try:
        # --- OUTPUT events ---
        output_data, texts = _query_output_events(conn, window)
        result.sample_size = len(output_data)

        if output_data:
            # First-draft acceptance: outputs not heavily edited by user
            unedited = sum(1 for d in output_data if not d.get("major_edit", False))
            result.first_draft_acceptance = round(unedited / len(output_data), 4)

            # Edit distance (if tracked in OUTPUT events)
            distances = [d.get("edit_distance", 0.0) for d in output_data if d.get("edit_distance")]
            if distances:
                result.avg_edit_distance = round(sum(distances) / len(distances), 4)

            # Severity distribution (if tracked)
            dist: dict[str, int] = {}
            for d in output_data:
                severity = d.get("severity", "accepted")
                dist[severity] = dist.get(severity, 0) + 1
            result.acceptance_distribution = dist

            rewrite_count = sum(v for k, v in dist.items() if k in ("major", "discarded"))
            result.rewrite_rate = round(rewrite_count / len(output_data), 4)

        # --- Blandness ---
        result.blandness_score = compute_blandness(texts)

        # --- CORRECTION events ---
        corrections = _query_correction_events(conn, window)
        result.correction_count = len(corrections)

        # --- RULE_APPLICATION events ---
        total_rules, accepted_rules, misfire_rules = _query_rule_application_events(conn, window)
        if total_rules > 0:
            result.rule_success_rate = round(accepted_rules / total_rules, 4)
            result.rule_misfire_rate = round(misfire_rules / total_rules, 4)

    finally:
        conn.close()

    return result


def format_metrics(m: MetricsWindow) -> str:
    """Format a MetricsWindow as human-readable multi-line summary."""
    if m.sample_size == 0:
        return (
            f"MetricsWindow (window={m.window_size})\n"
            "  No data — no OUTPUT events in window.\n"
        )

    dist_parts = ", ".join(
        f"{k}: {v}" for k, v in sorted(m.acceptance_distribution.items())
    )

    lines = [
        f"MetricsWindow (window={m.window_size}, outputs={m.sample_size}, corrections={m.correction_count})",
        f"  First-draft acceptance: {m.first_draft_acceptance:.1%}",
        f"  Rewrite rate:           {m.rewrite_rate:.1%}",
        f"  Avg edit distance:      {m.avg_edit_distance:.2f}",
        f"  Acceptance dist:        {dist_parts or 'none'}",
        f"  Rule success rate:      {m.rule_success_rate:.1%}",
        f"  Rule misfire rate:      {m.rule_misfire_rate:.1%}",
        f"  Blandness score:        {m.blandness_score:.3f} "
        f"({'generic' if m.blandness_score > 0.7 else 'varied'})",
    ]
    return "\n".join(lines)
