"""
Oscillation guard for self-healing rule rewrites.

When `_patches.observe_patch` is called, this module checks the recent rule
history for a cycle: a previous patch where we wrote *away from* the text
we're now writing *back to*. If detected, signal "abort + lock" so the
patcher skips the rewrite and emits a `rule_patch_cycle_detected` event
instead.

Without this guard, a poorly-tuned compliance scorer can ping-pong the
same lesson between two phrasings forever (each rewrite gets fresh "100%
reduction" credit because the new text has zero observations yet). Real
example from a production brain 2026-05-21:
    lesson 911130b3 oscillated A→B→A→B→A→B across 5 rollbacks in 20 days
    with no actual behavioral improvement.

Design:
    - Cycle = the proposed `new_text` MATCHES a recent `old_text` (i.e. we
      patched away from it before and now want to go back).
    - Lookback: 30 days OR N patches whichever is smaller (default N=5).
    - On detection: emit `rule_patch_cycle_detected` event with both
      texts, the chain of patches, and the recommended lock-until session.
    - Lock duration: 10 sessions (configurable via env).

The guard is intentionally conservative — it only fires on DIRECT cycles
(A→B then proposed B→A). Higher-order cycles (A→B→C→A) are not detected;
those are rare and false-positive risk on a sensitive guard kills more
value than it protects.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.brain import Brain


# Default lock duration (in sessions) after a cycle is detected.
_DEFAULT_LOCK_SESSIONS = 10

# Default lookback window for cycle detection.
_DEFAULT_LOOKBACK_DAYS = 30
_DEFAULT_LOOKBACK_PATCHES = 5


def _normalize(text: str) -> str:
    """Whitespace-collapse for stable comparison."""
    return " ".join((text or "").split()).lower()


def _lock_sessions() -> int:
    """Read lock duration from env (`GRADATA_OSCILLATION_LOCK_SESSIONS`)."""
    raw = os.environ.get("GRADATA_OSCILLATION_LOCK_SESSIONS")
    if raw is None:
        return _DEFAULT_LOCK_SESSIONS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_LOCK_SESSIONS
    return max(1, value)


def detect_cycle(
    brain: Brain,
    category: str,
    old_description: str,
    new_description: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    lookback_patches: int = _DEFAULT_LOOKBACK_PATCHES,
) -> dict | None:
    """Check whether applying the proposed patch would complete an A→B→A cycle.

    Args:
        brain: Brain instance — used to query past rule_patch_observed events.
        category: Rule category (e.g. "TONE"). Cycles only apply within a category.
        old_description: The current rule text being replaced.
        new_description: The proposed replacement text.
        lookback_days: Maximum age (in days) of prior patches to consider.
        lookback_patches: Maximum number of prior patches to consider.

    Returns:
        A dict describing the detected cycle:
            {
                "matched_event_id": str,        # the prior patch that wrote AWAY from new_description
                "matched_applied_at": str,      # ISO timestamp
                "cycle_length": int,            # how many patches between the prior write-away and now
                "lock_sessions": int,           # recommended lock duration
                "old_text": str,
                "new_text": str,
            }
        Or None if no cycle is detected (safe to apply patch).
    """
    proposed_old = _normalize(old_description)
    proposed_new = _normalize(new_description)

    # Trivial guard: never patch a rule to itself.
    if proposed_old == proposed_new:
        return {
            "matched_event_id": None,
            "matched_applied_at": None,
            "cycle_length": 0,
            "lock_sessions": _lock_sessions(),
            "old_text": old_description,
            "new_text": new_description,
            "reason": "self_identity",
        }

    cat = (category or "").upper()
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    try:
        events = brain.query_events(
            event_type="rule_patch_observed",
            limit=200,
        )
    except Exception:
        return None  # Fail open — never block patches on a query failure.

    relevant = []
    for ev in events:
        data = ev.get("data", {}) or {}
        if (data.get("category") or "").upper() != cat:
            continue
        applied_at_raw = data.get("applied_at")
        if applied_at_raw:
            try:
                applied_at = datetime.fromisoformat(applied_at_raw.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if applied_at < cutoff:
                continue
        relevant.append(ev)

    # Newest first, capped by lookback_patches.
    relevant.sort(
        key=lambda e: (e.get("data", {}) or {}).get("applied_at") or "",
        reverse=True,
    )
    relevant = relevant[:lookback_patches]

    for idx, ev in enumerate(relevant):
        data = ev.get("data", {}) or {}
        prior_old = _normalize(data.get("old_rule_text", ""))
        prior_new = _normalize(data.get("new_rule_text", ""))

        # Direct A→B then proposed B→A cycle:
        #   prior patch went FROM prior_old TO prior_new (= proposed_old).
        #   now we want to go FROM proposed_old BACK TO prior_old (= proposed_new).
        if prior_new == proposed_old and prior_old == proposed_new:
            return {
                "matched_event_id": ev.get("id"),
                "matched_applied_at": data.get("applied_at"),
                "cycle_length": idx + 1,
                "lock_sessions": _lock_sessions(),
                "old_text": old_description,
                "new_text": new_description,
                "reason": "direct_cycle",
            }

    return None


def emit_cycle_detected(brain: Brain, category: str, cycle: dict) -> dict:
    """Emit a `rule_patch_cycle_detected` event so the cycle is auditable.

    Returns the emitted event dict, or {} on failure (never raises).
    """
    try:
        event = brain.emit(
            "rule_patch_cycle_detected",
            "_oscillation_guard.detect_cycle",
            {
                "category": (category or "").upper(),
                "old_rule_text": (cycle.get("old_text") or "")[:500],
                "new_rule_text": (cycle.get("new_text") or "")[:500],
                "matched_event_id": cycle.get("matched_event_id"),
                "matched_applied_at": cycle.get("matched_applied_at"),
                "cycle_length": cycle.get("cycle_length", 0),
                "lock_sessions": cycle.get("lock_sessions", _DEFAULT_LOCK_SESSIONS),
                "reason": cycle.get("reason", "direct_cycle"),
                "detected_at": datetime.now(UTC).isoformat(),
            },
            [f"category:{category}", "self_healing", "cycle_detected", "patch_blocked"],
        )
        return event if isinstance(event, dict) else {}
    except Exception:
        return {}
