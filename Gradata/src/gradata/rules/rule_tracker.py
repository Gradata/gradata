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
        logging.getLogger("gradata.rule_tracker").warning(
            "Failed to log rule application for %s: %s", rule_id, e
        )
        return None


VALID_SUPPRESSION_REASONS = {
    "relevance_threshold",
    "domain_disabled",
    "conflict",
    "assumption_invalid",
}


def log_suppression(
    rule_id: str,
    reason: str,
    relevance: float,
    competing_rule_ids: list[str] | None = None,
    ctx=None,
    session: int | None = None,
) -> None:
    """Emit a RULE_SUPPRESSION event when a rule is filtered out.

    Args:
        rule_id: The rule that was suppressed.
        reason: One of VALID_SUPPRESSION_REASONS.
        relevance: The relevance score at time of suppression.
        competing_rule_ids: Other rules that caused suppression (for conflicts).
        ctx: Optional BrainContext.
        session: Optional session number.
    """
    from gradata._events import emit

    data = {
        "rule_id": rule_id,
        "reason": reason,
        "relevance": round(relevance, 4),
        "competing_rules": competing_rule_ids or [],
    }
    tags = [f"rule:{rule_id}", f"suppression:{reason}"]
    emit("RULE_SUPPRESSION", source="rule_engine", data=data, tags=tags, session=session, ctx=ctx)


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
    """Recent RULE_APPLICATION events for a specific rule.

    Uses a direct SQL `tags_json LIKE` filter to avoid pulling 500 rows
    and filtering Python-side — the rule_id is stored as a `rule:<id>`
    tag at emit time, so we can push the selectivity into SQLite.
    """
    try:
        import contextlib
        import json
        import sqlite3

        from gradata import _paths as _p

        with contextlib.closing(sqlite3.connect(str(db_path or _p.DB_PATH))) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM events "
                "WHERE type = 'RULE_APPLICATION' AND tags_json LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (f'%"rule:{rule_id}"%', limit),
            ).fetchall()

        return [
            {
                "rule_id": rule_id,
                "session": r["session"],
                "accepted": (json.loads(r["data_json"]) if r["data_json"] else {}).get(
                    "accepted", False
                ),
                "misfired": (json.loads(r["data_json"]) if r["data_json"] else {}).get(
                    "misfired", False
                ),
                "contradicted": (json.loads(r["data_json"]) if r["data_json"] else {}).get(
                    "contradicted", False
                ),
                "ts": r["ts"],
            }
            for r in rows
        ]
    except Exception as e:
        logging.getLogger("gradata.rule_tracker").warning(
            "get_rule_history failed for %s: %s", rule_id, e
        )
        return []
