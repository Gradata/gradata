"""Push-only cloud sync MVP for Gradata.

Reads rows tagged ``tenant_id = tenant_for(brain_dir)`` from the local
SQLite brain and POSTs them to Supabase via PostgREST. Gated by env:

    GRADATA_CLOUD_SYNC=1          enable sync (default: off)
    GRADATA_CLOUD_URL=https://..  Supabase project URL
    GRADATA_CLOUD_KEY=eyJ...      Supabase anon key (RLS-scoped to tenant)

Design (deliberately small, Karpathy-style):
- One function per table; each is a plain ``SELECT ... WHERE tenant_id = ?``
  filtered by ``last_push_at`` from the ``sync_state`` row.
- A single ``push(brain_dir)`` entrypoint that iterates the table list.
- No background threads, no queues, no retries beyond HTTP status check.
  Failure mode is "skip + log"; the next call will pick up the same rows.
- Visibility defaults to ``private``. Rows with ``visibility='shared'`` or
  ``'global'`` still push under the same tenant_id -- RLS in the cloud
  decides who else can read them.

Not yet implemented (future work, explicitly out of scope):
- Pull / conflict resolution (we're push-only MVP).
- Deletes (cloud rows never get removed by this path).
- Bulk batching beyond one table per HTTP call.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from gradata._tenant import tenant_for
logger = logging.getLogger(__name__)


_log = logging.getLogger("gradata.cloud_sync")

ENV_ENABLED: Final[str] = "GRADATA_CLOUD_SYNC"
ENV_URL: Final[str] = "GRADATA_CLOUD_URL"
ENV_KEY: Final[str] = "GRADATA_CLOUD_KEY"
# Aliases — accept the Supabase-native env var names too, so a single .env
# works for both the cloud backend service and the SDK push path.
ENV_URL_ALIAS: Final[str] = "GRADATA_SUPABASE_URL"
ENV_KEY_ALIAS: Final[str] = "GRADATA_SUPABASE_SERVICE_KEY"


def _env_url() -> str:
    return os.environ.get(ENV_URL) or os.environ.get(ENV_URL_ALIAS) or ""


def _env_key() -> str:
    return os.environ.get(ENV_KEY) or os.environ.get(ENV_KEY_ALIAS) or ""


# Tables pushed to the cloud. Order matters only for foreign keys; we keep
# the parent tables first so Supabase FK constraints pass on first try.
PUSH_TABLES: Final[tuple[str, ...]] = (
    "events",
    "lessons",
    "meta_rules",
    "clusters",
    "correction_patterns",
    "rule_provenance",
)

# Local SQLite table -> cloud Supabase table when names differ.
_TABLE_REMAP: Final[dict[str, str]] = {
    "correction_patterns": "corrections",
}

# Deterministic UUID namespace — stable across re-runs so upserts work.
_UUID_NS: Final[uuid.UUID] = uuid.UUID("b8a1c9e2-9f5d-4c9b-8a1e-7f3b2d1a0e4c")


def _row_uuid(tenant_id: str, table: str, local_key: Any) -> str:
    """Return a deterministic UUID for (tenant, table, local_key)."""
    return str(uuid.uuid5(_UUID_NS, f"{tenant_id}:{table}:{local_key}"))


def _maybe_json(value: Any, default: Any = None) -> Any:
    """Parse a text-encoded JSON column, tolerating nulls + bad data."""
    if value is None or value == "":
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def _scrub(value: Any) -> Any:
    """Recursively clean strings for Postgres JSONB.

    Strips NUL bytes (\\u0000 not allowed) and unpaired UTF-16 surrogates
    (\\ud800-\\udfff) that encode-survive in Python but poison JSONB.
    """
    if isinstance(value, str):
        cleaned = value.replace("\x00", "") if "\x00" in value else value
        # Round-trip through UTF-8 with surrogate replacement to drop lone halves.
        try:
            cleaned.encode("utf-8")
        except UnicodeEncodeError:
            cleaned = cleaned.encode("utf-8", "replace").decode("utf-8")
        return cleaned
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _transform_row(table: str, row: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    """Map a local SQLite row to the cloud Supabase row shape.

    The cloud schema is narrower: `brain_id` not `tenant_id`, `data` JSONB for
    extras, UUIDs for ids. We pick the known cloud columns explicitly and
    pack everything else into `data` so new SDK columns surface without a
    schema migration.
    """
    if table == "events":
        parsed = _maybe_json(row.get("data_json"), default={"_raw": row.get("data_json")})
        data_blob: dict[str, Any] = parsed if isinstance(parsed, dict) else {"_value": parsed}
        # Cloud JSONB rejects control chars / non-JSON-serializable values.
        # Fallback: stringify via repr if round-trip fails.
        try:
            json.dumps(data_blob, ensure_ascii=False)
        except (TypeError, ValueError):
            data_blob = {"_repr": repr(data_blob)}
        tags = _maybe_json(row.get("tags_json"), default=[])
        if not isinstance(tags, list):
            tags = []
        # Cloud `events.session` is INTEGER; local has heterogeneous data
        # (floats like 4.5, UUIDs). Coerce or drop into data.session_raw.
        session_raw = row.get("session")
        session_int: int | None
        try:
            session_int = int(session_raw) if session_raw is not None else None
        except (ValueError, TypeError):
            session_int = None
            if "session_raw" not in data_blob:
                data_blob["session_raw"] = session_raw
        return {
            "id": _row_uuid(tenant_id, table, row.get("id")),
            "brain_id": tenant_id,
            "type": row.get("type"),
            "source": row.get("source"),
            "session": session_int,
            "data": data_blob,
            "tags": tags,
            "created_at": row.get("ts"),
        }

    if table == "meta_rules":
        extras = {
            k: v
            for k, v in row.items()
            if k not in ("id", "tenant_id", "principle", "scope", "confidence")
        }
        raw_lesson_ids = _maybe_json(row.get("source_lesson_ids"), default=[])
        if raw_lesson_ids:
            extras["source_lesson_ids_raw"] = raw_lesson_ids
        visibility = row.get("visibility") or "private"
        if visibility not in ("private", "shared", "global"):
            visibility = "private"
        principle = row.get("principle") or ""
        title = (principle[:80] + "...") if len(principle) > 83 else (principle or "meta-rule")
        return {
            "id": _row_uuid(tenant_id, table, row.get("id")),
            "brain_id": tenant_id,
            "title": title,
            "principle": principle,
            "description": principle,
            "scope": row.get("scope"),
            "visibility": visibility,
            "confidence": row.get("confidence"),
            "data": extras,
        }

    if table == "correction_patterns":
        extras = {
            k: v
            for k, v in row.items()
            if k
            not in (
                "tenant_id",
                "session_id",
                "category",
                "severity",
                "representative_text",
                "created_at",
            )
        }
        raw_severity = row.get("severity")
        severity = (
            raw_severity
            if raw_severity in ("trivial", "minor", "moderate", "major", "rewrite")
            else "minor"
        )
        if severity != raw_severity:
            extras["severity_raw"] = raw_severity
        return {
            "id": _row_uuid(tenant_id, table, row.get("pattern_hash")),
            "brain_id": tenant_id,
            "session": row.get("session_id"),
            "category": row.get("category"),
            "severity": severity,
            "description": row.get("representative_text"),
            "data": extras,
            "created_at": row.get("created_at"),
        }

    out: dict[str, Any] = {"brain_id": tenant_id}
    for k, v in row.items():
        if k in ("tenant_id",):
            continue
        if k == "id" and isinstance(v, int):
            out["id"] = _row_uuid(tenant_id, table, v)
            continue
        out[k] = v
    return out


def enabled() -> bool:
    """True when the env flag is set AND both URL/key are present."""
    if os.environ.get(ENV_ENABLED, "").strip() not in ("1", "true", "yes"):
        return False
    return bool(_env_url() and _env_key())


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _sync_state_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_state'"
    ).fetchone()
    return row is not None


def _last_push_at(conn: sqlite3.Connection, tenant_id: str) -> str | None:
    """Read sync_state.last_push_at. Returns None on first push or pre-migration brain."""
    if not _sync_state_exists(conn):
        return None
    row = conn.execute(
        "SELECT last_push_at FROM sync_state WHERE brain_id = ?",
        (tenant_id,),
    ).fetchone()
    return row[0] if row and row[0] else None


def _mark_push(conn: sqlite3.Connection, tenant_id: str, when: str) -> None:
    """Advance sync_state.last_push_at. No-op on pre-migration brains."""
    if not _sync_state_exists(conn):
        return
    conn.execute(
        """
        INSERT INTO sync_state (brain_id, last_push_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(brain_id) DO UPDATE SET
            last_push_at = excluded.last_push_at,
            updated_at   = excluded.updated_at
        """,
        (tenant_id, when, when),
    )
    conn.commit()


def _rows_since(
    conn: sqlite3.Connection,
    table: str,
    tenant_id: str,
    since: str | None,
) -> list[dict[str, Any]]:
    """Read rows for the given table/tenant created or updated after ``since``.

    Uses whichever timestamp column the table has (``updated_at`` > ``created_at``
    > ``ts``). If none exist, returns all rows for the tenant (one-shot tables
    like ``rule_provenance``).
    """
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if "tenant_id" not in cols:
        return []

    ts_col = next((c for c in ("updated_at", "created_at", "ts") if c in cols), None)
    where = ["tenant_id = ?"]
    params: list[Any] = [tenant_id]
    if since and ts_col:
        where.append(f"{ts_col} > ?")
        params.append(since)

    # table is allowlisted via PUSH_TABLES; column list comes from PRAGMA.
    sql = f"SELECT * FROM {table} WHERE {' AND '.join(where)}"
    cur = conn.execute(sql, params)
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


_POST_BATCH_SIZE: Final[int] = 500

# Filename in brain_dir for last cloud push error. Surfaced by `gradata doctor`
# so constraint-violation silent-retry loops become visible without
# grepping logs.
_PUSH_ERROR_FILENAME: Final[str] = "cloud_push_error.json"


def _scrub_error_body(body: str) -> str:
    """Reduce a PostgREST error body to the subset safe to persist.

    Postgres ``23505`` errors echo the conflicting row's column values in the
    ``details``/``hint`` fields (e.g. ``"Key (id)=(uuid-value) already
    exists"``). ``cloud_push_error.json`` is read and printed by ``gradata
    doctor``, so leaking those values would surface tenant data on unrelated
    screens. Keeps ``code`` and the first 120 chars of ``message`` (enough for
    the constraint name); drops everything else.
    """
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return f"<non-json body, {len(body)} bytes>"
    if not isinstance(parsed, dict):
        return f"<non-object body, {len(body)} bytes>"
    safe: dict[str, Any] = {}
    for k in ("code", "message"):
        v = parsed.get(k)
        if isinstance(v, str):
            safe[k] = v[:120]
    return json.dumps(safe)


def _post(table: str, rows: list[dict[str, Any]]) -> tuple[int, dict | None]:
    """POST rows to Supabase PostgREST.

    Returns ``(accepted, error)``. ``error`` is ``None`` on success or
    ``{"code": int, "message": str, "constraint_violation": bool}`` on
    failure. Constraint violations (HTTP 409 / Postgres 23505) log at ERROR
    so the doctor + log aggregators catch silent retry loops.

    Applies ``_TABLE_REMAP`` so local table names that differ from the cloud
    (e.g. ``correction_patterns`` -> ``corrections``) route correctly. Batches
    large pushes because PostgREST rejects oversize bodies with opaque
    "Empty or invalid json" errors.
    """
    if not rows:
        return 0, None
    # Dedupe within the batch so ON CONFLICT DO UPDATE doesn't hit the same
    # row twice in a single statement (Postgres rejects that).
    seen: set[Any] = set()
    deduped: list[dict[str, Any]] = []
    for r in rows:
        key = r.get("id")
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        deduped.append(r)
    rows = deduped
    if len(rows) > _POST_BATCH_SIZE:
        total = 0
        first_error: dict | None = None
        for i in range(0, len(rows), _POST_BATCH_SIZE):
            count, err = _post(table, rows[i : i + _POST_BATCH_SIZE])
            total += count
            if err is not None and first_error is None:
                first_error = err
        return total, first_error
    cloud_table = _TABLE_REMAP.get(table, table)
    url = f"{_env_url().rstrip('/')}/rest/v1/{cloud_table}"
    key = _env_key()
    # Final scrub catches NUL / lone surrogates anywhere in the payload.
    body = json.dumps(_scrub(rows)).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # Upsert on primary key so repeat pushes are idempotent.
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        # URL is sourced from GRADATA_CLOUD_URL env; operator-controlled.
        with urllib.request.urlopen(req, timeout=30) as resp:
            if 200 <= resp.status < 300:
                return len(rows), None
            _log.warning("cloud_sync: %s returned HTTP %s", table, resp.status)
            return 0, {
                "code": resp.status,
                "message": f"HTTP {resp.status}",
                "constraint_violation": False,
            }
    except urllib.error.HTTPError as e:
        body_snippet = e.read()[:500].decode("utf-8", errors="replace")
        is_constraint = e.code == 409 or "23505" in body_snippet
        scrubbed = _scrub_error_body(body_snippet)
        if is_constraint:
            _log.error(
                "cloud_sync: %s constraint violation (HTTP %s): %s",
                table,
                e.code,
                scrubbed,
            )
        else:
            _log.warning(
                "cloud_sync: %s HTTP %s: %s",
                table,
                e.code,
                scrubbed,
            )
        return 0, {
            "code": e.code,
            "message": scrubbed,
            "constraint_violation": is_constraint,
        }
    except urllib.error.URLError as e:
        _log.warning("cloud_sync: %s network error: %s", table, e)
        return 0, {
            "code": 0,
            "message": f"network error: {e}",
            "constraint_violation": False,
        }


def _record_push_error(brain_dir: Path, error: dict) -> None:
    """Persist last cloud-push error so `gradata doctor` surfaces it.

    Atomic: writes to a tmp sibling then ``os.replace`` — on any platform
    concurrent readers never observe a truncated-then-rewritten file. This
    matters because daemon + MCP server can both call ``push()`` while a user
    runs ``gradata doctor``; a partial read would mask the violation as
    ``error file unreadable`` instead of surfacing the constraint.

    Best-effort: swallows OSError (read-only FS, permissions) because cloud
    push must not take down the caller on disk hiccups.
    """
    target = brain_dir / _PUSH_ERROR_FILENAME
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        payload = {**error, "recorded_at": _iso_now()}
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, target)
    except OSError as exc:
        _log.debug("cloud_sync: could not record push error: %s", exc)
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            logger.warning('Suppressed exception in _record_push_error', exc_info=True)


def _clear_push_error(brain_dir: Path) -> None:
    try:
        p = brain_dir / _PUSH_ERROR_FILENAME
        if p.exists():
            p.unlink()
    except OSError as exc:
        _log.debug("cloud_sync: could not clear push error: %s", exc)


def _resolve_db(brain_dir: str | Path) -> Path | None:
    """Return the SQLite path inside ``brain_dir`` if present, else None.

    Accepts either the brain directory OR the .db file directly so the caller
    can pass a BrainContext.db_path without a wrapping if-guard.
    """
    p = Path(brain_dir).expanduser().resolve()
    if p.is_file():
        return p if p.exists() else None
    for name in ("system.db", "brain.db"):
        candidate = p / name
        if candidate.exists():
            return candidate
    return None


def push(brain_dir: str | Path) -> dict[str, int]:
    """Push pending rows for this tenant to the cloud.

    Returns a dict mapping ``table -> rows_pushed``. A no-op when
    :func:`enabled` is False; safe to call unconditionally from hot paths.

    Watermark semantics: ``sync_state.last_push_at`` only advances when every
    table that had pending rows also successfully pushed them all. Any partial
    failure leaves the watermark unchanged so the next call retries.
    """
    if not enabled():
        return {}

    db_path = _resolve_db(brain_dir)
    if db_path is None:
        return {}
    brain = db_path.parent

    tenant_id = tenant_for(brain)
    conn = sqlite3.connect(db_path)
    try:
        since = _last_push_at(conn, tenant_id)
        pushed: dict[str, int] = {}
        all_ok = True
        started = _iso_now()
        last_error: dict | None = None
        for table in PUSH_TABLES:
            rows = _rows_since(conn, table, tenant_id, since)
            if not rows:
                continue
            transformed = []
            for r in rows:
                try:
                    transformed.append(_transform_row(table, r, tenant_id))
                except Exception as exc:
                    _log.warning("cloud_sync: skipping malformed row in %s: %s", table, exc)
                    all_ok = False
            if not transformed:
                continue
            accepted, error = _post(table, transformed)
            pushed[table] = accepted
            if error is not None and last_error is None:
                last_error = {**error, "table": table}
            if accepted != len(transformed):
                all_ok = False
        if pushed and all_ok:
            _mark_push(conn, tenant_id, started)
            _clear_push_error(brain)
        elif last_error is not None:
            _record_push_error(brain, last_error)
        return pushed
    finally:
        conn.close()


__all__ = ["PUSH_TABLES", "enabled", "push"]
