"""
Success Conditions — 6-condition validation from Build Directive.
================================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

SPEC Section 5: ALL must be true across 20+ sessions:
  1. Correction rate decreases
  2. Edit distance decreases
  3. First-draft acceptance increases
  4. Rule success rate increases
  5. Misfire rate stays low or decreases
  6. Output does NOT become more generic (blandness < 0.70)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SuccessCondition:
    """A single success condition evaluation."""
    name: str
    met: bool = False
    value: float = 0.0
    threshold: float = 0.0
    detail: str = ""


@dataclass
class SuccessConditionsReport:
    """Result of evaluating all 6 success conditions."""
    all_met: bool = False
    conditions: list[SuccessCondition] = field(default_factory=list)
    window_size: int = 20
    sessions_evaluated: int = 0


def evaluate_success_conditions(
    db_path=None,
    window: int = 20,
    ctx=None,
) -> SuccessConditionsReport:
    """Evaluate the 6 SPEC success conditions over a session window.

    Returns a report with each condition's status.
    Basic open-source version — checks what data is available.
    """
    report = SuccessConditionsReport(window_size=window)

    conditions = [
        SuccessCondition(name="correction_rate_decreasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="edit_distance_decreasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="fda_increasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="rule_success_increasing", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="misfire_rate_low", detail="Requires 20+ sessions of data"),
        SuccessCondition(name="not_bland", detail="Requires blandness < 0.70"),
    ]

    try:
        import sqlite3
        from pathlib import Path

        db = Path(db_path) if db_path else (Path(ctx.brain_dir) / "system.db" if ctx else None)
        if db and db.exists():
            conn = sqlite3.connect(str(db))
            max_session = conn.execute(
                "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
            ).fetchone()[0] or 0
            report.sessions_evaluated = max_session
            conn.close()
    except Exception:
        pass

    report.conditions = conditions
    report.all_met = all(c.met for c in conditions)
    return report
