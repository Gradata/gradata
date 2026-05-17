"""Background sync worker — drains the local ``sync_queue`` to the cloud.

Day 3 of #194. A :class:`SyncWorker` runs as a daemon thread inside the
Brain process. On each tick (default 30s) it:

1. Opens a fresh sqlite connection to ``<brain>/system.db``.
2. Reads up to 50 pending rows via :func:`gradata._sync_queue.peek_pending`.
3. POSTs each payload to the cloud ingest endpoint
   (``GRADATA_CLOUD_INGEST_URL`` or ``https://api.gradata.ai/api/v1/ingest``).
4. On 2xx (including ``deduplicated=true``) → ``mark_synced``.
5. On 4xx other than 429 → ``mark_failed`` (permanent; treated as
   not-pending by re-marking; payload kept for forensics but not retried).
6. On 5xx / network errors → ``mark_failed`` (transient, retried next tick).
7. On 429 → ``mark_failed`` and bail out of the tick (back off until next).

Concurrency rules:
* Daemon thread; never blocks process exit.
* Never holds the brain's locks — owns its own connection-per-call.
* :meth:`stop(drain=True)` runs one final synchronous tick before returning,
  so :meth:`gradata.brain.Brain.close` can flush pending corrections on exit.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from gradata import _sync_queue

__all__ = ["SyncWorker"]

logger = logging.getLogger("gradata.sync_worker")

_DEFAULT_INGEST_URL = "https://api.gradata.ai/api/v1/ingest"
_TICK_BATCH = 50
_HTTP_TIMEOUT = 30.0
# 4xx status codes that mean "don't retry, this row is poison".
_PERMANENT_4XX = {400, 401, 403, 404, 410, 422}


class SyncWorker:
    """Drain ``sync_queue`` to the cloud ``/api/v1/ingest`` endpoint.

    Args:
        brain_dir: Path to the brain directory (contains ``system.db``).
        api_key: Bearer token for the cloud API.
        ingest_url: Full URL of the cloud ingest endpoint.
        tick_sec: Interval between drain attempts.
    """

    def __init__(
        self,
        brain_dir: Path,
        api_key: str,
        ingest_url: str = _DEFAULT_INGEST_URL,
        tick_sec: float = 30.0,
    ) -> None:
        self.brain_dir = Path(brain_dir)
        self.api_key = api_key
        self.ingest_url = ingest_url
        self.tick_sec = float(tick_sec)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    # ── lifecycle ────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the daemon thread. Idempotent."""
        if self._started:
            return
        self._started = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="gradata-sync-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self, drain: bool = True) -> None:
        """Signal shutdown and (optionally) run one final synchronous tick.

        Safe to call multiple times.
        """
        self._stop_event.set()
        if drain:
            try:
                self._tick()
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("final drain tick failed: %s", exc)
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.tick_sec))
            self._thread = None
        self._started = False

    # ── thread loop ──────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning("sync tick failed: %s", exc, exc_info=True)
            # Wait tick_sec OR until shutdown — wake immediately on stop().
            self._stop_event.wait(self.tick_sec)

    # ── single tick ──────────────────────────────────────────────────

    def _tick(self) -> None:
        db_path = self.brain_dir / "system.db"
        if not db_path.exists():
            return

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = _sync_queue.peek_pending(conn, limit=_TICK_BATCH)
            if not rows:
                return

            for row in rows:
                if self._stop_event.is_set():
                    # On shutdown, only finish work if we're inside the
                    # explicit drain path (stop calls _tick directly).
                    # Otherwise bail early — main thread already set the
                    # event and any in-flight POST would just delay exit.
                    if threading.current_thread() is not self._thread:
                        # we are inside stop(drain=True) → keep going
                        pass
                    else:
                        return

                row_id = int(row["id"])
                payload = row.get("payload") or {}
                try:
                    status, _resp = self._post_one(payload)
                except urllib.error.HTTPError as exc:
                    status = int(exc.code)
                    body_preview = _safe_body_preview(exc)
                    if status == 429:
                        _sync_queue.mark_failed(conn, [row_id], f"http 429: {body_preview}")
                        # Back off — stop this tick entirely.
                        return
                    if status in _PERMANENT_4XX:
                        # Mark synced so we don't retry forever. The row
                        # remains in the table for forensics. last_error
                        # is set via a preceding mark_failed for context.
                        _sync_queue.mark_failed(
                            conn, [row_id], f"http {status} (permanent): {body_preview}"
                        )
                        _sync_queue.mark_synced(conn, [row_id])
                        continue
                    # 5xx and anything else → transient, retry next tick.
                    _sync_queue.mark_failed(conn, [row_id], f"http {status}: {body_preview}")
                    continue
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    _sync_queue.mark_failed(conn, [row_id], f"network: {exc}")
                    continue
                except Exception as exc:  # pragma: no cover — defensive
                    _sync_queue.mark_failed(conn, [row_id], f"unexpected: {exc}")
                    continue

                # 2xx happy path (including deduplicated=true)
                if 200 <= status < 300:
                    try:
                        _sync_queue.mark_synced(conn, [row_id])
                    except Exception as exc:
                        # At-least-once: don't lose the row if the DB
                        # write fails. It will retry next tick (the cloud
                        # is idempotent on event_id).
                        logger.warning(
                            "mark_synced failed for row %s: %s",
                            row_id,
                            exc,
                            exc_info=True,
                        )
                        # Re-raise so the parent retry path sees it.
                        raise
                else:
                    _sync_queue.mark_failed(conn, [row_id], f"unexpected status {status}")
        finally:
            conn.close()

    # ── http ─────────────────────────────────────────────────────────

    def _post_one(self, payload: dict) -> tuple[int, dict]:
        """POST a single payload to the ingest endpoint.

        Returns ``(status, response_dict)``. Raises
        :class:`urllib.error.HTTPError` on non-2xx (urllib's default).
        """
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.ingest_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "gradata-sync-worker/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:  # noqa: S310
            raw = resp.read()
            status = int(resp.status)
        try:
            parsed: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:500].decode("utf-8", errors="replace")}
        if not isinstance(parsed, dict):
            parsed = {"_value": parsed}
        return status, parsed


def _safe_body_preview(exc: urllib.error.HTTPError) -> str:
    """Best-effort short string of an HTTPError body for log/error storage."""
    try:
        raw = exc.read() or b""
    except Exception:
        return ""
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return ""
    return text[:200]
