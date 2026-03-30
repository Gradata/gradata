"""
Correction Tracking — Density, half-life, MTBF/MTTR.
=====================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Tracks correction patterns over time: how often corrections occur,
how long between them (MTBF), and how quickly they're resolved (MTTR).
"""

from __future__ import annotations


def compute_density(
    corrections: int = 0,
    outputs: int = 0,
    **kwargs,
) -> float:
    """Compute correction density: corrections / outputs.

    Args:
        corrections: Number of corrections in the window.
        outputs: Number of outputs in the window.

    Returns:
        Density ratio in [0.0, 1.0]. Returns 0.0 if no outputs.
    """
    if outputs <= 0:
        return 0.0
    return round(corrections / outputs, 6)


def compute_half_life(
    corrections_by_session: list[int],
) -> float | None:
    """Compute the half-life of correction frequency.

    Half-life = number of sessions for correction rate to halve.
    Returns None if insufficient data.
    """
    if len(corrections_by_session) < 10:
        return None

    first_half = sum(corrections_by_session[:5])
    second_half = sum(corrections_by_session[5:10])

    if first_half <= 0:
        return None
    if second_half >= first_half:
        return None  # Not decreasing

    ratio = second_half / first_half
    if ratio <= 0:
        return 5.0  # Corrections went to zero in 5 sessions

    import math
    return round(-5.0 / math.log2(ratio), 1)


def compute_mtbf(
    correction_sessions: list[int],
) -> float | None:
    """Mean Time Between Failures (corrections).

    Returns average number of sessions between corrections.
    None if fewer than 2 corrections.
    """
    if len(correction_sessions) < 2:
        return None

    sorted_sessions = sorted(correction_sessions)
    gaps = [
        sorted_sessions[i + 1] - sorted_sessions[i]
        for i in range(len(sorted_sessions) - 1)
    ]
    return round(sum(gaps) / len(gaps), 1) if gaps else None
