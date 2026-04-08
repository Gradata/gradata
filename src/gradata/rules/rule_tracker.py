"""
Rule Application Tracker — records outcomes via the event system.
=================================================================
Event-sourced: rule applications are RULE_APPLICATION events in the
events table, not a separate domain table. This aligns with the brain's
append-only event architecture.

Each time the rule engine surfaces a rule, the caller logs it here.
Aggregate stats are queried from events for the self-improvement pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gradata._scope import RuleScope, scope_to_dict

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_application(
    rule_id: str,
    session: int,
    accepted: bool,
    misfired: bool = False,
    contradicted: bool = False,
    scope: RuleScope | None = None,
    source: str = "rule_engine",
) -> dict | None:
    """Emit a RULE_APPLICATION event through the standard event pipeline.

    Returns the event dict on success, None on failure.
    """
    data = {
        "rule_id": rule_id,
        "accepted": accepted,
        "misfired": misfired,
        "contradicted": contradicted,
    }
    if scope is not None:
        data["scope"] = scope_to_dict(scope)

    tags = [f"rule:{rule_id}"]
    if accepted:
        tags.append("outcome:accepted")
    if misfired:
        tags.append("outcome:misfired")
    if contradicted:
        tags.append("outcome:contradicted")

    try:
        from gradata._events import emit
        return emit("RULE_APPLICATION", source, data, tags, session)
    except Exception as e:
        logging.getLogger("gradata.rule_tracker").warning("Failed to log rule application for %s: %s", rule_id, e)
        return None



def get_session_applications(db_path: Path, session: int) -> list[dict]:
    """All RULE_APPLICATION events for a given session."""
    try:
        from gradata._events import query
        events = query(event_type="RULE_APPLICATION", session=session, limit=500)
        return [
            {
                "rule_id": e["data"].get("rule_id", ""),
                "session": e.get("session"),
                "accepted": e["data"].get("accepted", False),
                "misfired": e["data"].get("misfired", False),
                "contradicted": e["data"].get("contradicted", False),
                "scope": e["data"].get("scope"),
                "ts": e.get("ts"),
            }
            for e in events
        ]
    except Exception as e:
        logging.getLogger("gradata.rule_tracker").warning("get_session_applications failed: %s", e)
        return []


@dataclass
class RuleApplication:
    """Typed record of a single rule application event."""
    rule_id: str
    session: int | None = None
    accepted: bool = False
    misfired: bool = False
    contradicted: bool = False
    scope: str = ""
    ts: str = ""


def get_rule_history(db_path: Path, rule_id: str, limit: int = 20) -> list[dict]:
    """Recent RULE_APPLICATION events for a specific rule."""
    try:
        from gradata._events import query
        events = query(event_type="RULE_APPLICATION", limit=500)
        matching = [e for e in events if e.get("data", {}).get("rule_id") == rule_id]
        return [
            {
                "rule_id": e["data"].get("rule_id", ""),
                "session": e.get("session"),
                "accepted": e["data"].get("accepted", False),
                "misfired": e["data"].get("misfired", False),
                "contradicted": e["data"].get("contradicted", False),
                "ts": e.get("ts"),
            }
            for e in matching[:limit]
        ]
    except Exception as e:
        logging.getLogger("gradata.rule_tracker").warning("get_rule_history failed for %s: %s", rule_id, e)
        return []