"""
Rule Inspection API — standalone functions for introspecting brain rules.
=========================================================================
SDK LAYER: Layer 0 (no Brain dependency). All functions take primitive
paths (db_path, lessons_path) so they can be used without instantiating
a Brain object. Brain gets thin 1-2 line wrappers.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from gradata._types import ELIGIBLE_STATES, Lesson, LessonState
from gradata.rules.rule_engine import _make_rule_id

_log = logging.getLogger(__name__)


def _load_lessons_from_path(lessons_path: Path | str) -> list[Lesson]:
    """Read and parse lessons.md from a file path."""
    from gradata.enhancements.self_improvement import parse_lessons

    p = Path(lessons_path)
    if not p.is_file():
        return []
    return parse_lessons(p.read_text(encoding="utf-8"))


def _lesson_to_dict(lesson: Lesson) -> dict:
    """Convert a Lesson dataclass to a serializable dict with a stable ID."""
    d = {
        "id": _make_rule_id(lesson),
        "date": lesson.date,
        "state": lesson.state.value,
        "confidence": lesson.confidence,
        "category": lesson.category,
        "description": lesson.description,
        "root_cause": lesson.root_cause,
        "fire_count": lesson.fire_count,
        "sessions_since_fire": lesson.sessions_since_fire,
        "misfire_count": lesson.misfire_count,
        "correction_event_ids": lesson.correction_event_ids,
    }
    if hasattr(lesson, "metadata") and lesson.metadata is not None:
        d["metadata"] = lesson.metadata.to_dict() if hasattr(lesson.metadata, "to_dict") else lesson.metadata
    return d


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def list_rules(
    *,
    db_path: Path | str,
    lessons_path: Path | str,
    include_all: bool = False,
    category: str | None = None,
) -> list[dict]:
    """List brain rules from lessons.md.

    Args:
        db_path: Path to system.db (reserved for future enrichment).
        lessons_path: Path to lessons.md file.
        include_all: If True, return all lessons regardless of state.
            Default returns only PATTERN + RULE (ELIGIBLE_STATES).
        category: Optional category filter (e.g. "DRAFTING").

    Returns:
        List of rule dicts sorted by confidence descending.
    """
    lessons = _load_lessons_from_path(lessons_path)

    if not include_all:
        lessons = [lesson for lesson in lessons if lesson.state in ELIGIBLE_STATES]

    if category:
        lessons = [lesson for lesson in lessons if lesson.category.upper() == category.upper()]

    # Sort by confidence descending
    lessons.sort(key=lambda lesson: lesson.confidence, reverse=True)

    return [_lesson_to_dict(lesson) for lesson in lessons]


def explain_rule(
    *,
    db_path: Path | str,
    events_path: Path | str,
    rule_id: str,
    lessons_path: Path | str,
) -> dict:
    """Trace a rule back to its source corrections and transitions.

    Args:
        db_path: Path to system.db.
        events_path: Reserved for future provenance event lookup.
        rule_id: The stable rule ID (from list_rules).
        lessons_path: Path to lessons.md.

    Returns:
        Dict with rule metadata, correction_ids, transitions, and root_cause.
        Returns {"error": "..."} if rule_id not found.
    """
    lessons = _load_lessons_from_path(lessons_path)

    # Find the lesson matching this rule_id
    target: Lesson | None = None
    for lesson in lessons:
        if _make_rule_id(lesson) == rule_id:
            target = lesson
            break

    if target is None:
        return {"error": f"Rule not found: {rule_id}"}

    result = _lesson_to_dict(target)

    # Fetch transitions from SQLite
    transitions: list[dict] = []
    db = Path(db_path)
    if db.is_file():
        try:
            with sqlite3.connect(str(db)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """SELECT old_state, new_state, confidence, fire_count,
                              session, transitioned_at
                       FROM lesson_transitions
                       WHERE lesson_desc = ? AND category = ?
                       ORDER BY transitioned_at""",
                    (target.description, target.category),
                ).fetchall()
                transitions = [dict(r) for r in rows]
        except Exception as e:
            _log.debug("Failed to query lesson_transitions: %s", e)

    result["transitions"] = transitions
    return result


def export_rules(
    *,
    db_path: Path | str,
    lessons_path: Path | str,
    output_format: str = "json",
) -> str:
    """Export rules in the specified format.

    Args:
        db_path: Path to system.db.
        lessons_path: Path to lessons.md.
        output_format: "json" or "yaml". Raises ValueError for unsupported formats.

    Returns:
        Serialized string in the requested format.
    """
    if output_format not in ("json", "yaml"):
        raise ValueError(f"Unsupported format: {output_format!r}. Use 'json' or 'yaml'.")

    rules = list_rules(db_path=db_path, lessons_path=lessons_path)
    payload = {
        "rules": rules,
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(rules),
            "format": output_format,
        },
    }

    if output_format == "json":
        return json.dumps(payload, indent=2, default=str)

    # YAML — minimal serializer, no PyYAML dependency
    return _dict_to_yaml(payload)


# ---------------------------------------------------------------------------
# Minimal YAML serializer (~30 lines, no PyYAML dependency)
# ---------------------------------------------------------------------------

def _yaml_val(v: object) -> str:
    """Format a scalar value for YAML output."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Escape embedded double quotes before wrapping
    s = s.replace('"', '\\"')
    # Quote strings that could be misinterpreted
    if s == "" or ":" in s or "#" in s or s.startswith(("-", "[", "{")):
        return f'"{s}"'
    return s


def _dict_to_yaml(d: object, indent: int = 0) -> str:
    """Convert a dict/list/scalar to minimal YAML string."""
    prefix = "  " * indent
    lines: list[str] = []

    if isinstance(d, dict):
        for key, val in d.items():
            if isinstance(val, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(_dict_to_yaml(val, indent + 1))
            elif isinstance(val, list):
                lines.append(f"{prefix}{key}:")
                for item in val:
                    if isinstance(item, dict):
                        # First key on the "- " line, rest indented
                        items = list(item.items())
                        if items:
                            k0, v0 = items[0]
                            if isinstance(v0, (dict, list)):
                                lines.append(f"{prefix}  - {k0}:")
                                lines.append(_dict_to_yaml(v0, indent + 3))
                            else:
                                lines.append(f"{prefix}  - {k0}: {_yaml_val(v0)}")
                            for k, v in items[1:]:
                                if isinstance(v, (dict, list)):
                                    lines.append(f"{prefix}    {k}:")
                                    lines.append(_dict_to_yaml(v, indent + 3))
                                else:
                                    lines.append(f"{prefix}    {k}: {_yaml_val(v)}")
                    else:
                        lines.append(f"{prefix}  - {_yaml_val(item)}")
            else:
                lines.append(f"{prefix}{key}: {_yaml_val(val)}")
    elif isinstance(d, list):
        for item in d:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(_dict_to_yaml(item, indent + 1))
            else:
                lines.append(f"{prefix}- {_yaml_val(item)}")
    else:
        lines.append(f"{prefix}{_yaml_val(d)}")

    return "\n".join(lines)
