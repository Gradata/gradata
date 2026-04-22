"""Event-stream → lesson state materializer (Phase 2).

Rebuilds ``lessons.state`` from the ordered RULE_GRADUATED / RULE_DEMOTED
event stream alone. Enables disaster recovery and multi-device sync: a
fresh device can replay cloud events and converge on the same state the
origin device graduated to.

Contract (from ``docs/specs/merge-semantics.md``, Decision 9):

- Tier 1 (automatic, LWW): when two events share ``(category, pattern_hash)``
  and ``|Δconfidence| < 0.15`` and ``new_state`` agrees, later ``ts`` wins.
  Tie-break on ``device_id`` lexicographically.
- Tier 2 (conflict queue): when ``|Δconfidence| >= 0.15`` OR ``new_state``
  disagrees, neither version materializes — a ``RULE_CONFLICT`` event is
  emitted and the state stays at whatever preceded the conflict.
- Tier 3 (source-authority override): ``RULE_OVERRIDE`` events trump
  Tier 1/2. Phase 3 — recorded here but never produced by Phase 2.

Phase 2 scope:
- Tier 1 implemented.
- Tier 2 detects conflicts and returns them; emitting ``RULE_CONFLICT``
  back into the event stream is the caller's decision (so dry-run is
  non-mutating).
- Tier 3 recognized but not applied.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

_log = logging.getLogger(__name__)

# `|Δconfidence| >= CONFLICT_THRESHOLD` escalates Tier 1 -> Tier 2.
# Spec default; overridable via `cloud-config.json`.
CONFLICT_THRESHOLD: float = 0.15


@dataclass(frozen=True)
class MaterializedRule:
    """Point-in-time state of a graduated rule derived from events."""

    category: str
    description: str
    state: str
    confidence: float
    fire_count: int
    winning_event_ts: str
    winning_device_id: str


@dataclass(frozen=True)
class Conflict:
    """Two events disagree too strongly for LWW. Caller must adjudicate."""

    key: tuple[str, str]  # (category, pattern_hash_or_description)
    left_event: dict
    right_event: dict
    reason: str  # "confidence_drift" | "state_disagreement"


@dataclass
class MaterializeResult:
    """Output of :func:`materialize`."""

    rules: dict[tuple[str, str], MaterializedRule] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)
    events_consumed: int = 0
    events_skipped: int = 0


def _rule_key(event: dict) -> tuple[str, str] | None:
    """Key an event by (category, pattern_hash|description).

    ``pattern_hash`` is the stable identifier once available; falls back
    to trimmed description for pre-hash events.
    """
    data = event.get("data") or {}
    category = str(data.get("category") or "").strip()
    pattern_hash = str(data.get("pattern_hash") or "").strip()
    description = str(data.get("description") or "").strip()
    ident = pattern_hash or description
    if not category or not ident:
        return None
    return (category, ident)


def _lww(left: dict, right: dict) -> dict:
    """Return the winner per Tier 1: later ts, tiebreak on device_id."""
    lt = str(left.get("ts") or "")
    rt = str(right.get("ts") or "")
    if lt != rt:
        return right if rt > lt else left
    ld = str((left.get("data") or {}).get("device_id") or "")
    rd = str((right.get("data") or {}).get("device_id") or "")
    return right if rd > ld else left


def _apply_tier(
    existing: dict | None,
    incoming: dict,
    threshold: float,
) -> tuple[dict | None, Conflict | None]:
    """Decide whether ``incoming`` updates state, holds as conflict, or is ignored.

    Returns ``(new_winner, conflict)``:
    - ``new_winner``: the event that now represents state, or ``None`` if
      we remain in a conflict hold.
    - ``conflict``: set when Tier 2 triggers.
    """
    if existing is None:
        return incoming, None

    e_data = existing.get("data") or {}
    i_data = incoming.get("data") or {}
    e_state = str(e_data.get("new_state") or "")
    i_state = str(i_data.get("new_state") or "")
    try:
        e_conf = float(e_data.get("confidence") or 0.0)
        i_conf = float(i_data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        e_conf = i_conf = 0.0

    delta = abs(i_conf - e_conf)
    state_disagrees = bool(e_state and i_state and e_state != i_state)

    if delta >= threshold or state_disagrees:
        key = _rule_key(incoming) or ("", "")
        reason = "state_disagreement" if state_disagrees else "confidence_drift"
        return None, Conflict(
            key=key,
            left_event=existing,
            right_event=incoming,
            reason=reason,
        )

    winner = _lww(existing, incoming)
    return winner, None


_MATERIALIZER_EVENT_TYPES: tuple[str, ...] = (
    "RULE_GRADUATED",
    "RULE_DEMOTED",
    "RULE_OVERRIDE",
    "RULE_CONFLICT_RESOLVED",
)


def _load_events_from_db(
    db_path: Path,
    event_types: Iterable[str] = _MATERIALIZER_EVENT_TYPES,
) -> list[dict]:
    """Load candidate events from system.db in ts-ASC order.

    Returns events with ``data`` already decoded from ``data_json``. Rows
    that fail to decode are skipped (never fatal — caller gets the rest).
    """
    if not db_path.exists():
        return []
    types = tuple(event_types)
    placeholders = ",".join(["?"] * len(types))
    query = (
        f"SELECT ts, type, source, data_json FROM events "
        f"WHERE type IN ({placeholders}) ORDER BY ts ASC, id ASC"
    )
    out: list[dict] = []
    with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
        try:
            rows = conn.execute(query, types).fetchall()
        except sqlite3.OperationalError as exc:
            _log.debug("materializer db read failed: %s", exc)
            return []
    for ts, etype, source, data_json in rows:
        try:
            data = json.loads(data_json) if data_json else {}
        except json.JSONDecodeError:
            continue
        out.append({"ts": ts, "type": etype, "source": source, "data": data})
    return out


def materialize(
    events: Iterable[dict] | None = None,
    *,
    db_path: Path | None = None,
    threshold: float = CONFLICT_THRESHOLD,
) -> MaterializeResult:
    """Fold an event stream into current rule state.

    Supply ``events`` directly (for testing / pulled batches) or let the
    materializer read from ``db_path`` — not both.

    The function is **pure**: no writes to the events table, no mutation
    of input events, no network. Apply the returned state however the
    caller wants (rebuild ``lessons`` table, emit ``RULE_CONFLICT``, etc).
    """
    if events is not None and db_path is not None:
        raise ValueError("pass events OR db_path, not both")
    if events is None:
        events = _load_events_from_db(db_path) if db_path else []

    # Track the current "winning" event per key, plus any active conflict.
    winners: dict[tuple[str, str], dict] = {}
    conflict_holds: dict[tuple[str, str], Conflict] = {}
    result = MaterializeResult()

    # Index graduation events by ts so RULE_CONFLICT_RESOLVED can re-apply
    # the winning side once adjudication lands. The spec names a winning
    # event_id; we fall back to (ts, device_id) because the Phase 1 event
    # schema doesn't expose event_id on the materializer input.
    graduation_history: dict[tuple[str, str], list[dict]] = {}

    for evt in events:
        result.events_consumed += 1
        etype = str(evt.get("type") or "")
        if etype == "RULE_OVERRIDE":
            # Tier 3: Phase 3 feature. Recorded as winner unconditionally
            # but flagged so callers know this path ran.
            key = _rule_key(evt)
            if key is None:
                result.events_skipped += 1
                continue
            winners[key] = evt
            conflict_holds.pop(key, None)
            continue

        if etype == "RULE_CONFLICT_RESOLVED":
            # User adjudicated a held Tier 2 conflict. Clear the hold and
            # materialize the picked side. The resolver event carries
            # `winning_ts` (ISO) pointing at the graduation event to apply.
            key = _rule_key(evt)
            if key is None:
                result.events_skipped += 1
                continue
            data = evt.get("data") or {}
            winning_ts = str(data.get("winning_ts") or "")
            winning_device = str(data.get("winning_device_id") or "")
            picked: dict | None = None
            for hist in graduation_history.get(key, []):
                ht = str(hist.get("ts") or "")
                hd = str((hist.get("data") or {}).get("device_id") or "")
                if ht == winning_ts and (not winning_device or hd == winning_device):
                    picked = hist
                    break
            conflict_holds.pop(key, None)
            if picked is not None:
                winners[key] = picked
            else:
                # No matching history — caller passed a partial stream.
                # Leave the hold cleared; state will catch up on next pull.
                result.events_skipped += 1
            continue

        key = _rule_key(evt)
        if key is None:
            result.events_skipped += 1
            continue

        # Record every graduation in history for later RULE_CONFLICT_RESOLVED
        # lookup. Accumulates regardless of conflict state so a resolver
        # that names a held event can still find it.
        graduation_history.setdefault(key, []).append(evt)

        if key in conflict_holds:
            # Spec §3 Tier 2: a held conflict stays held until a
            # RULE_CONFLICT_RESOLVED or RULE_OVERRIDE lands. Subsequent
            # graduation events for this key accumulate but don't
            # change materialized state.
            result.events_skipped += 1
            continue

        existing = winners.get(key)
        winner, conflict = _apply_tier(existing, evt, threshold)
        if conflict is not None:
            conflict_holds[key] = conflict
            result.conflicts.append(conflict)
            # State stays at whatever was winning before; no rollback.
            continue
        if winner is not None:
            winners[key] = winner

    # Prune conflicts that were resolved later in the same stream so
    # callers don't emit stale RULE_CONFLICT events for keys already
    # adjudicated.
    if result.conflicts:
        result.conflicts = [c for c in result.conflicts if c.key in conflict_holds]

    for key, evt in winners.items():
        data = evt.get("data") or {}
        result.rules[key] = MaterializedRule(
            category=key[0],
            description=str(data.get("description") or ""),
            state=str(data.get("new_state") or ""),
            confidence=float(data.get("confidence") or 0.0),
            fire_count=int(data.get("fire_count") or 0),
            winning_event_ts=str(evt.get("ts") or ""),
            winning_device_id=str(data.get("device_id") or ""),
        )
    return result


__all__ = [
    "CONFLICT_THRESHOLD",
    "Conflict",
    "MaterializedRule",
    "MaterializeResult",
    "materialize",
]
