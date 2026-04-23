"""
Observation Dedup — fingerprint-based near-duplicate suppression.
================================================================
SDK LAYER: Layer 1 (enhancements). Stdlib only.

Problem
-------
Ten sessions that all contain "don't use em-dashes" should NOT produce ten
lesson reinforcements and inflate confidence 10x. Each (category, normalized
text) pair is the same **observation** and must be deduped before it flows
into the fire_count / confidence pipeline.

Public API
----------
    from gradata.enhancements.dedup import (
        observation_fingerprint,
        is_duplicate,
        register_observation,
    )

    fp = observation_fingerprint("Don't use em-dashes.", category="FORMAT")
    if is_duplicate(db_path, fp, recent_window_sessions=10):
        # suppress — already seen in recent window
        ...
    else:
        register_observation(db_path, fp, session=42)

Semantics
---------
Default = **DROP** within the recent-session window. `seen_count` is tracked
on the persisted row so MERGE semantics (bump fire_count by seen_count at
window rollover) can be wired in later without losing evidence.

MERGE vs DROP is a policy decision flagged for polyclaude — see the task brief
for wt-observation-dedup. The current codebase cannot wire seen_count into
`update_confidence` without editing `self_improvement.py`, which is off-limits
for this worktree.

Storage
-------
A single table in system.db:

    observation_dedup(
        fingerprint TEXT PRIMARY KEY,
        category    TEXT NOT NULL,
        first_session INTEGER NOT NULL,
        last_session  INTEGER NOT NULL,
        seen_count    INTEGER NOT NULL DEFAULT 1,
        first_seen_ts TEXT NOT NULL,
        last_seen_ts  TEXT NOT NULL
    )

Normalization
-------------
- lowercase
- strip leading/trailing whitespace
- collapse internal whitespace to a single space
- drop trailing punctuation (. , ; : ! ?)
- category is uppercased and prefixed to the hash input so the same phrasing
  under different categories is NOT deduped together.

Hash: sha1 of ``f"{CATEGORY}|{normalized_text}"`` — stable across processes
and cheap enough to compute on every ingestion.
"""

from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from gradata._db import ensure_table, get_connection

_log = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")

_DEFAULT_WINDOW_SESSIONS = 10

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS observation_dedup (
    fingerprint    TEXT PRIMARY KEY,
    category       TEXT NOT NULL,
    first_session  INTEGER NOT NULL,
    last_session   INTEGER NOT NULL,
    seen_count     INTEGER NOT NULL DEFAULT 1,
    first_seen_ts  TEXT NOT NULL,
    last_seen_ts   TEXT NOT NULL
)
"""

_CREATE_IDX_LAST_SESSION = (
    "CREATE INDEX IF NOT EXISTS idx_observation_dedup_last_session "
    "ON observation_dedup(last_session)"
)


def _normalize_text(text: str) -> str:
    """Canonical form used for fingerprinting.

    Lowercase, trim, collapse whitespace, drop trailing punctuation.
    """
    if not text:
        return ""
    s = _WS_RE.sub(" ", text.strip().lower())
    return _TRAILING_PUNCT_RE.sub("", s).strip()


def _normalize_category(category: str | None) -> str:
    return (category or "UNKNOWN").strip().upper() or "UNKNOWN"


def observation_fingerprint(text: str, category: str | None = None) -> str:
    """Return a stable sha1 fingerprint for (category, normalized text).

    Two near-identical corrections (differing only in case, trailing
    punctuation, or whitespace) produce the same fingerprint. Different
    categories for the same text produce **different** fingerprints — by
    design, since the same phrase can mean different things in different
    categories.
    """
    payload = f"{_normalize_category(category)}|{_normalize_text(text)}".encode()
    return hashlib.sha1(payload).hexdigest()


def _open(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with schema ensured. Caller owns the connection."""
    conn = get_connection(db_path)
    ensure_table(conn, _CREATE_SQL)
    conn.execute(_CREATE_IDX_LAST_SESSION)
    conn.commit()
    return conn


