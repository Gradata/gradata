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
from collections.abc import Iterable

_log = logging.getLogger(__name__)

# `|Δconfidence| >= CONFLICT_THRESHOLD` escalates Tier 1 -> Tier 2.
# Spec default; overridable via `cloud-config.json`.
CONFLICT_THRESHOLD: float = 0.15

# Event types the materializer is allowed to fold into winner/conflict state.
# Other types pulled alongside (CORRECTION, OUTPUT_ACCEPTED, IMPLICIT_FEEDBACK,
# etc.) are out of scope per docs/specs/merge-semantics.md §2 and must not
# advance graduation state even if they carry a (category, pattern_hash) key.
_MATERIALIZABLE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "RULE_GRADUATED",
        "RULE_DEMOTED",
        "RULE_OVERRIDE",
        "RULE_CONFLICT_RESOLVED",
        "META_RULE_SYNTHESIZED",
    }
)


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
    # Normalize category to lowercase so rules emitted with mixed casing
    # (e.g. "Security" vs "security") converge on a single materialized row
    # instead of fragmenting into duplicates that later trigger spurious
    # conflicts during merge.
    category = str(data.get("category") or "").strip().lower()
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
    # Parse each side independently — coupling them with a single try/except
    # would silently zero out a valid confidence whenever the *other* side
    # was malformed, converting a legitimate update into a Tier 2 bypass.
    try:
        e_conf = float(e_data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        e_conf = 0.0
    try:
        i_conf = float(i_data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        i_conf = 0.0

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


def _load_events_from_db(
    db_path: Path,
    event_types: Iterable[str] | None = None,
) -> list[dict]:
    """Load candidate events from system.db in ts-ASC order.

    Returns events with ``data`` already decoded from ``data_json``. Rows
    that fail to decode are skipped (never fatal — caller gets the rest).
    """
    if not db_path.exists():
        return []
    # Default to the materializable set (minus META_RULE_SYNTHESIZED which
    # the pass currently always skips). Keeping the default a single source
    # of truth removes the old _MATERIALIZER_EVENT_TYPES / _MATERIALIZABLE_
    # EVENT_TYPES drift CodeRabbit flagged.
    types = tuple(event_types if event_types is not None else _MATERIALIZABLE_EVENT_TYPES)
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
        if etype not in _MATERIALIZABLE_EVENT_TYPES:
            # Non-graduation events share the /events/pull stream (corrections,
            # output telemetry, implicit feedback). Per spec §2 they must not
            # influence winner selection even if they carry a category hash.
            result.events_skipped += 1
            continue
        if etype == "META_RULE_SYNTHESIZED":
            # Per spec §4: meta-rules must wait for all source lessons to
            # clear any Tier 2 hold before materializing. Phase 2 doesn't
            # track per-source lineage through this loop, so hold the
            # event rather than risk materializing a meta-rule on top of
            # unresolved source disagreement. Dashboard surfaces the block
            # via the MATERIALIZE_SKIPPED count + event recording elsewhere.
            result.events_skipped += 1
            continue
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
            # `winning_ts` (ISO) pointing at the graduation event to apply
            # and — when the emitter includes it — a full `winning_event`
            # snapshot so incremental pulls that arrive alone (without the
            # original graduation in the same batch) still resolve.
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
            if picked is None:
                # Fallback A: the resolver may carry the full winner payload
                # under ``winning_event``. This is what Phase 2 emitters are
                # expected to populate so a standalone RULE_CONFLICT_RESOLVED
                # in an incremental pull is self-sufficient.
                embedded = data.get("winning_event")
                if isinstance(embedded, dict):
                    picked = embedded
            if picked is None:
                # Fallback B: the resolver may carry just the scalar winner
                # fields (description/new_state/confidence/fire_count) under
                # ``winning_snapshot``. Reconstruct a synthetic graduation
                # event so the winner path below can fold it into state.
                snapshot = data.get("winning_snapshot")
                if isinstance(snapshot, dict):
                    picked = {
                        "type": "RULE_GRADUATED",
                        "ts": winning_ts or str(evt.get("ts") or ""),
                        "data": {
                            "category": key[0],
                            "pattern_hash": key[1],
                            "device_id": winning_device,
                            **snapshot,
                        },
                    }
            conflict_holds.pop(key, None)
            if picked is not None:
                winners[key] = picked
            else:
                # No way to reconstruct the winner — caller passed a partial
                # stream and the resolver carried no payload. Leave the hold
                # cleared; state will catch up on the next full replay.
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
        # Defensive numeric coercion — a graduation event with a non-numeric
        # confidence/fire_count (seen in hand-edited test fixtures and very
        # old DB rows) would otherwise raise deep inside the dataclass
        # constructor and kill the entire materialization pass.
        try:
            confidence = float(data.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        try:
            fire_count = int(data.get("fire_count") or 0)
        except (TypeError, ValueError):
            fire_count = 0
        result.rules[key] = MaterializedRule(
            category=key[0],
            description=str(data.get("description") or ""),
            state=str(data.get("new_state") or ""),
            confidence=confidence,
            fire_count=fire_count,
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
