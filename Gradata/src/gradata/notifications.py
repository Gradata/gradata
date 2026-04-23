"""Notification system — human-readable event formatters for Gradata.

Turns raw EventBus payloads into user-facing messages. Registered
via ``brain.on_notification(callback)`` or used standalone.

Events handled:
  - correction.created   -> "Learned: {category} — {description}"
  - lesson.graduated     -> "Promoted: {category} INSTINCT -> PATTERN"
  - meta_rule.created    -> "Meta-rule: {principle}"
  - session.ended        -> "Session complete: {corrections} corrections, {promotions} promotions"
  - rule_scoped_out      -> "Scoped out: {category} (misfire rate too high in {domain})"
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from gradata.events_bus import EventBus


@dataclass
class Notification:
    """A formatted notification ready for display."""

    event: str
    message: str
    level: str  # "info", "success", "warning"
    data: dict[str, Any]


# ── Formatters ────────────────────────────────────────────────────────

# Truncation limits for notification message fields.
# Graduation is shorter (60) because the message already includes
# old_state, new_state, and confidence — more fields to fit.
_MAX_DESC = 80
_MAX_DESC_SHORT = 60


def _fmt_correction(payload: dict) -> Notification:
    cat = payload.get("category", "?")
    desc = payload.get("description", payload.get("detail", ""))[:_MAX_DESC]
    severity = payload.get("severity", "")
    msg = f"Learned: {cat}"
    if desc:
        msg += f" \u2014 {desc}"
    if severity:
        msg += f" ({severity})"
    return Notification("correction.created", msg, "info", payload)


def _fmt_graduation(payload: dict) -> Notification:
    cat = payload.get("category", "?")
    old = payload.get("old_state", "?")
    new = payload.get("new_state", "?")
    desc = payload.get("description", "")[:_MAX_DESC_SHORT]
    conf = payload.get("confidence", 0)
    msg = f"Promoted: {cat} {old} \u2192 {new} (conf={conf:.2f})"
    if desc:
        msg += f" \u2014 {desc}"
    return Notification("lesson.graduated", msg, "success", payload)


def _fmt_meta_rule(payload: dict) -> Notification:
    principle = payload.get("principle", payload.get("description", ""))[:_MAX_DESC]
    source_count = payload.get("source_count", "?")
    msg = f"Meta-rule created: {principle} (from {source_count} rules)"
    return Notification("meta_rule.created", msg, "success", payload)


def _fmt_session_ended(payload: dict) -> Notification:
    corrections = payload.get("corrections", 0)
    promotions = payload.get("promotions", 0)
    msg = f"Session complete: {corrections} corrections, {promotions} promotions"
    return Notification("session.ended", msg, "info", payload)


def _fmt_rule_scoped_out(payload: dict) -> Notification:
    cat = payload.get("lesson_category", "?")
    domain = payload.get("domain", "?")
    rate = payload.get("misfire_rate", 0)
    msg = f"Scoped out: {cat} in {domain} (misfire rate {rate:.0%})"
    return Notification("rule_scoped_out", msg, "warning", payload)


_FORMATTERS: dict[str, Callable[[dict], Notification]] = {
    "correction.created": _fmt_correction,
    "lesson.graduated": _fmt_graduation,
    "meta_rule.created": _fmt_meta_rule,
    "session.ended": _fmt_session_ended,
    "rule_scoped_out": _fmt_rule_scoped_out,
}


# ── Subscriber wiring ────────────────────────────────────────────────


def subscribe(bus: EventBus, callback: Callable[[Notification], None]) -> None:
    """Wire all notification formatters to the bus, routing to callback."""
    for event_name, formatter in _FORMATTERS.items():

        def _make_handler(fmt: Callable) -> Callable:
            def handler(payload: dict) -> None:
                try:
                    notif = fmt(payload or {})
                    callback(notif)
                except Exception:
                    _log.debug("Notification handler error", exc_info=True)

            return handler

        bus.on(event_name, _make_handler(formatter))


# ── Built-in output handlers ─────────────────────────────────────────

_COLORS = {
    "info": "\033[36m",  # cyan
    "success": "\033[32m",  # green
    "warning": "\033[33m",  # yellow
}
_RESET = "\033[0m"
_PREFIX = "\033[90m[gradata]\033[0m"  # gray prefix


def cli_handler(notif: Notification) -> None:
    """Print notification to stderr with ANSI colors."""
    color = _COLORS.get(notif.level, "")
    print(f"{_PREFIX} {color}{notif.message}{_RESET}", file=sys.stderr)


def collect_handler(target: list[Notification]) -> Callable[[Notification], None]:
    """Return a handler that appends notifications to a list (for testing/MCP)."""

    def handler(notif: Notification) -> None:
        target.append(notif)

    return handler
