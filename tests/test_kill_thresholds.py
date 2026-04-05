"""Tests for inverted kill thresholds — mature rules live longer."""
from __future__ import annotations

from gradata.enhancements.self_improvement import KILL_LIMITS, MACHINE_KILL_LIMITS


def test_mature_rules_have_longer_grace_period():
    assert KILL_LIMITS["STABLE"] > KILL_LIMITS["INFANT"]
    assert KILL_LIMITS["MATURE"] > KILL_LIMITS["ADOLESCENT"]


def test_machine_kill_limits_also_inverted():
    assert MACHINE_KILL_LIMITS["STABLE"] > MACHINE_KILL_LIMITS["INFANT"]


def test_kill_limits_monotonically_increasing():
    order = ["INFANT", "ADOLESCENT", "MATURE", "STABLE"]
    for i in range(len(order) - 1):
        assert KILL_LIMITS[order[i]] < KILL_LIMITS[order[i + 1]], \
            f"{order[i]} ({KILL_LIMITS[order[i]]}) should be < {order[i+1]} ({KILL_LIMITS[order[i+1]]})"
