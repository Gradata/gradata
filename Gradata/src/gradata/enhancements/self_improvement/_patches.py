"""
Rule-patch telemetry — tracks behavioral compliance before and after rule rewrites.

When brain.patch_rule() applies a rewrite, observe_patch() emits a
``rule_patch_observed`` event capturing:

    - old_rule_text / new_rule_text / applied_at
    - observed_compliance_before: RULE_FAILURE count for this rule in the
      last 3 sessions before the patch
    - observed_compliance_after_3_sessions: None at apply time; filled
      by resolve_patch_compliance() three sessions later

The acceptance rate (% of patches where after < before) is the headline
metric for whether self-healing rule rewrites actually change agent behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.brain import Brain

_LOOKBACK_SESSIONS = 3
_MAX_RULE_TEXT = 500
_PATCH_TAG = "patch_telemetry"


def _count_failures_for_rule(
    brain: Brain,
    category: str,
    rule_description: str,
    lookback_sessions: int = _LOOKBACK_SESSIONS,
) -> int:
    """Count RULE_FAILURE events matching this specific rule in the last N sessions."""
    try:
        events = brain.query_events(
            event_type="RULE_FAILURE",
            last_n_sessions=lookback_sessions,
            limit=500,
        )
    except Exception:
        return 0

    cat = category.upper()
    rule_desc = rule_description.strip()
    return sum(
        1
        for e in events
        if (
            (e.get("data", {}).get("failed_rule_category") or "").upper() == cat
            and (e.get("data", {}).get("failed_rule_description") or "").strip() == rule_desc
        )
    )


def _get_current_session(brain: Brain) -> int:
    """Return the highest session number seen in recent events, or 1."""
    try:
        events = brain.query_events(limit=10)
        if events:
            return max((e.get("session") or 0) for e in events)
    except Exception:
        pass
    return 1


def observe_patch(
    brain: Brain,
    category: str,
    old_description: str,
    new_description: str,
) -> dict:
    """Emit a rule_patch_observed event capturing pre-patch compliance.

    Called immediately after brain.patch_rule() succeeds. Records the
    RULE_FAILURE count for the old rule text over the last 3 sessions so
    we can compare against the post-patch count via resolve_patch_compliance().

    Oscillation guard: if applying this patch would complete an A→B→A
    cycle (we're patching back to a text we patched AWAY from recently),
    no `rule_patch_observed` event is emitted. Instead we emit a
    `rule_patch_cycle_detected` event and return that. Caller can detect
    the abort via the event type field.

    Args:
        brain: Brain instance — used to query events and emit.
        category: Rule category (e.g. "TONE").
        old_description: Rule text being replaced.
        new_description: Replacement rule text.

    Returns:
        The emitted event dict. May be a `rule_patch_observed` (normal path)
        OR a `rule_patch_cycle_detected` (cycle aborted) event. Empty dict
        on emit failure. Never raises.
    """
    # Cycle check BEFORE recording the patch. If we'd be completing an
    # A→B then proposed B→A cycle, bail and emit a cycle-detected event
    # so the dashboard can show the lock state and the patcher can skip
    # this lesson for N sessions.
    from gradata.enhancements.self_improvement._oscillation_guard import (
        detect_cycle,
        emit_cycle_detected,
    )

    cycle = detect_cycle(brain, category, old_description, new_description)
    if cycle is not None:
        return emit_cycle_detected(brain, category, cycle)

    compliance_before = _count_failures_for_rule(brain, category, old_description)

    try:
        event = brain.emit(
            "rule_patch_observed",
            "_patches.observe_patch",
            {
                "category": category.upper(),
                "old_rule_text": old_description[:_MAX_RULE_TEXT],
                "new_rule_text": new_description[:_MAX_RULE_TEXT],
                "applied_at": datetime.now(UTC).isoformat(),
                "observed_compliance_before": compliance_before,
                "observed_compliance_after_3_sessions": None,
            },
            [f"category:{category}", "self_healing", _PATCH_TAG],
        )
        return event if isinstance(event, dict) else {}
    except Exception:
        return {}


def resolve_patch_compliance(
    brain: Brain,
    min_session_gap: int = _LOOKBACK_SESSIONS,
) -> list[dict]:
    """Fill in observed_compliance_after_3_sessions for pending observations.

    Finds rule_patch_observed events where the after value is still None
    and the patch was applied at least min_session_gap sessions ago. For
    each, measures current RULE_FAILURE count for the new rule text and
    emits a new resolved event.

    Returns:
        List of resolution receipts — one per observation resolved this call.
    """
    try:
        pending_events = brain.query_events(event_type="rule_patch_observed", limit=200)
    except Exception:
        return []

    current_session = _get_current_session(brain)
    updates: list[dict] = []

    for ev in pending_events:
        data = ev.get("data", {})
        if data.get("observed_compliance_after_3_sessions") is not None:
            continue

        patch_session = ev.get("session") or 0
        if current_session - patch_session < min_session_gap:
            continue

        category = data.get("category", "")
        new_rule_text = data.get("new_rule_text", "")

        compliance_after = _count_failures_for_rule(brain, category, new_rule_text)
        compliance_before = data.get("observed_compliance_before") or 0
        improved = compliance_after < compliance_before

        try:
            updated = brain.emit(
                "rule_patch_observed",
                "_patches.resolve_patch_compliance",
                {
                    **data,
                    "observed_compliance_after_3_sessions": compliance_after,
                    "compliance_improved": improved,
                    "resolution_session": current_session,
                    "original_event_id": ev.get("id"),
                },
                [f"category:{category}", "self_healing", _PATCH_TAG, "resolved"],
            )
            updates.append(
                {
                    "category": category,
                    "compliance_before": compliance_before,
                    "compliance_after": compliance_after,
                    "improved": improved,
                    "event": updated if isinstance(updated, dict) else {},
                }
            )
        except Exception:
            continue

    return updates


def patch_acceptance_rate(brain: Brain) -> dict:
    """Compute the acceptance rate from all resolved rule_patch_observed events.

    "Accepted" = compliance improved (compliance_after < compliance_before).

    Returns:
        {
            "total_observed": int,
            "total_resolved": int,
            "accepted": int,
            "rejected": int,
            "acceptance_rate": float,   # 0.0 if no resolved observations
            "pending": int,
        }
    """
    try:
        events = brain.query_events(event_type="rule_patch_observed", limit=500)
    except Exception:
        events = []

    resolved = [
        e
        for e in events
        if e.get("data", {}).get("observed_compliance_after_3_sessions") is not None
    ]
    pending = len(events) - len(resolved)
    accepted = sum(1 for e in resolved if e.get("data", {}).get("compliance_improved", False))
    rejected = len(resolved) - accepted
    rate = accepted / len(resolved) if resolved else 0.0

    return {
        "total_observed": len(events),
        "total_resolved": len(resolved),
        "accepted": accepted,
        "rejected": rejected,
        "acceptance_rate": round(rate, 3),
        "pending": pending,
    }
