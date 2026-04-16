"""Tests for freshness tracking on graduated rules."""
import pytest
from gradata.enhancements.freshness import (
    Trend,
    compute_trend,
    FreshnessInfo,
    update_freshness,
    mark_fired,
    SEVERITY_WEIGHTS,
)


class TestComputeTrend:
    def test_empty_corrections_returns_stale(self):
        assert compute_trend([], current_session=50) == Trend.STALE

    def test_all_recent_returns_new(self):
        corrections = [
            {"session": 48, "severity": "minor"},
            {"session": 49, "severity": "minor"},
        ]
        assert compute_trend(corrections, current_session=50) == Trend.NEW

    def test_no_recent_returns_stale(self):
        corrections = [
            {"session": 10, "severity": "minor"},
            {"session": 15, "severity": "minor"},
        ]
        assert compute_trend(corrections, current_session=50) == Trend.STALE

    def test_accelerating_returns_strengthening(self):
        # 5 recent corrections (sessions 46-50) vs 2 old corrections (sessions 30-35)
        corrections = [
            {"session": 30, "severity": "minor"},
            {"session": 35, "severity": "minor"},
            {"session": 46, "severity": "minor"},
            {"session": 47, "severity": "minor"},
            {"session": 48, "severity": "minor"},
            {"session": 49, "severity": "minor"},
            {"session": 50, "severity": "minor"},
        ]
        assert compute_trend(corrections, current_session=50) == Trend.STRENGTHENING

    def test_decelerating_returns_weakening(self):
        # 1 recent vs 10 old
        corrections = [{"session": i, "severity": "minor"} for i in range(30, 40)]
        corrections.append({"session": 49, "severity": "minor"})
        assert compute_trend(corrections, current_session=50) == Trend.WEAKENING

    def test_steady_returns_stable(self):
        # Equal density: 2 recent events over 5-session window (0.4/session),
        # 4 old+middle events over 10-session window (0.4/session) -> ratio=1.0
        corrections = [
            {"session": 30, "severity": "minor"},
            {"session": 33, "severity": "minor"},
            {"session": 38, "severity": "minor"},
            {"session": 42, "severity": "minor"},
            {"session": 46, "severity": "minor"},
            {"session": 48, "severity": "minor"},
        ]
        assert compute_trend(corrections, current_session=50) == Trend.STABLE

    def test_severity_weighting(self):
        # 1 rewrite (weight 5) recent vs 5 trivial (weight 0.5 each = 2.5) old
        corrections = [
            {"session": 30, "severity": "trivial"},
            {"session": 31, "severity": "trivial"},
            {"session": 32, "severity": "trivial"},
            {"session": 33, "severity": "trivial"},
            {"session": 34, "severity": "trivial"},
            {"session": 49, "severity": "rewrite"},
        ]
        # recent density = 5/5 = 1.0, old density = 2.5/10 = 0.25
        # ratio = 4.0 > 1.5 -> STRENGTHENING
        assert compute_trend(corrections, current_session=50) == Trend.STRENGTHENING


class TestFreshnessInfo:
    def test_stale_penalty(self):
        f = FreshnessInfo(trend=Trend.STALE)
        assert f.staleness_penalty == 0.5

    def test_strengthening_boost(self):
        f = FreshnessInfo(trend=Trend.STRENGTHENING)
        assert f.staleness_penalty == 1.2

    def test_no_decay_under_30_sessions(self):
        f = FreshnessInfo()
        assert f.confidence_decay(sessions_stale=29) == 0.0

    def test_decay_after_30_sessions(self):
        f = FreshnessInfo()
        assert f.confidence_decay(sessions_stale=31) == pytest.approx(-0.02)

    def test_mark_fired_resets(self):
        f = FreshnessInfo(last_fired_session=10, sessions_since_fired=40)
        mark_fired(f, session=50)
        assert f.last_fired_session == 50
        assert f.sessions_since_fired == 0
