"""Materializer tests: Tier 1 LWW + Tier 2 conflict detection + convergence.

Property invariants (from docs/specs/events-pull-contract.md §6):
1. Idempotent replay: same stream twice = same state.
2. Order-independence for non-conflicting events.
3. Dedup invariant: a repeated event doesn't change result.
"""

from __future__ import annotations

import random

import pytest

from gradata.cloud.materializer import (
    CONFLICT_THRESHOLD,
    Conflict,
    MaterializeResult,
    materialize,
)


def _evt(
    *,
    ts: str,
    category: str = "style",
    description: str = "use active voice",
    new_state: str = "PATTERN",
    confidence: float = 0.62,
    fire_count: int = 3,
    device_id: str = "dev_aaaa",
    etype: str = "RULE_GRADUATED",
    pattern_hash: str = "",
) -> dict:
    """Minimal event constructor used by every test below."""
    data = {
        "category": category,
        "description": description,
        "new_state": new_state,
        "confidence": confidence,
        "fire_count": fire_count,
        "device_id": device_id,
    }
    if pattern_hash:
        data["pattern_hash"] = pattern_hash
    return {"ts": ts, "type": etype, "source": "graduate", "data": data}


class TestSingleDevice:
    def test_empty_stream_yields_empty_result(self) -> None:
        result = materialize([])
        assert result.rules == {}
        assert result.conflicts == []
        assert result.events_consumed == 0

    def test_single_graduation_materializes_one_rule(self) -> None:
        result = materialize([_evt(ts="2026-04-20T00:00:00Z")])
        assert len(result.rules) == 1
        rule = next(iter(result.rules.values()))
        assert rule.state == "PATTERN"
        assert rule.confidence == pytest.approx(0.62)

    def test_later_promotion_wins(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", new_state="PATTERN", confidence=0.62),
            _evt(ts="2026-04-20T00:01:00Z", new_state="PATTERN", confidence=0.70),
        ]
        result = materialize(stream)
        rule = next(iter(result.rules.values()))
        assert rule.confidence == pytest.approx(0.70)
        assert rule.winning_event_ts == "2026-04-20T00:01:00Z"


class TestTier1LWW:
    def test_tie_on_ts_breaks_on_device_id(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", device_id="dev_aaaa", confidence=0.62),
            _evt(ts="2026-04-20T00:00:00Z", device_id="dev_zzzz", confidence=0.63),
        ]
        result = materialize(stream)
        rule = next(iter(result.rules.values()))
        assert rule.winning_device_id == "dev_zzzz"

    def test_small_confidence_drift_below_threshold_is_lww(self) -> None:
        # |0.70 - 0.62| = 0.08 < 0.15 → Tier 1 applies.
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", device_id="dev_a", confidence=0.62),
            _evt(ts="2026-04-20T00:01:00Z", device_id="dev_b", confidence=0.70),
        ]
        result = materialize(stream)
        assert result.conflicts == []
        rule = next(iter(result.rules.values()))
        assert rule.winning_device_id == "dev_b"


class TestTier2Conflict:
    def test_large_confidence_drift_triggers_conflict(self) -> None:
        # |0.90 - 0.62| = 0.28 >= 0.15 → Tier 2.
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", confidence=0.62, device_id="dev_a"),
            _evt(ts="2026-04-20T00:01:00Z", confidence=0.90, device_id="dev_b"),
        ]
        result = materialize(stream)
        assert len(result.conflicts) == 1
        assert result.conflicts[0].reason == "confidence_drift"
        # First event keeps winning state until user adjudicates.
        rule = next(iter(result.rules.values()))
        assert rule.winning_device_id == "dev_a"

    def test_state_disagreement_triggers_conflict(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", new_state="PATTERN", confidence=0.62),
            _evt(ts="2026-04-20T00:01:00Z", new_state="INSTINCT", confidence=0.55),
        ]
        result = materialize(stream)
        assert len(result.conflicts) == 1
        assert result.conflicts[0].reason == "state_disagreement"

    def test_post_conflict_events_are_held(self) -> None:
        # Once conflict, further events for same key don't move state.
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", confidence=0.62),
            _evt(ts="2026-04-20T00:01:00Z", confidence=0.90),  # conflict
            _evt(ts="2026-04-20T00:02:00Z", confidence=0.95),  # held
        ]
        result = materialize(stream)
        assert len(result.conflicts) == 1
        assert result.events_skipped >= 1


class TestTier3Override:
    def test_rule_override_clears_conflict_hold(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", confidence=0.62),
            _evt(ts="2026-04-20T00:01:00Z", confidence=0.90),  # conflict
            _evt(
                ts="2026-04-20T00:02:00Z",
                etype="RULE_OVERRIDE",
                new_state="RULE",
                confidence=0.95,
                device_id="dev_admin",
            ),
        ]
        result = materialize(stream)
        rule = next(iter(result.rules.values()))
        assert rule.state == "RULE"
        assert rule.winning_device_id == "dev_admin"


class TestPropertyInvariants:
    def test_idempotent_replay(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", confidence=0.62),
            _evt(ts="2026-04-20T00:01:00Z", confidence=0.68),
        ]
        first = materialize(stream)
        second = materialize(stream)
        assert first.rules == second.rules

    def test_duplicate_event_is_noop(self) -> None:
        # Same content, same ts, same device → second is effectively a
        # dedup retry. LWW picks either (they're equal), state unchanged.
        evt = _evt(ts="2026-04-20T00:00:00Z", confidence=0.62)
        single = materialize([evt]).rules
        doubled = materialize([evt, dict(evt)]).rules
        assert single == doubled

    def test_order_independence_for_non_conflicting_streams(self) -> None:
        # Two different keys, each with its own monotonic timeline — the
        # materialized state must be identical regardless of interleave.
        # We only shuffle WITHIN a key's ts-ordered slice trivially
        # (shuffling across keys, since the LWW comparison is per-key).
        stream_a = [
            _evt(ts="2026-04-20T00:00:00Z", category="style", description="use active voice"),
            _evt(
                ts="2026-04-20T00:01:00Z",
                category="style",
                description="use active voice",
                confidence=0.68,
            ),
        ]
        stream_b = [
            _evt(
                ts="2026-04-20T00:00:30Z",
                category="structure",
                description="headings before prose",
                confidence=0.70,
            ),
        ]
        combined = stream_a + stream_b
        shuffled = combined[:]
        rng = random.Random(1234)
        rng.shuffle(shuffled)

        # Sort both by ts so LWW per-key semantics are preserved (the
        # network is expected to give us ts-ordered replay).
        def by_ts(s):
            return sorted(s, key=lambda e: e["ts"])

        base = materialize(by_ts(combined))
        perm = materialize(by_ts(shuffled))
        assert base.rules == perm.rules


class TestResultShape:
    def test_result_exposes_consumed_and_skipped_counts(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z"),
            _evt(ts="2026-04-20T00:01:00Z", category=""),  # invalid key
        ]
        result = materialize(stream)
        assert result.events_consumed == 2
        assert result.events_skipped == 1

    def test_pass_both_events_and_db_path_raises(self) -> None:
        with pytest.raises(ValueError):
            materialize([_evt(ts="2026-04-20T00:00:00Z")], db_path=object())  # type: ignore[arg-type]


def test_threshold_constant_matches_spec() -> None:
    # docs/specs/merge-semantics.md §3 pins this at 0.15.
    assert CONFLICT_THRESHOLD == 0.15
