"""Materialize graduated RULE events into brain/rules/*.json files.

RULE_GRADUATED events are the transition log; these JSON files are the durable
per-rule artifacts consumed by lightweight injectors/exporters. The writer is
best-effort and idempotent: repeat emissions for the same rule_id overwrite the
same file atomically.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gradata._atomic import atomic_write_json

_log = logging.getLogger(__name__)


def rule_id_for(category: str, pattern: str) -> str:
    """Return the stable rule id used by RULE_GRADUATED payloads."""
    return hashlib.sha256(f"{category}:{pattern}".encode("utf-8")).hexdigest()[:16]


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _record_from_payload(payload: dict, *, session: int | None = None) -> dict | None:
    """Build the canonical rules/<rule_id>.json record from an event payload."""
    if (payload.get("new_state") or "") != "RULE":
        return None

    category = str(payload.get("category") or "GENERAL")
    pattern = str(payload.get("pattern") or payload.get("description") or "").strip()
    if not pattern:
        return None

    rule_id = str(payload.get("rule_id") or rule_id_for(category, pattern))
    source_ids = payload.get("source_correction_ids") or []
    if not isinstance(source_ids, list):
        source_ids = [source_ids]
    source_id = payload.get("source_correction_id") or (source_ids[0] if source_ids else None)

    graduation = {
        "old_state": payload.get("old_state"),
        "new_state": payload.get("new_state"),
        "reason": payload.get("reason"),
        "confidence": _coerce_float(payload.get("confidence")),
        "fire_count": _coerce_int(payload.get("fire_count")),
        "graduated_at": datetime.now(UTC).isoformat(),
    }
    if session is not None:
        graduation["session"] = session

    return {
        "schema_version": 1,
        "rule_id": rule_id,
        "pattern": pattern,
        "category": category,
        "source": payload.get("source") or "graduate",
        "source_correction_id": source_id,
        "source_correction_ids": source_ids,
        "lesson_description": payload.get("lesson_description") or pattern,
        "confidence": graduation["confidence"],
        "fire_count": graduation["fire_count"],
        "graduation": graduation,
    }


def write_rule_file(payload: dict, brain_dir: str | Path, *, session: int | None = None) -> Path | None:
    """Write brain/rules/<rule_id>.json for PATTERN->RULE graduations.

    Returns the written path, or None if the payload is not a RULE graduation or
    cannot be materialized. Never raises; callers should treat this as a
    best-effort side effect of the graduation event.
    """
    try:
        record = _record_from_payload(payload, session=session)
        if record is None:
            return None
        path = Path(brain_dir) / "rules" / f"{record['rule_id']}.json"
        atomic_write_json(path, record, indent=2)
        return path
    except Exception as exc:  # pragma: no cover - defensive best-effort guard
        _log.debug("rule file materialization failed: %s", exc)
        return None


def write_rule_file_for_lesson(
    lesson: Any,
    brain_dir: str | Path,
    *,
    old_state: Any,
    reason: str,
    session: int | None = None,
) -> Path | None:
    """Materialize a just-graduated Lesson without requiring an event payload."""
    category = getattr(lesson, "category", "") or ""
    pattern = getattr(lesson, "description", "") or ""
    source_ids = list(getattr(lesson, "correction_event_ids", []) or [])
    payload = {
        "rule_id": rule_id_for(category, pattern),
        "pattern": pattern,
        "source_correction_id": source_ids[0] if source_ids else None,
        "source_correction_ids": source_ids,
        "lesson_description": pattern,
        "category": category,
        "description": pattern,
        "old_state": getattr(old_state, "name", str(old_state)),
        "new_state": getattr(getattr(lesson, "state", None), "name", str(getattr(lesson, "state", ""))),
        "confidence": getattr(lesson, "confidence", 0.0),
        "fire_count": getattr(lesson, "fire_count", 0),
        "reason": reason,
        "source": "graduate",
    }
    return write_rule_file(payload, brain_dir, session=session)
