"""Tests for the notification system (notifications.py + brain.on_notification)."""

from __future__ import annotations

from gradata.brain import Brain
from gradata.events_bus import EventBus
from gradata.notifications import (
    Notification,
    _fmt_correction,
    _fmt_graduation,
    _fmt_meta_rule,
    _fmt_rule_scoped_out,
    _fmt_session_ended,
    collect_handler,
    subscribe,
)

# ── Formatter unit tests ──────────────────────────────────────────────


def test_fmt_correction_basic():
    n = _fmt_correction({"category": "TONE", "description": "avoid jargon", "severity": "moderate"})
    assert n.event == "correction.created"
    assert n.level == "info"
    assert "TONE" in n.message
    assert "avoid jargon" in n.message
    assert "moderate" in n.message


def test_fmt_correction_empty_payload():
    n = _fmt_correction({})
    assert n.event == "correction.created"
    assert "?" in n.message


def test_fmt_graduation():
    n = _fmt_graduation(
        {
            "category": "DRAFTING",
            "old_state": "INSTINCT",
            "new_state": "PATTERN",
            "description": "use colons",
            "confidence": 0.72,
        }
    )
    assert n.event == "lesson.graduated"
    assert n.level == "success"
    assert "DRAFTING" in n.message
    assert "INSTINCT" in n.message
    assert "PATTERN" in n.message
    assert "0.72" in n.message


def test_fmt_meta_rule():
    n = _fmt_meta_rule({"principle": "Always verify data", "source_count": 3})
    assert "Meta-rule" in n.message
    assert "3 rules" in n.message


def test_fmt_session_ended():
    n = _fmt_session_ended({"corrections": 5, "promotions": 2})
    assert "5 corrections" in n.message
    assert "2 promotions" in n.message


def test_fmt_rule_scoped_out():
    n = _fmt_rule_scoped_out(
        {
            "lesson_category": "CODE",
            "domain": "EMAIL",
            "misfire_rate": 0.8,
        }
    )
    assert n.level == "warning"
    assert "CODE" in n.message
    assert "EMAIL" in n.message


# ── Subscriber wiring tests ──────────────────────────────────────────


def test_subscribe_routes_events():
    bus = EventBus()
    collected: list[Notification] = []
    subscribe(bus, collect_handler(collected))

    bus.emit("correction.created", {"category": "TONE", "description": "fix"})
    bus.emit(
        "lesson.graduated",
        {
            "category": "X",
            "old_state": "I",
            "new_state": "P",
            "confidence": 0.7,
        },
    )

    assert len(collected) == 2
    assert collected[0].event == "correction.created"
    assert collected[1].event == "lesson.graduated"


def test_subscribe_ignores_unknown_events():
    bus = EventBus()
    collected: list[Notification] = []
    subscribe(bus, collect_handler(collected))

    bus.emit("unknown.event", {"data": 1})
    assert len(collected) == 0


def test_subscribe_survives_bad_payload():
    bus = EventBus()
    collected: list[Notification] = []
    subscribe(bus, collect_handler(collected))

    bus.emit("correction.created", None)
    assert len(collected) == 1  # formatter handles None -> {}


# ── Brain integration test ───────────────────────────────────────────


def test_brain_on_notification(tmp_path):
    brain = Brain(str(tmp_path))
    collected: list[Notification] = []
    brain.on_notification(collect_handler(collected))

    # Emit a correction event through the bus
    brain.bus.emit("correction.created", {"category": "TONE", "description": "test"})

    assert len(collected) == 1
    assert "TONE" in collected[0].message


def test_brain_on_notification_default_cli(tmp_path, capsys):
    """on_notification() with no args uses CLI handler (stderr)."""
    brain = Brain(str(tmp_path))
    brain.on_notification()

    brain.bus.emit(
        "lesson.graduated",
        {
            "category": "CODE",
            "old_state": "INSTINCT",
            "new_state": "PATTERN",
            "description": "test graduation",
            "confidence": 0.75,
        },
    )

    captured = capsys.readouterr()
    assert "CODE" in captured.err
    assert "PATTERN" in captured.err


def test_brain_on_notification_with_correction(tmp_path):
    """Full integration: brain.correct() -> bus -> notification."""
    brain = Brain(str(tmp_path))
    collected: list[Notification] = []
    brain.on_notification(collect_handler(collected))

    brain.correct("bad text", "good text", category="TONE", session=1)

    # correction.created should fire
    correction_notifs = [n for n in collected if n.event == "correction.created"]
    assert len(correction_notifs) >= 1
