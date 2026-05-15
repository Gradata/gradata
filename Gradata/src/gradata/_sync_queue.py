"""Sync queue primitives — local SQLite buffer for write-through cloud sync.

Day 1 of #194 (write-through sync). Provides CRUD over the ``sync_queue``
table that is created as part of the standard Brain schema (see
``_migrations/__init__.py``). The queue stores serialized payloads that
need to be flushed to the cloud ingest endpoint; the actual flush
worker is implemented later in the rollout.

All public functions take an explicit ``sqlite3.Connection`` as the first
argument — there are no implicit globals or module-level state.
"""

from __future__ import annotations

import json
import sqlite3
import time

__all__ = ["enqueue", "peek_pending", "mark_synced", "mark_failed"]

_VALID_KINDS = ("correction", "lesson", "event")
_MAX_ERROR_LEN = 500


def enqueue(conn: sqlite3.Connection, kind: str, payload: dict) -> int:
    """Insert a new row into ``sync_queue`` and return its row id.

    Args:
        conn: Active SQLite connection to a brain database.
        kind: One of ``'correction'``, ``'lesson'``, ``'event'``. The
            CHECK constraint on the column will reject anything else
            with :class:`sqlite3.IntegrityError`.
        payload: Arbitrary JSON-serializable dict; stored via
            ``json.dumps`` into ``payload_json``.

    Returns:
        The autoincrement ``id`` of the newly inserted row.
    """
    payload_json = json.dumps(payload, ensure_ascii=False)
    cur = conn.execute(
        "INSERT INTO sync_queue (payload_json, kind, enqueued_at) "
        "VALUES (?, ?, ?)",
        (payload_json, kind, time.time()),
    )
    conn.commit()
    rowid = cur.lastrowid
    if rowid is None:
        raise RuntimeError("sync_queue insert did not return a lastrowid")
    return int(rowid)


def peek_pending(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    """Return up to ``limit`` pending rows ordered by id (FIFO).

    Pending == ``synced_at IS NULL``. Each returned dict has keys:
    ``id`` (int), ``kind`` (str), ``payload`` (decoded dict),
    ``enqueued_at`` (float), and ``attempts`` (int).
    """
    rows = conn.execute(
        "SELECT id, kind, payload_json, enqueued_at, attempts "
        "FROM sync_queue "
        "WHERE synced_at IS NULL "
        "ORDER BY id ASC "
        "LIMIT ?",
        (int(limit),),
    ).fetchall()

    out: list[dict] = []
    for r in rows:
        # Support both sqlite3.Row (named) and tuple rows.
        try:
            rid = r["id"]
            kind = r["kind"]
            payload_json = r["payload_json"]
            enqueued_at = r["enqueued_at"]
            attempts = r["attempts"]
        except (TypeError, IndexError):
            rid, kind, payload_json, enqueued_at, attempts = r
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            payload = {"_raw": payload_json}
        out.append(
            {
                "id": int(rid),
                "kind": kind,
                "payload": payload,
                "enqueued_at": float(enqueued_at) if enqueued_at is not None else None,
                "attempts": int(attempts) if attempts is not None else 0,
            }
        )
    return out


def mark_synced(conn: sqlite3.Connection, ids: list[int]) -> None:
    """Mark the given row ids as successfully synced (sets ``synced_at``)."""
    if not ids:
        return
    now = time.time()
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE sync_queue SET synced_at = ? WHERE id IN ({placeholders})",
        (now, *[int(i) for i in ids]),
    )
    conn.commit()


def mark_failed(conn: sqlite3.Connection, ids: list[int], error: str) -> None:
    """Record a failed sync attempt for the given rows.

    Increments ``attempts`` and stores the (truncated) error message on
    every targeted row. The rows remain pending (``synced_at`` stays
    NULL) so they will be retried.
    """
    if not ids:
        return
    truncated = (error or "")[:_MAX_ERROR_LEN]
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE sync_queue "
        f"SET attempts = COALESCE(attempts, 0) + 1, last_error = ? "
        f"WHERE id IN ({placeholders})",
        (truncated, *[int(i) for i in ids]),
    )
    conn.commit()
