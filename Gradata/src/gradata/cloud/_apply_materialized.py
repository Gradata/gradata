"""Apply a MaterializeResult to an in-memory Lesson list.

Keeps the materializer itself pure (no imports of the broader SDK). This
module is the adapter between the event-fold and the persistent lessons
store. Callers:

- Disaster recovery (``/events/pull`` with empty local state)
- Multi-device reconciliation after a pull
- Tests that want to verify state derives from events alone

The apply path is deliberately non-destructive for fields the materializer
doesn't know about (scope_json, metadata, memory_ids, etc.). Only the
three fields graduation actually drives — ``state``, ``confidence``,
``fire_count`` — are overwritten.
"""

from __future__ import annotations

import logging

from gradata._types import Lesson, LessonState
from gradata.cloud.materializer import MaterializeResult

_log = logging.getLogger(__name__)


def _state_from_name(name: str) -> LessonState | None:
    """Parse ``'PATTERN'`` → ``LessonState.PATTERN``; tolerate unknowns."""
    if not name:
        return None
    try:
        return LessonState[name]
    except KeyError:
        _log.debug("unknown LessonState %r in materialized event", name)
        return None


def apply_to_lessons(
    lessons: list[Lesson],
    result: MaterializeResult,
) -> list[Lesson]:
    """Return a new list with materialized state merged into ``lessons``.

    Matching key: ``(category, description)``. If the materializer's
    key uses ``pattern_hash``, callers should resolve ``pattern_hash`` to
    ``description`` before invoking this helper (the materializer carries
    description in the result for exactly this reason).

    Existing lessons not touched by any materialized rule are returned
    unchanged. Materialized rules that have no corresponding Lesson are
    appended as fresh ``Lesson`` rows so disaster recovery on a blank
    device converges to the same state as the origin device.

    Skipped intentionally:
    - Rules currently held in a Tier 2 conflict (``result.conflicts``)
      do not overwrite local state. Callers should emit ``RULE_CONFLICT``
      events separately (see :func:`emit_conflict_events`).
    """
    # Match case-insensitively on category — lessons.md uppercases on
    # serialize, while events carry the raw emitted case. Without
    # normalization, a second apply would duplicate every row.
    by_key: dict[tuple[str, str], Lesson] = {
        (l.category.upper(), l.description): l for l in lessons
    }

    # Skip any key currently in conflict — local state stands until
    # user adjudicates via RULE_CONFLICT_RESOLVED.
    conflict_keys = {c.key for c in result.conflicts}

    updated: list[Lesson] = list(lessons)
    for key, rule in result.rules.items():
        if key in conflict_keys:
            continue
        new_state = _state_from_name(rule.state)
        if new_state is None:
            continue

        lesson_key = (rule.category.upper(), rule.description)
        existing = by_key.get(lesson_key)
        if existing is not None:
            existing.state = new_state
            existing.confidence = rule.confidence
            if rule.fire_count > existing.fire_count:
                existing.fire_count = rule.fire_count
            continue

        # New lesson from the event stream — fill the minimum contract.
        # date defaults to the winning event's ts; callers that need
        # finer-grained lesson provenance can post-process.
        fresh = Lesson(
            date=rule.winning_event_ts[:10] if rule.winning_event_ts else "",
            state=new_state,
            confidence=rule.confidence,
            category=rule.category.upper(),
            description=rule.description,
            fire_count=rule.fire_count,
        )
        updated.append(fresh)
    return updated


def emit_conflict_events(
    result: MaterializeResult,
    *,
    emit_fn=None,
) -> int:
    """Emit a ``RULE_CONFLICT`` event for each unresolved Tier 2 conflict.

    Best-effort: never raises. Returns the number of events emitted.
    ``emit_fn`` defaults to :func:`gradata._events.emit`; tests can inject
    a recorder.
    """
    if not result.conflicts:
        return 0
    if emit_fn is None:
        from gradata._events import emit as emit_fn  # type: ignore[assignment]

    emitted = 0
    for conflict in result.conflicts:
        payload = {
            "category": conflict.key[0],
            "description": conflict.key[1],
            "reason": conflict.reason,
            "left_ts": str(conflict.left_event.get("ts") or ""),
            "right_ts": str(conflict.right_event.get("ts") or ""),
            "left_device": str((conflict.left_event.get("data") or {}).get("device_id") or ""),
            "right_device": str((conflict.right_event.get("data") or {}).get("device_id") or ""),
        }
        try:
            emit_fn("RULE_CONFLICT", "materializer", payload, [])  # type: ignore[misc]
            emitted += 1
        except Exception as exc:
            _log.debug("RULE_CONFLICT emit failed: %s", exc)
    return emitted


__all__ = ["apply_to_lessons", "emit_conflict_events"]
