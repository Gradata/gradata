"""Freshness tracking for graduated rules.

Adapted from Hindsight's observation freshness model, but session-count-based
instead of calendar-based, and severity-weighted.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Trend(StrEnum):
    STABLE = "stable"
    STRENGTHENING = "strengthening"
    WEAKENING = "weakening"
    NEW = "new"
    STALE = "stale"


# Severity weights for density computation
SEVERITY_WEIGHTS = {
    "trivial": 0.5,
    "minor": 1.0,
    "moderate": 2.0,
    "major": 3.0,
    "rewrite": 5.0,
}


def compute_trend(
    correction_sessions: list[dict],
    current_session: int,
    recent_window: int = 5,
    old_window: int = 15,
) -> Trend:
    """Compute freshness trend from correction history.

    Args:
        correction_sessions: List of dicts with 'session' (int) and 'severity' (str) keys.
        current_session: Current session number.
        recent_window: Number of recent sessions to consider "recent".
        old_window: Total window size (recent + middle + old).

    Returns:
        Trend enum value.
    """
    if not correction_sessions:
        return Trend.STALE

    recent_cutoff = current_session - recent_window
    old_cutoff = current_session - old_window

    recent = [e for e in correction_sessions if e.get("session", 0) > recent_cutoff]
    old = [e for e in correction_sessions if e.get("session", 0) <= old_cutoff]
    middle = [
        e
        for e in correction_sessions
        if old_cutoff < e.get("session", 0) <= recent_cutoff
    ]

    if not recent:
        return Trend.STALE

    if not old and not middle:
        return Trend.NEW

    # Severity-weighted density
    def weighted_count(events: list[dict]) -> float:
        return sum(SEVERITY_WEIGHTS.get(e.get("severity", "minor"), 1.0) for e in events)

    recent_density = weighted_count(recent) / max(recent_window, 1)
    older_period = old_window - recent_window
    older_density = weighted_count(old + middle) / max(older_period, 1)

    if older_density == 0:
        return Trend.NEW

    ratio = recent_density / older_density

    if ratio > 1.5:
        return Trend.STRENGTHENING
    elif ratio < 0.5:
        return Trend.WEAKENING
    else:
        return Trend.STABLE


@dataclass
class FreshnessInfo:
    """Freshness metadata for a graduated rule."""

    last_fired_session: int | None = None
    sessions_since_fired: int = 0
    trend: Trend = Trend.NEW

    @property
    def is_stale(self) -> bool:
        return self.trend == Trend.STALE

    @property
    def staleness_penalty(self) -> float:
        """Retrieval ranking penalty for stale rules. 1.0 = no penalty."""
        if self.trend == Trend.STALE:
            return 0.5  # 50% penalty
        elif self.trend == Trend.WEAKENING:
            return 0.8  # 20% penalty
        elif self.trend == Trend.STRENGTHENING:
            return 1.2  # 20% boost
        return 1.0

    def confidence_decay(self, sessions_stale: int = 0) -> float:
        """Confidence decay for rules stale for many sessions.

        Returns negative delta to apply to confidence.
        Only triggers after 30+ sessions of staleness.
        """
        if sessions_stale < 30:
            return 0.0
        return -0.01 * (sessions_stale - 29)  # -0.01 per session after 30


def update_freshness(
    freshness: FreshnessInfo,
    correction_sessions: list[dict],
    current_session: int,
) -> FreshnessInfo:
    """Update freshness info from correction history."""
    freshness.trend = compute_trend(correction_sessions, current_session)
    if freshness.last_fired_session is not None:
        freshness.sessions_since_fired = current_session - freshness.last_fired_session
    return freshness


def mark_fired(freshness: FreshnessInfo, session: int) -> FreshnessInfo:
    """Mark a rule as fired in the given session."""
    freshness.last_fired_session = session
    freshness.sessions_since_fired = 0
    return freshness
