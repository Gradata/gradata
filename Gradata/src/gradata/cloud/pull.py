"""Client for ``GET /events/pull`` with Phase 2 merge wiring.

The contract is frozen in ``docs/specs/events-pull-contract.md``.

Behavior:
  - Server returns ``501 Not Implemented`` → ``{"status": "disabled_server_side", ...}``.
  - Server returns ``410 Gone`` → ``{"status": "error", "reason": "rewind_beyond_retention"}``.
  - Server returns ``200 OK`` with ``apply=False`` (default) → materializes
    the stream and returns counts/watermark without touching local state.
  - Server returns ``200 OK`` with ``apply=True`` → materializes, applies
    to ``lessons.md``, and emits ``RULE_CONFLICT`` events for any Tier 2
    conflicts (see ``docs/specs/merge-semantics.md``).

``apply=False`` is the safe default so accidental calls during CI / smoke
tests never mutate a brain.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from gradata import __version__ as _sdk_version
from gradata._http import require_https
from gradata._migrations.device_uuid import get_or_create_device_id
from gradata._tenant import tenant_for
from gradata.cloud import _credentials as _creds
from gradata.cloud.sync import load_config

log = logging.getLogger(__name__)


def pull_events(
    brain_dir: str | Path,
    *,
    rebuild_from: str | None = None,
    limit: int = 500,
    cursor: str | None = None,
    include_archived: bool = False,
    timeout: float = 30.0,
    apply: bool = False,
) -> dict[str, Any]:
    """Pull pending events from cloud. See ``docs/specs/events-pull-contract.md``.

    When ``apply=False`` (default) the pulled stream is materialized and
    summarized but local lessons are **not** mutated and no conflict events
    are emitted — callers preview the delta before committing. When
    ``apply=True`` the materialized state is written to ``lessons.md`` and
    ``RULE_CONFLICT`` events are emitted for any Tier 2 conflicts.

    Returns a summary dict with a stable ``status`` field:
      - ``ok``                  — events successfully pulled.
      - ``disabled_server_side`` — server returned 501.
      - ``disabled``            — local ``sync_enabled: false``.
      - ``kill_switch``         — ``GRADATA_CLOUD_SYNC_DISABLE`` is set.
      - ``no_credential``       — no key resolves.
      - ``no_db``               — brain has no ``system.db``.
      - ``error``               — with ``reason`` field; see ``docs/errors.md``.
    """
    summary: dict[str, Any] = {
        "status": "ok",
        "events_pulled": 0,
        "watermark": None,
        "end_of_stream": True,
    }

    brain = Path(brain_dir).resolve()
    db = brain / "system.db"
    if not db.is_file():
        summary["status"] = "no_db"
        return summary

    if _creds.kill_switch_set():
        summary["status"] = "kill_switch"
        return summary

    try:
        config = load_config(brain)
    except Exception as exc:
        log.debug("events/pull: config load failed: %s", exc)
        summary["status"] = "error"
        summary["reason"] = "config_load_failed"
        return summary

    if not config.sync_enabled:
        summary["status"] = "disabled"
        return summary

    resolved = config.token.strip() or _creds.resolve_credential()
    if not resolved:
        summary["status"] = "no_credential"
        return summary

    # Route through the shared endpoint resolver so ``GRADATA_ENDPOINT`` /
    # ``GRADATA_CLOUD_API_BASE`` env overrides take effect for pull the same
    # way they do for push and the CLI. Prior to this, pull only honored
    # ``config.api_base``, which meant env-only deployments silently targeted
    # an outdated endpoint.
    api_base = _creds.resolve_endpoint(fallback=config.api_base or "").rstrip("/")
    try:
        require_https(api_base, "api_base")
    except ValueError as exc:
        log.error("events/pull refused — %s", exc)
        summary["status"] = "error"
        summary["reason"] = "https_required"
        return summary

    # Mirror push.py: identity resolution can raise OSError on a corrupted
    # brain dir, and the public contract is "never raise — return summary".
    try:
        resolved_tenant = tenant_for(brain)
        resolved_device = get_or_create_device_id(brain)
    except OSError as exc:
        log.debug("events/pull: identity resolution failed: %s", exc)
        summary["status"] = "error"
        summary["reason"] = "identity_error"
        return summary

    base_params: dict[str, Any] = {
        "brain_id": resolved_tenant,
        "device_id": resolved_device,
        "limit": max(1, min(int(limit), 1000)),
    }

    # Auto-resume: when the caller didn't pin a rewind point or cursor,
    # pick up from the last persisted watermark so successive pulls
    # stream incrementally without re-downloading history.
    if not rebuild_from and not cursor:
        from gradata.cloud._sync_state import get_pull_cursor

        persisted = get_pull_cursor(
            db,
            tenant_id=base_params["brain_id"],
            device_id=base_params["device_id"],
        )
        if persisted:
            cursor = persisted

    all_events: list[dict[str, Any]] = []
    final_watermark: str | None = None
    end_of_stream = True
    pages_fetched = 0
    PAGE_CAP = 50  # bound for runaway servers; 50 × 1000 = 50k events/call

    next_cursor = cursor
    pending_rebuild_from = rebuild_from
    while pages_fetched < PAGE_CAP:
        page_params = dict(base_params)
        if pending_rebuild_from:
            page_params["rebuild_from"] = pending_rebuild_from
            pending_rebuild_from = None  # only sent on the first page
        if next_cursor:
            page_params["cursor"] = next_cursor
        if include_archived:
            page_params["include_archived"] = "true"

        url = f"{api_base}/events/pull?{urlencode(page_params)}"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {resolved}",
                "Accept": "application/json",
                "User-Agent": f"gradata-sdk/{_sdk_version}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_body = resp.read()
            body = raw_body.decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 501:
                summary["status"] = "disabled_server_side"
                return summary
            if e.code == 410:
                summary["status"] = "error"
                summary["reason"] = "rewind_beyond_retention"
                return summary
            log.warning("events/pull HTTP %s: %s", e.code, e.reason)
            summary["status"] = "error"
            summary["reason"] = f"http_{e.code}"
            return summary
        except (urllib.error.URLError, OSError) as exc:
            log.debug("events/pull transport error: %s", exc)
            summary["status"] = "error"
            summary["reason"] = "transport"
            return summary
        except UnicodeDecodeError as exc:
            # A non-UTF-8 body would otherwise escape the transport/HTTP guards
            # and crash the caller — public contract is "never raise". Treat
            # garbage bytes as a malformed response.
            log.warning("events/pull: response body is not valid UTF-8: %s", exc)
            summary["status"] = "error"
            summary["reason"] = "malformed_response"
            return summary

        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            log.warning("events/pull: server returned non-JSON body")
            summary["status"] = "error"
            summary["reason"] = "malformed_response"
            return summary

        # Validate shape — valid JSON in the wrong shape (``[]``, scalar,
        # nested non-list events) would otherwise crash materialize() or
        # silently skip events.
        if not isinstance(parsed, dict):
            log.warning("events/pull: server returned non-object JSON")
            summary["status"] = "error"
            summary["reason"] = "malformed_response"
            return summary
        page_events = parsed.get("events") or []
        if not isinstance(page_events, list) or any(
            not isinstance(evt, dict) for evt in page_events
        ):
            log.warning("events/pull: events field is not a list of objects")
            summary["status"] = "error"
            summary["reason"] = "malformed_response"
            return summary
        all_events.extend(page_events)
        page_watermark = parsed.get("watermark")
        # Reject the wrong types outright — ``bool()`` would coerce the string
        # ``"false"`` to True, and a dict/list watermark would later be
        # ``str(...)``-ified and persisted as garbage. Force the caller onto
        # the malformed_response path instead.
        if page_watermark is not None and not isinstance(page_watermark, str):
            log.warning("events/pull: watermark field is not a string")
            summary["status"] = "error"
            summary["reason"] = "malformed_response"
            return summary
        page_end_of_stream = parsed.get("end_of_stream", True)
        if not isinstance(page_end_of_stream, bool):
            log.warning("events/pull: end_of_stream field is not a boolean")
            summary["status"] = "error"
            summary["reason"] = "malformed_response"
            return summary
        if page_watermark:
            final_watermark = page_watermark
        end_of_stream = page_end_of_stream
        pages_fetched += 1

        if end_of_stream:
            break
        # Advance to the next page using the watermark as cursor; if the
        # server forgot to send one, stop rather than spin forever.
        if not page_watermark:
            break
        next_cursor = page_watermark

    summary["events_pulled"] = len(all_events)
    summary["watermark"] = final_watermark
    summary["end_of_stream"] = end_of_stream
    summary["pages_fetched"] = pages_fetched

    # Materialize regardless of apply — gives the caller a preview of
    # state/conflict counts without writing anything.
    from gradata.cloud.materializer import CONFLICT_THRESHOLD, materialize

    threshold = config.conflict_threshold or CONFLICT_THRESHOLD
    mat = materialize(all_events, threshold=threshold)
    summary["conflict_threshold"] = threshold
    summary["rules_materialized"] = len(mat.rules)
    summary["conflicts"] = len(mat.conflicts)
    summary["applied"] = False

    if apply:
        from gradata._db import write_lessons_safe
        from gradata.cloud._apply_materialized import (
            apply_to_lessons,
            emit_conflict_events,
        )
        from gradata.cloud._sync_state import update_pull_cursor
        from gradata.enhancements.self_improvement import format_lessons, parse_lessons

        if mat.rules or mat.conflicts:
            lessons_path = brain / "lessons.md"
            existing = (
                parse_lessons(lessons_path.read_text(encoding="utf-8"))
                if lessons_path.is_file()
                else []
            )
            merged = apply_to_lessons(existing, mat)
            try:
                write_lessons_safe(lessons_path, format_lessons(merged))
            except Exception as exc:
                log.error("events/pull: lessons write failed: %s", exc)
                summary["status"] = "error"
                summary["reason"] = "lessons_write_failed"
                return summary

            summary["conflict_events_emitted"] = emit_conflict_events(mat)

        # Persist the pull watermark whenever the caller committed to an
        # apply pass — even if the page contained no rules or conflicts.
        # Without this, a pull that returned only tombstones or events from
        # other devices would never advance the cursor and the next pull
        # would re-fetch the same stream indefinitely.
        watermark = summary.get("watermark")
        persisted = True
        if watermark:
            try:
                persisted = bool(
                    update_pull_cursor(
                        db,
                        tenant_id=base_params["brain_id"],
                        device_id=base_params["device_id"],
                        cursor=str(watermark),
                    )
                )
            except Exception as exc:
                log.debug("events/pull: watermark persist failed: %s", exc)
                persisted = False
            if not persisted:
                # Surface the failure so callers don't treat the run as a
                # clean success and schedule follow-ups based on a cursor
                # that never landed. Skip the success telemetry too.
                summary["status"] = "error"
                summary["reason"] = "watermark_persist_failed"
                return summary

        # ``applied`` reflects "the apply path ran end-to-end", not "the
        # lessons write touched at least one byte". A pull that materialized
        # to an empty delta still counts — callers need to distinguish that
        # from ``apply=False`` preview mode. Set it only after every hard
        # failure path (lessons_write_failed, watermark_persist_failed) has
        # had its chance to short-circuit.
        summary["applied"] = True

        try:
            from gradata._events import emit as _emit

            _emit(
                "CLOUD_SYNC_COMPLETED",
                "cloud_pull",
                {
                    "events_pulled": summary["events_pulled"],
                    "rules_materialized": summary["rules_materialized"],
                    "conflicts": summary["conflicts"],
                    "pages_fetched": summary["pages_fetched"],
                    "conflict_threshold": summary["conflict_threshold"],
                    "watermark": summary.get("watermark") or "",
                    "status": summary["status"],
                },
                [],
            )
        except Exception as exc:
            log.debug("CLOUD_SYNC_COMPLETED emit failed: %s", exc)

    return summary
