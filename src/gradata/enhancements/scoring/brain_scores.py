"""
Brain Scores — compound health metric for an Gradata.
=========================================================
Wraps the authoritative ``compute_brain_scores()`` implementation in
``gradata._events`` and reshapes its dict return value into a typed
``BrainScores`` dataclass.

Design contract:
- This module does NOT reimplement the 130+ line scoring algorithm.
- It delegates to ``gradata._events.compute_brain_scores`` and maps
  the result into ``BrainScores``.
- If that import fails (e.g., during testing with a minimal stub), a
  lightweight fallback computes a simplified version directly from the
  events table using only stdlib.

Stdlib only: sqlite3, dataclasses, math.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class BrainScores:
    """Compound health metrics for a brain at a point in time.

    Attributes:
        system_health: Infrastructure quality score, 0–100.  Reflects gate
            pass rate, event emission consistency, and tag coverage.
        ai_quality: Output quality score, 0–100.  Reflects first-draft
            acceptance, correction density, and calibration accuracy.
        compound_growth: Business-outcome index, typically 100 at baseline.
            Above 100 means outperforming baseline; below means under.
        arch_quality: Systems/architecture quality score, 0–100.  Measures
            whether system-building sessions caused regressions.
        brier_score: Calibration accuracy as a Brier score (0.0 = perfect,
            1.0 = worst).  ``None`` when insufficient data.
        brier_calibration: Human label for the Brier score — one of
            ``"EXCELLENT"``, ``"GOOD"``, ``"FAIR"``, ``"POOR"``,
            ``"WORSE_THAN_RANDOM"``, or ``"NO_DATA"``.
        data_sufficient: ``True`` when enough sessions exist for the scores
            to be statistically meaningful (typically >= 3 sessions).
        score_errors: List of component names that raised exceptions during
            computation.  An empty list means all components succeeded.
    """

    system_health: float = 0.0
    ai_quality: float = 0.0
    compound_growth: float = 100.0
    arch_quality: float = 0.0
    brier_score: float | None = None
    brier_calibration: str = "NO_DATA"
    data_sufficient: bool = False
    score_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fallback: lightweight scorer from raw events table
# ---------------------------------------------------------------------------


def _fallback_brain_scores(
    db_path: Path,
    last_n_sessions: int,
) -> BrainScores:
    """Minimal brain-score computation using only the events table.

    Used when ``gradata._events`` is not importable.  Computes a subset
    of scores sufficient for a useful health snapshot:

    - ``system_health``: ratio of sessions with at least one GATE_RESULT
      event to total distinct sessions (capped at 100).
    - ``ai_quality``: 100 minus (correction_rate * 100), where
      correction_rate = corrections / (corrections + outputs).
    - ``compound_growth``: always 100.0 (no CRM data available).
    - ``arch_quality``: 0.0 (no session_metrics table guaranteed).

    Args:
        db_path: Path to the brain's ``system.db``.
        last_n_sessions: Number of most-recent sessions to include.

    Returns:
        A BrainScores with scores derived only from the events table.
    """
    errors: list[str] = []
    system_health = 0.0
    ai_quality = 0.0
    data_sufficient = False

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row

        # Determine session window
        max_row = conn.execute(
            "SELECT COALESCE(MAX(session), 0) FROM events"
        ).fetchone()
        max_session: int = int(max_row[0]) if max_row else 0
        min_session = max(0, max_session - (last_n_sessions - 1))

        # --- System health: sessions with any GATE_RESULT / total sessions ---
        total_sessions_row = conn.execute(
            "SELECT COUNT(DISTINCT session) FROM events WHERE session >= ?",
            (min_session,),
        ).fetchone()
        total_sessions = int(total_sessions_row[0]) if total_sessions_row else 0

        gate_sessions_row = conn.execute(
            "SELECT COUNT(DISTINCT session) FROM events "
            "WHERE type = 'GATE_RESULT' AND session >= ?",
            (min_session,),
        ).fetchone()
        gate_sessions = int(gate_sessions_row[0]) if gate_sessions_row else 0

        if total_sessions > 0:
            system_health = round(
                min(100.0, (gate_sessions / total_sessions) * 100.0), 1
            )

        # --- AI quality: inverse of correction density ---
        totals = conn.execute(
            """
            SELECT
                SUM(CASE WHEN type = 'CORRECTION' THEN 1 ELSE 0 END),
                SUM(CASE WHEN type = 'OUTPUT'     THEN 1 ELSE 0 END)
            FROM events
            WHERE session >= ?
            """,
            (min_session,),
        ).fetchone()
        corrections = int(totals[0] or 0)
        outputs = int(totals[1] or 0)
        total_signal = corrections + outputs
        if total_signal > 0:
            corr_rate = corrections / total_signal
            ai_quality = round(max(0.0, 100.0 * (1.0 - corr_rate)), 1)

        data_sufficient = total_sessions >= 3
        conn.close()

    except Exception as exc:
        errors.append(f"fallback_scorer: {exc}")

    return BrainScores(
        system_health=system_health,
        ai_quality=ai_quality,
        compound_growth=100.0,
        arch_quality=0.0,
        brier_score=None,
        brier_calibration="NO_DATA",
        data_sufficient=data_sufficient,
        score_errors=errors,
    )


# ---------------------------------------------------------------------------
# Dict → BrainScores reshaper
# ---------------------------------------------------------------------------


def _reshape(raw: dict) -> BrainScores:
    """Convert the dict returned by _events.compute_brain_scores into BrainScores.

    Args:
        raw: The dict returned by the authoritative scorer.

    Returns:
        A BrainScores dataclass with values copied from the dict.
        Missing keys fall back to their dataclass defaults.
    """
    return BrainScores(
        system_health=float(raw.get("system_health", 0.0)),
        ai_quality=float(raw.get("ai_quality", 0.0)),
        compound_growth=float(raw.get("compound_growth", 100.0)),
        arch_quality=float(raw.get("arch_quality", 0.0)),
        brier_score=raw.get("brier_score"),  # may be None
        brier_calibration=str(raw.get("brier_calibration", "NO_DATA")),
        data_sufficient=bool(raw.get("data_sufficient", False)),
        score_errors=list(raw.get("score_errors", [])),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_brain_scores(
    db_path: Path,
    last_n_prospect_sessions: int = 10,
) -> BrainScores:
    """Compute compound brain health scores.

    Delegates to ``gradata._events.compute_brain_scores`` (the
    authoritative 130+ line implementation) and reshapes its dict into a
    typed ``BrainScores`` dataclass.

    If the import fails for any reason, falls back to a simplified scorer
    that computes a useful subset of scores directly from the events table.

    .. note::
        The authoritative scorer reads from ``gradata._paths.DB_PATH``
        (a module-level global), not from the ``db_path`` parameter.  When
        the calling code has previously called ``Brain.init()`` or
        ``_paths.set_brain_dir()``, those globals will already point at the
        correct database.  If you are calling this function in isolation
        (e.g., in a test), ensure ``BRAIN_DIR`` env var or
        ``_paths.set_brain_dir()`` is set first; otherwise the fallback
        scorer, which does use ``db_path`` directly, will be used.

    Args:
        db_path: Path to the brain's ``system.db``.  Used by the fallback
            scorer and for validation.
        last_n_prospect_sessions: Rolling window size passed to the
            authoritative scorer.

    Returns:
        A fully populated BrainScores.
    """
    # Primary path: delegate to the authoritative implementation
    try:
        from ... import _events as _events
        _fn = getattr(_events, "compute_brain_scores", None)
        if _fn is None:
            raise AttributeError("compute_brain_scores not available")
        raw: dict = _fn(
            last_n_prospect_sessions=last_n_prospect_sessions
        )
        return _reshape(raw)

    except Exception:
        # Fallback: compute directly from events table via db_path
        return _fallback_brain_scores(db_path, last_n_prospect_sessions)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_CALIBRATION_SYMBOL: dict[str, str] = {
    "EXCELLENT": "++",
    "GOOD": "+",
    "FAIR": "~",
    "POOR": "-",
    "WORSE_THAN_RANDOM": "--",
    "NO_DATA": "?",
}


def _bar(value: float, max_val: float = 100.0, width: int = 20) -> str:
    """Render a simple ASCII progress bar.

    Args:
        value: Current value.
        max_val: Maximum value (100% mark).
        width: Character width of the full bar.

    Returns:
        A string like ``"[####................] 42.0%"``.
    """
    clamped = max(0.0, min(value, max_val))
    filled = round((clamped / max_val) * width)
    bar = "#" * filled + "." * (width - filled)
    return f"[{bar}] {value:.1f}%"


def format_brain_scores(scores: BrainScores) -> str:
    """Render a BrainScores as a human-readable report card.

    Args:
        scores: A BrainScores returned by compute_brain_scores.

    Returns:
        Multi-line string suitable for logging or terminal display.
    """
    cal_sym = _CALIBRATION_SYMBOL.get(scores.brier_calibration, "?")

    brier_line = (
        f"  Calibration (Brier) : {scores.brier_score:.4f}  [{cal_sym} {scores.brier_calibration}]"
        if scores.brier_score is not None
        else "  Calibration (Brier) : NO DATA"
    )

    growth_bar_max = max(200.0, scores.compound_growth)
    growth_filled = round((min(scores.compound_growth, growth_bar_max) / growth_bar_max) * 20)
    growth_bar = "#" * growth_filled + "." * (20 - growth_filled)

    lines: list[str] = [
        "Brain Report Card",
        "=================",
        f"System Health  : {_bar(scores.system_health)}",
        f"AI Quality     : {_bar(scores.ai_quality)}",
        f"Arch Quality   : {_bar(scores.arch_quality)}",
        f"Compound Growth: [{growth_bar}] {scores.compound_growth:.1f}% (vs baseline)",
        "",
        brier_line,
        "",
        f"Data sufficient: {'Yes' if scores.data_sufficient else 'No (< 3 sessions)'}",
    ]

    if scores.score_errors:
        lines.append("")
        lines.append("Score errors:")
        for err in scores.score_errors:
            lines.append(f"  - {err}")

    return "\n".join(lines)