def is_duplicate(
    db_path: str | Path,
    fingerprint: str,
    *,
    current_session: int | None = None,
    recent_window_sessions: int = _DEFAULT_WINDOW_SESSIONS,
) -> bool:
    """Return True if this fingerprint was seen inside the recent session window.

    Window definition: the row's ``last_session`` is within
    ``recent_window_sessions`` of ``current_session``. If no row exists for
    this fingerprint, it's not a duplicate.

    Edge cases:
    - current_session=None => dedup against any prior sighting (window is
      effectively open-ended). This is the safe default for non-session
      callers.
    - recent_window_sessions<=0 => same as None; any prior sighting counts.
    """
    conn = _open(db_path)
    try:
        row = conn.execute(
            "SELECT last_session FROM observation_dedup WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return False
    last_session = row[0]
    if current_session is None or recent_window_sessions <= 0:
        return True
    # Window: inclusive lower bound at (current_session - window + 1)
    return last_session >= current_session - recent_window_sessions + 1


def register_observation(
    db_path: str | Path,
    fingerprint: str,
    *,
    category: str | None = None,
    session: int | None = None,
) -> dict:
    """Record a sighting of ``fingerprint``. Returns a dict describing the outcome.

    - If the fingerprint is new: inserts a row with seen_count=1.
    - If already present: increments seen_count and updates last_session /
      last_seen_ts.

    Returns
    -------
    {"new": True/False, "seen_count": int, "fingerprint": str}
    """
    sess = int(session) if session is not None else 0
    norm_cat = _normalize_category(category)
    now = datetime.now(UTC).isoformat()

    conn = _open(db_path)
    try:
        existing = conn.execute(
            "SELECT seen_count, first_session FROM observation_dedup WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO observation_dedup "
                "(fingerprint, category, first_session, last_session, "
                " seen_count, first_seen_ts, last_seen_ts) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (fingerprint, norm_cat, sess, sess, now, now),
            )
            conn.commit()
            return {"new": True, "seen_count": 1, "fingerprint": fingerprint}
        new_count = int(existing[0]) + 1
        conn.execute(
            "UPDATE observation_dedup "
            "SET seen_count = ?, last_session = ?, last_seen_ts = ? "
            "WHERE fingerprint = ?",
            (new_count, sess, now, fingerprint),
        )
        conn.commit()
        return {"new": False, "seen_count": new_count, "fingerprint": fingerprint}
    finally:
        conn.close()


def check_and_register(
    db_path: str | Path,
    text: str,
    *,
    category: str | None = None,
    session: int | None = None,
    recent_window_sessions: int = _DEFAULT_WINDOW_SESSIONS,
) -> dict:
    """Convenience: fingerprint + duplicate-check + register in one call.

    This is the single hook point intended for the ingestion path.

    Returns
    -------
    {
        "fingerprint": str,
        "is_duplicate": bool,     # was this a dup BEFORE this registration?
        "seen_count": int,        # seen_count AFTER this registration
        "new": bool,              # was this the first sighting ever?
    }
    """
    fp = observation_fingerprint(text, category=category)
    dup = is_duplicate(
        db_path,
        fp,
        current_session=session,
        recent_window_sessions=recent_window_sessions,
    )
    reg = register_observation(db_path, fp, category=category, session=session)
    return {
        "fingerprint": fp,
        "is_duplicate": dup,
        "seen_count": reg["seen_count"],
        "new": reg["new"],
    }


def annotate_event_with_dedup(
    event: dict,
    db_path: str | Path,
    *,
    draft: str,
    final: str,
    category: str | None,
    session: int | None,
) -> bool:
    """Single-seam ingestion hook used by `brain_correct`.

    Fingerprints on the (draft, final) pair (first 500 chars each) so truly
    identical corrections dedup but genuinely distinct ones do NOT. Mutates
    ``event`` in place to add ``observation_fingerprint`` and
    ``observation_seen_count``, plus ``observation_deduped`` when a hit is
    inside the recent-session window.

    Returns True if the observation was a duplicate (caller should skip the
    lesson create/reinforce branch). Any error is swallowed and returns False
    so dedup cannot break the ingestion path.
    """
    try:
        dedup_text = f"{(draft or '')[:500]}||{(final or '')[:500]}"
        info = check_and_register(
            db_path,
            dedup_text,
            category=(category or "UNKNOWN"),
            session=session,
        )
        event["observation_fingerprint"] = info["fingerprint"]
        event["observation_seen_count"] = info["seen_count"]
        if info["is_duplicate"]:
            event["observation_deduped"] = True
            return True
        return False
    except Exception as e:
        _log.debug("Observation dedup failed: %s", e)
        return False


__all__ = [
    "annotate_event_with_dedup",
    "check_and_register",
    "is_duplicate",
    "observation_fingerprint",
    "register_observation",
]
