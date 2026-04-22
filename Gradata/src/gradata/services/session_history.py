"""
Session History — Rule Effectiveness Tracking.
================================================
Tracks which rules were injected during a session and whether
corrections occurred against them. A rule that was injected but
never triggered a correction is considered *effective* (it
prevented the mistake). A rule that was corrected is *not effective*
(the agent still made the mistake despite the rule).

Usage:
    from gradata.services.session_history import SessionHistory

    sh = SessionHistory()
    sh.subscribe_to_bus(bus)  # auto-wires to event bus

    # ``gradata.integrations.session_history`` still resolves via a
    # deprecation shim through v0.9.0 but should not be used in new code.
"""

from __future__ import annotations


class SessionHistory:
    """Track injected rules and corrections within a single session."""

    def __init__(self) -> None:
        self.injected_this_session: set[str] = set()
        self.corrected_this_session: set[str] = set()

    # ── Event handlers ───────────────────────────────────────────

    def on_rules_injected(self, payload: dict) -> None:
        """Record rule IDs from a rules.injected event."""
        for rule in payload.get("rules", []):
            rule_id = rule.get("id")
            if rule_id:
                self.injected_this_session.add(rule_id)

    def on_correction_created(self, payload: dict) -> None:
        """Mark a rule as corrected if it was injected this session."""
        lesson = payload.get("lesson", {})
        rule_id = lesson.get("rule_id")
        if rule_id and rule_id in self.injected_this_session:
            self.corrected_this_session.add(rule_id)

    def on_session_ended(self, payload: dict) -> None:
        """Attach effectiveness scores to the session-end payload and reset.

        Side effect: mutates ``payload`` in place by adding the
        ``rule_effectiveness`` key. Callers who plan to reuse ``payload``
        elsewhere after this handler runs should pass a shallow copy.
        The in-place mutation is intentional so the bus broadcast sees
        the enriched payload without an extra round-trip.

        Resets session state after computing effectiveness so the next
        session starts clean (prevents cross-session state leakage).
        """
        payload["rule_effectiveness"] = self.compute_effectiveness()
        self.reset()

    # ── Public API ───────────────────────────────────────────────

    def compute_effectiveness(self) -> dict[str, dict]:
        """Return per-rule effectiveness scores.

        Returns:
            Dict mapping rule_id -> {"effective": bool, "corrected": bool}.
            A rule is effective if it was NOT corrected during the session.
        """
        if not self.injected_this_session:
            return {}
        return {
            rule_id: {
                "effective": rule_id not in self.corrected_this_session,
                "corrected": rule_id in self.corrected_this_session,
            }
            for rule_id in self.injected_this_session
        }

    def reset(self) -> None:
        """Clear session state."""
        self.injected_this_session.clear()
        self.corrected_this_session.clear()

    def subscribe_to_bus(self, bus) -> None:
        """Register event handlers on an EventBus instance."""
        bus.on("rules.injected", self.on_rules_injected)
        bus.on("correction.created", self.on_correction_created)
        bus.on("session.ended", self.on_session_ended)
