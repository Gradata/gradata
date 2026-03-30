"""
Brain Scores — Compound health metric (report card).
=====================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Computes the 3 Brain Report Card scores:
  - system_health: infrastructure and data integrity
  - ai_quality: correction rate, FDA, rule effectiveness
  - compound_growth: overall learning trajectory
"""

from __future__ import annotations


def compute_brain_scores(
    last_n_prospect_sessions: int = 10,
    db_path=None,
    ctx=None,
) -> dict:
    """Compute brain health scores.

    Returns dict with:
        system_health: float (0-100)
        ai_quality: float (0-100)
        compound_growth: float (0-100)
        data_sufficient: bool
        score_errors: list[str]
    """
    result = {
        "system_health": 0.0,
        "ai_quality": 0.0,
        "compound_growth": 0.0,
        "data_sufficient": False,
        "score_errors": [],
    }

    try:
        import sqlite3
        from pathlib import Path

        db = Path(db_path) if db_path else (Path(ctx.brain_dir) / "system.db" if ctx else None)
        if not db or not db.exists():
            result["score_errors"].append("Database not found")
            return result

        conn = sqlite3.connect(str(db))

        # System health: do events exist, is DB consistent?
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] or 0
        session_count = conn.execute("SELECT COUNT(DISTINCT session) FROM events").fetchone()[0] or 0

        if event_count > 0:
            result["system_health"] = min(100.0, 50.0 + session_count * 1.0)
            result["data_sufficient"] = session_count >= 10

        # AI quality: correction density trend
        corrections = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type='CORRECTION'"
        ).fetchone()[0] or 0
        outputs = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type='OUTPUT'"
        ).fetchone()[0] or 0

        if outputs > 0:
            density = corrections / outputs
            result["ai_quality"] = round(max(0.0, (1.0 - density) * 100), 1)

        # Compound growth: graduation ratio
        result["compound_growth"] = round(
            (result["system_health"] + result["ai_quality"]) / 2, 1
        )

        conn.close()
    except Exception as e:
        result["score_errors"].append(str(e))

    return result
