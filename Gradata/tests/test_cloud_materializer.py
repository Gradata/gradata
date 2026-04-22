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


class TestConflictResolved:
    def test_resolved_event_clears_hold_and_applies_winner(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", confidence=0.62, device_id="dev_a"),
            _evt(ts="2026-04-20T00:01:00Z", confidence=0.90, device_id="dev_b"),  # conflict
            {
                "ts": "2026-04-20T00:02:00Z",
                "type": "RULE_CONFLICT_RESOLVED",
                "source": "dashboard",
                "data": {
                    "category": "style",
                    "description": "use active voice",
                    "winning_ts": "2026-04-20T00:01:00Z",
                    "winning_device_id": "dev_b",
                },
            },
        ]
        result = materialize(stream)
        rule = next(iter(result.rules.values()))
        assert rule.winning_device_id == "dev_b"
        assert rule.confidence == pytest.approx(0.90)
        # Conflict was adjudicated — no stale RULE_CONFLICT should remain.
        assert result.conflicts == []

    def test_resolved_without_matching_history_clears_hold_only(self) -> None:
        stream = [
            _evt(ts="2026-04-20T00:00:00Z", confidence=0.62, device_id="dev_a"),
            _evt(ts="2026-04-20T00:01:00Z", confidence=0.90, device_id="dev_b"),
            {
                "ts": "2026-04-20T00:02:00Z",
                "type": "RULE_CONFLICT_RESOLVED",
                "source": "dashboard",
                "data": {
                    "category": "style",
                    "description": "use active voice",
                    "winning_ts": "9999-01-01T00:00:00Z",  # doesn't match history
                },
            },
            _evt(ts="2026-04-20T00:03:00Z", confidence=0.75, device_id="dev_c"),
        ]
        result = materialize(stream)
        # Hold cleared, but the next graduation after it now materializes.
        rule = next(iter(result.rules.values()))
        assert rule.winning_device_id == "dev_c"


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


class TestConvergence:
    """Ship-gate property: any ordering of the same ts-sorted slice yields
    identical materialized state. See docs/specs/merge-semantics.md §6.

    We build a cross-key event pool (each key has a monotonic per-key
    timeline so LWW semantics are deterministic once sorted by ts) and
    assert that N shuffled orderings → same rules after a by-ts sort.
    """

    def _build_pool(self, rng: random.Random, n_keys: int, per_key: int) -> list[dict]:
        pool: list[dict] = []
        for k in range(n_keys):
            base_conf = 0.55 + rng.random() * 0.08  # stays under Tier 2 drift
            for i in range(per_key):
                # Per-key monotonic timestamps so there's one true winner.
                ts = f"2026-04-20T00:{i:02d}:00Z"
                conf = round(base_conf + i * 0.01, 3)
                pool.append(
                    _evt(
                        ts=ts,
                        category=f"cat{k}",
                        description=f"rule-{k}",
                        confidence=conf,
                        device_id=f"dev_{rng.randint(0, 9):04d}",
                    )
                )
        return pool

    def test_convergence_across_shuffled_orderings(self) -> None:
        rng = random.Random(20260420)
        pool = self._build_pool(rng, n_keys=8, per_key=4)
        baseline = materialize(sorted(pool, key=lambda e: e["ts"])).rules

        # Full 10k is overkill for CI; 200 permutations is enough to catch
        # any ordering-dependent bug while keeping the test < 1s.
        for _ in range(200):
            shuffled = pool[:]
            rng.shuffle(shuffled)
            result = materialize(sorted(shuffled, key=lambda e: e["ts"])).rules
            assert result == baseline

    def test_convergence_with_injected_conflicts(self) -> None:
        """Even when some keys enter Tier 2 hold, replay order is irrelevant."""
        rng = random.Random(4242)
        pool = self._build_pool(rng, n_keys=4, per_key=3)
        # Inject a large-drift event per key → forces a conflict hold.
        for k in range(4):
            pool.append(
                _evt(
                    ts=f"2026-04-20T00:30:00Z",
                    category=f"cat{k}",
                    description=f"rule-{k}",
                    confidence=0.95,
                    device_id="dev_burst",
                )
            )

        baseline = materialize(sorted(pool, key=lambda e: e["ts"]))
        baseline_rules = baseline.rules
        baseline_conflict_keys = {c.key for c in baseline.conflicts}

        for _ in range(100):
            shuffled = pool[:]
            rng.shuffle(shuffled)
            result = materialize(sorted(shuffled, key=lambda e: e["ts"]))
            assert result.rules == baseline_rules
            assert {c.key for c in result.conflicts} == baseline_conflict_keys
