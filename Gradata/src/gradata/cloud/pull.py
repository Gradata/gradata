"""Client for ``GET /events/pull`` — ships disabled in Phase 1.

The contract is frozen in ``docs/specs/events-pull-contract.md``. This module
exists in Phase 1 so every field of the signature and return shape is locked
in code before the server implementation ships.

Behavior in Phase 1:
  - Server returns ``501 Not Implemented`` → returns ``{"status": "disabled_server_side", ...}``.
  - Server returns ``200 OK`` → raises :class:`NotImplementedError` so
    nothing accidentally gets merged into the local brain before the
    materializer ships in Phase 2.

Once the materializer lands, the ``200 OK`` branch will be wired through a
merge path guarded by ``docs/specs/merge-semantics.md``.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

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
) -> dict[str, Any]:
    """Pull pending events from cloud. See ``docs/specs/events-pull-contract.md``.

    Returns a summary dict with a stable ``status`` field:
      - ``ok``                  — events successfully pulled (Phase 2+).
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
        summary["status"] = "error"
        summary["reason"] = "no_db"
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

    api_base = (config.api_base or "").rstrip("/")
    try:
        require_https(api_base, "api_base")
    except ValueError as exc:
        log.error("events/pull refused — %s", exc)
        summary["status"] = "error"
        summary["reason"] = "https_required"
        return summary

    params: dict[str, Any] = {
        "brain_id": tenant_for(brain),
        "device_id": get_or_create_device_id(brain),
        "limit": max(1, min(int(limit), 1000)),
    }
    if rebuild_from:
        params["rebuild_from"] = rebuild_from
    if cursor:
        params["cursor"] = cursor
    if include_archived:
        params["include_archived"] = "true"

    url = f"{api_base}/events/pull?{urlencode(params)}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {resolved}",
            "Accept": "application/json",
            "User-Agent": "gradata-sdk/0.6",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
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

    # 200 OK path — intentionally not wired in Phase 1.
    # The materializer + merge-semantics are the prerequisite for merging
    # pulled events into local state. Shipping a "works partially" path
    # would silently corrupt brains. Raise loudly instead.
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {}
    raise NotImplementedError(
        "events/pull merge path is Phase 2. See docs/specs/events-pull-contract.md §7. "
        f"Server returned {len(parsed.get('events', []) or [])} events but merge is not wired."
    )
