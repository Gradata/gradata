"""Recall coverage audit utilities.

// TODO: dashboard widget. Adjacent gradata-cloud dashboard components were
// not present in this checkout, so the cloud widget is intentionally skipped.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from gradata.hooks.adapters._base import AGENTS, adapter_config_path


def run_audit(brain_dir: str | Path) -> dict[str, Any]:
    root = Path(brain_dir)
    events = _load_recent_events(root / "events.jsonl")
    sessions_with_tool = _sessions_matching(events, _is_tool_call)
    sessions_with_recall = _sessions_matching(events, _is_recall_hit)
    coverage = (
        round((len(sessions_with_recall) / len(sessions_with_tool)) * 100, 2)
        if sessions_with_tool
        else 0.0
    )
    agents = _agent_hook_state()
    return {
        "brain_dir": str(root),
        "agents_configured": sum(1 for item in agents if item["configured"]),
        "agents": agents,
        "window_days": 7,
        "tool_call_sessions": len(sessions_with_tool),
        "recall_hit_sessions": len(sessions_with_recall),
        "recall_coverage_pct": coverage,
        "events_tool_calls": sum(1 for event in events if _is_tool_call(event)),
        "events_recall_hits": sum(1 for event in events if _is_recall_hit(event)),
        "decay_rules_injected": _decay_rules_injected(root),
        "invalid_meta_sources": _invalid_meta_sources(root),
    }


def format_audit_text(report: dict[str, Any]) -> str:
    lines = [
        f"Recall coverage: {report['recall_coverage_pct']}%",
        f"Agents configured: {report['agents_configured']}",
        (
            "Sessions: "
            f"{report['recall_hit_sessions']} recall-hit / "
            f"{report['tool_call_sessions']} tool-call in last {report['window_days']} days"
        ),
    ]
    if report["decay_rules_injected"]:
        lines.append(f"WARN: {len(report['decay_rules_injected'])} decayed rules appear injectable")
    if report["invalid_meta_sources"]:
        lines.append(
            f"WARN: {len(report['invalid_meta_sources'])} meta-rules have non-injectable sources"
        )
    return "\n".join(lines)


def _load_recent_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(UTC) - timedelta(days=7)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = _event_time(event)
        if ts is None or ts >= cutoff:
            events.append(event)
    return events


def _event_time(event: dict[str, Any]) -> datetime | None:
    raw = str(event.get("ts") or event.get("timestamp") or event.get("time") or "")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _session_id(event: dict[str, Any]) -> str:
    raw_data = event.get("data")
    data = raw_data if isinstance(raw_data, dict) else {}
    return str(event.get("session") or event.get("session_id") or data.get("session_id") or "0")


def _sessions_matching(events: list[dict[str, Any]], predicate) -> set[str]:
    return {_session_id(event) for event in events if predicate(event)}


def _is_tool_call(event: dict[str, Any]) -> bool:
    typ = str(event.get("type", "")).lower()
    source = str(event.get("source", "")).lower()
    return "tool" in typ or "tool" in source


def _is_recall_hit(event: dict[str, Any]) -> bool:
    typ = str(event.get("type", "")).lower()
    source = str(event.get("source", "")).lower()
    raw_data = event.get("data")
    data = raw_data if isinstance(raw_data, dict) else {}
    return (
        "recall" in typ
        or "rules.injected" in typ
        or "recall" in source
        or bool(data.get("recall_hits"))
        or bool(data.get("rules"))
    )


def _agent_hook_state() -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for agent in AGENTS:
        path = adapter_config_path(agent)
        configured = False
        if path.exists():
            configured = "gradata" in path.read_text(encoding="utf-8", errors="replace").lower()
        states.append({"agent": agent, "config_path": str(path), "configured": configured})
    return states


def _decay_rules_injected(root: Path) -> list[str]:
    lessons = root / "lessons.md"
    if not lessons.exists():
        return []
    lines = lessons.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line for line in lines if "DECAY" in line.upper() and "KILLED" not in line.upper()]


def _invalid_meta_sources(root: Path) -> list[dict[str, str]]:
    try:
        from gradata.enhancements.meta_rules import INJECTABLE_META_SOURCES
        from gradata.enhancements.meta_rules_storage import load_meta_rules
    except ImportError:
        return []
    db_path = root / "system.db"
    if not db_path.exists():
        return []
    try:
        metas = load_meta_rules(db_path)
    except Exception:
        return []
    invalid = []
    for meta in metas:
        source = getattr(meta, "source", "deterministic")
        if source not in INJECTABLE_META_SOURCES:
            invalid.append({"id": getattr(meta, "id", ""), "source": source})
    return invalid
