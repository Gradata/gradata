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
        import sys
        print(f"[rule_tracker] WARNING: Failed to log rule application for {rule_id}: {e}", file=sys.stderr)
        return None


def get_rule_stats(db_path: Path, rule_id: str) -> dict:
    """Aggregate stats for a rule from RULE_APPLICATION events.

    Returns dict with: total, accepted, misfired, contradicted,
    acceptance_rate, misfire_rate.
    """
    empty: dict = {
        "total": 0, "accepted": 0, "misfired": 0, "contradicted": 0,
        "acceptance_rate": 0.0, "misfire_rate": 0.0,
    }
    try:
        from gradata._events import query
        events = query(event_type="RULE_APPLICATION", limit=1000)
        matching = [e for e in events if e.get("data", {}).get("rule_id") == rule_id]

        if not matching:
            return empty

        total = len(matching)
        accepted = sum(1 for e in matching if e["data"].get("accepted"))
        misfired = sum(1 for e in matching if e["data"].get("misfired"))
        contradicted = sum(1 for e in matching if e["data"].get("contradicted"))

        return {
            "total": total,
            "accepted": accepted,
            "misfired": misfired,
            "contradicted": contradicted,
            "acceptance_rate": round(accepted / total, 4) if total else 0.0,
            "misfire_rate": round(misfired / total, 4) if total else 0.0,
        }
    except Exception:
        return empty


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
        import sys
        print(f"[rule_tracker] WARNING: get_session_applications failed: {e}", file=sys.stderr)
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
        import sys
        print(f"[rule_tracker] WARNING: get_rule_history failed for {rule_id}: {e}", file=sys.stderr)
        return []
