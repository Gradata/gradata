"""Tests for sliding-window query budgeting."""

import time

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
        qb = QueryBudget(window_seconds=300, max_calls=1000)

        # 10 slow calls spread across ~2s (5 calls/sec average)
        for _ in range(10):
            qb.record("ep")
            time.sleep(0.2)

        # 50 fast calls in a tight burst (>>15 calls/sec)
        for _ in range(50):
            qb.record("ep")

        result = qb.detect_anomalies("ep")
        assert result["burst"] is True

    def test_no_false_positive_on_normal_usage(self):
        qb = QueryBudget(window_seconds=300, max_calls=1000)
        # 20 calls at a steady pace
        for _ in range(20):
            qb.record("ep")
            time.sleep(0.02)
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
        qb = QueryBudget(window_seconds=1, max_calls=100)
        qb.record("ep")
        assert qb.count("ep") == 1
        time.sleep(1.1)
        assert qb.count("ep") == 0
