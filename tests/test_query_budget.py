"""Tests for sliding-window query budgeting."""

from unittest.mock import patch

import pytest

from gradata.security.query_budget import QueryBudget


class TestRecordAndCount:
    """record() stores timestamps, count() returns the window total."""

    def test_count_after_records(self):
        qb = QueryBudget(window_seconds=60, max_calls=100)
        for _ in range(5):
            qb.record("apply_rules")
        assert qb.count("apply_rules") == 5

    def test_count_zero_for_unknown_endpoint(self):
        qb = QueryBudget()
        assert qb.count("unknown") == 0


class TestRateLimitExceeded:
    """is_rate_exceeded returns True after max_calls+1."""

    def test_exceeded_after_max_plus_one(self):
        budget = 10
        qb = QueryBudget(window_seconds=60, max_calls=budget)
        for _ in range(budget):
            qb.record("ep")
        assert not qb.is_rate_exceeded("ep")
        qb.record("ep")  # max_calls + 1
        assert qb.is_rate_exceeded("ep")


class TestBurstDetection:
    """detect_anomalies flags bursts when recent rate > 3x average."""

    def test_burst_detected(self):
        """Simulate slow calls then a fast burst using mocked time."""
        _clock = [0.0]

        def _monotonic():
            return _clock[0]

        with patch("gradata.security.query_budget.time") as mock_time:
            mock_time.monotonic = _monotonic
            qb = QueryBudget(window_seconds=300, max_calls=1000)

            # 10 slow calls spread across 2s
            for _ in range(10):
                qb.record("ep")
                _clock[0] += 0.2

            # 50 fast calls in a tight burst
            for _ in range(50):
                qb.record("ep")
                _clock[0] += 0.001

            result = qb.detect_anomalies("ep")
            assert result["burst"] is True

    def test_no_false_positive_on_normal_usage(self):
        """Steady-pace calls should not trigger burst detection."""
        _clock = [0.0]

        def _monotonic():
            return _clock[0]

        with patch("gradata.security.query_budget.time") as mock_time:
            mock_time.monotonic = _monotonic
            qb = QueryBudget(window_seconds=300, max_calls=1000)

            for _ in range(20):
                qb.record("ep")
                _clock[0] += 0.02

            result = qb.detect_anomalies("ep")
            assert result["burst"] is False

    def test_below_minimum_calls_no_burst(self):
        qb = QueryBudget(window_seconds=300, max_calls=1000)
        for _ in range(5):
            qb.record("ep")
        result = qb.detect_anomalies("ep")
        assert result["burst"] is False


class TestWindowExpiry:
    """Expired timestamps are pruned and count drops to 0."""

    def test_window_expiry(self):
        """Use mocked time to simulate window expiry without sleeping."""
        _clock = [0.0]

        def _monotonic():
            return _clock[0]

        with patch("gradata.security.query_budget.time") as mock_time:
            mock_time.monotonic = _monotonic
            qb = QueryBudget(window_seconds=1, max_calls=100)
            qb.record("ep")
            assert qb.count("ep") == 1

            _clock[0] += 1.1  # Advance past the 1s window
            assert qb.count("ep") == 0


class TestInitValidation:
    """Constructor rejects invalid parameters."""

    def test_rejects_zero_window(self):
        with pytest.raises(ValueError, match="positive"):
            QueryBudget(window_seconds=0)

    def test_rejects_negative_window(self):
        with pytest.raises(ValueError, match="positive"):
            QueryBudget(window_seconds=-1)

    def test_rejects_negative_max_calls(self):
        with pytest.raises(ValueError, match="non-negative"):
            QueryBudget(max_calls=-1)

    def test_accepts_zero_max_calls(self):
        qb = QueryBudget(max_calls=0)
        assert qb.max_calls == 0
