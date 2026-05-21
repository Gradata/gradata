"""Tests for the oscillation guard on self-healing rule patches.

Without these tests guarding the behavior, a poorly-tuned compliance
scorer can ping-pong the same lesson between two phrasings forever.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

# _FakeBrain doesn't implement the full Brain protocol but provides the
# subset detect_cycle / observe_patch actually use. Tell pyright to chill.
# pyright: reportArgumentType=false
from gradata.enhancements.self_improvement._oscillation_guard import (
    _normalize,
    detect_cycle,
    emit_cycle_detected,
)
from gradata.enhancements.self_improvement._patches import observe_patch


# ---------------------------------------------------------------------------
# Test fake brain
# ---------------------------------------------------------------------------


class _FakeBrain:
    """Minimal in-memory brain stand-in for cycle-guard testing.

    Stores emitted events in a list. `query_events` filters by event_type.
    """

    def __init__(self, events: list[dict] | None = None) -> None:
        self._events: list[dict] = list(events or [])
        self._next_id = len(self._events)

    def query_events(
        self,
        event_type: str | None = None,
        last_n_sessions: int | None = None,
        limit: int = 500,
    ) -> list[dict]:
        out = self._events
        if event_type is not None:
            out = [e for e in out if e.get("event_type") == event_type]
        return out[:limit]

    def emit(
        self,
        event_type: str,
        source: str,
        data: dict,
        tags: list[str] | None = None,
    ) -> dict:
        self._next_id += 1
        ev = {
            "id": f"ev_{self._next_id}",
            "event_type": event_type,
            "source": source,
            "data": data,
            "tags": tags or [],
            "session": 1,
        }
        self._events.append(ev)
        return ev


def _patch_event(old_text: str, new_text: str, category: str = "TONE", applied_at: str | None = None) -> dict:
    return {
        "id": f"patch_{old_text[:5]}_{new_text[:5]}",
        "event_type": "rule_patch_observed",
        "data": {
            "category": category,
            "old_rule_text": old_text,
            "new_rule_text": new_text,
            "applied_at": applied_at or datetime.now(UTC).isoformat(),
            "observed_compliance_before": 2,
            "observed_compliance_after_3_sessions": None,
        },
        "session": 1,
    }


# ---------------------------------------------------------------------------
# detect_cycle()
# ---------------------------------------------------------------------------


def test_no_history_returns_none() -> None:
    brain = _FakeBrain([])
    result = detect_cycle(brain, "TONE", "A", "B")
    assert result is None


def test_unrelated_patches_return_none() -> None:
    brain = _FakeBrain([
        _patch_event("X", "Y"),
        _patch_event("Y", "Z"),
    ])
    # Proposing X → W is not a cycle.
    result = detect_cycle(brain, "TONE", "X", "W")
    assert result is None


def test_direct_cycle_detected() -> None:
    """A → B was patched recently. Proposing B → A must be flagged."""
    brain = _FakeBrain([_patch_event("A", "B")])
    result = detect_cycle(brain, "TONE", "B", "A")
    assert result is not None
    assert result["reason"] == "direct_cycle"
    assert result["lock_sessions"] > 0
    assert result["old_text"] == "B"
    assert result["new_text"] == "A"


def test_self_identity_detected() -> None:
    """Patching X → X is meaningless; always flag as a cycle."""
    brain = _FakeBrain([])
    result = detect_cycle(brain, "TONE", "X", "X")
    assert result is not None
    assert result["reason"] == "self_identity"


def test_category_isolation() -> None:
    """A cycle in TONE must not affect URL-category patches."""
    brain = _FakeBrain([_patch_event("A", "B", category="TONE")])
    # Same texts, different category → not a cycle.
    result = detect_cycle(brain, "URL", "B", "A")
    assert result is None


def test_whitespace_normalization() -> None:
    """Whitespace/case differences must not break cycle detection."""
    brain = _FakeBrain([
        _patch_event(
            "  Don't give prospects a WAY OUT",
            "When prospect EXPRESSED interest, close immediately",
        ),
    ])
    # Same texts with different casing/whitespace must still trip the guard.
    result = detect_cycle(
        brain,
        "TONE",
        "when prospect expressed   interest, close immediately",
        "don't give prospects a way out",
    )
    assert result is not None
    assert result["reason"] == "direct_cycle"


def test_old_patch_outside_lookback() -> None:
    """A patch older than the lookback window must NOT trip the guard."""
    very_old = "2020-01-01T00:00:00+00:00"
    brain = _FakeBrain([_patch_event("A", "B", applied_at=very_old)])
    result = detect_cycle(brain, "TONE", "B", "A", lookback_days=7)
    assert result is None


# ---------------------------------------------------------------------------
# emit_cycle_detected()
# ---------------------------------------------------------------------------


def test_emit_cycle_detected_records_event() -> None:
    brain = _FakeBrain()
    cycle = {
        "matched_event_id": "patch_X_Y",
        "matched_applied_at": datetime.now(UTC).isoformat(),
        "cycle_length": 1,
        "lock_sessions": 10,
        "old_text": "B",
        "new_text": "A",
        "reason": "direct_cycle",
    }
    event = emit_cycle_detected(brain, "TONE", cycle)
    assert event["event_type"] == "rule_patch_cycle_detected"
    assert event["data"]["lock_sessions"] == 10
    assert event["data"]["reason"] == "direct_cycle"
    assert event["data"]["category"] == "TONE"
    # The brain stored it.
    assert any(
        e.get("event_type") == "rule_patch_cycle_detected" for e in brain.query_events()
    )


# ---------------------------------------------------------------------------
# observe_patch() integration — the customer-visible behavior
# ---------------------------------------------------------------------------


def test_observe_patch_normal_path_emits_observed() -> None:
    brain = _FakeBrain()
    event = observe_patch(brain, "TONE", "A", "B")
    assert event["event_type"] == "rule_patch_observed"


def test_observe_patch_blocks_direct_cycle() -> None:
    """Real-world bug: lesson 911130b3 oscillated A→B→A→B 5×.

    After this fix, the 2nd patch back to A must emit
    `rule_patch_cycle_detected` instead of `rule_patch_observed`, so no
    fake "100% reduction" gets recorded and the dashboard shows a lock
    badge instead of another rollback entry.
    """
    brain = _FakeBrain()
    # First patch A → B succeeds normally.
    first = observe_patch(brain, "TONE", "A", "B")
    assert first["event_type"] == "rule_patch_observed"
    # Second patch attempts B → A — must be blocked as a direct cycle.
    second = observe_patch(brain, "TONE", "B", "A")
    assert second["event_type"] == "rule_patch_cycle_detected"
    assert second["data"]["old_rule_text"] == "B"
    assert second["data"]["new_rule_text"] == "A"


def test_observe_patch_allows_genuine_new_text() -> None:
    """A → B then C → D is two unrelated patches, not a cycle."""
    brain = _FakeBrain()
    first = observe_patch(brain, "TONE", "A", "B")
    second = observe_patch(brain, "TONE", "C", "D")
    assert first["event_type"] == "rule_patch_observed"
    assert second["event_type"] == "rule_patch_observed"


def test_normalize_helper() -> None:
    assert _normalize("  Hello   WORLD  ") == "hello world"
    assert _normalize("") == ""
    assert _normalize(None) == ""  # type: ignore[arg-type]
