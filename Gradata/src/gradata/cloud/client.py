"""
CloudClient — API client for Gradata Cloud.
==============================================
Handles authentication, brain sync, and routing of graduation
pipeline calls to the cloud API.

The client is designed to be a drop-in replacement for local
enhancements. When connected, Brain.correct() and Brain.apply_brain_rules()
route through this client instead of running locally.

All network calls are synchronous (urllib, no async deps) to maintain
the zero-dependency guarantee for the base SDK.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gradata._http import require_https

logger = logging.getLogger("gradata.cloud")

DEFAULT_ENDPOINT = "https://api.gradata.ai/api/v1"
ENV_API_KEY = "GRADATA_API_KEY"
ENV_ENDPOINT = "GRADATA_ENDPOINT"


class _TooLargeError(Exception):
    """Raised when the server returns HTTP 413 (batch too large)."""


class CloudClient:
    """Client for Gradata Cloud API.

    Provides server-side graduation, quality scoring, and marketplace
    access. Falls back gracefully when the cloud is unreachable.
    """

    def __init__(
        self,
        brain_dir: str | Path,
        api_key: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self.brain_dir = Path(brain_dir).resolve()
        self.api_key = api_key or os.environ.get(ENV_API_KEY, "")
        self.endpoint = (endpoint or os.environ.get(ENV_ENDPOINT, "") or DEFAULT_ENDPOINT).rstrip(
            "/"
        )
        if self.endpoint:
            require_https(self.endpoint, "GRADATA_ENDPOINT")
        self.connected = False
        self._brain_id: str | None = None

    def connect(self) -> bool:
        """Authenticate and register this brain with the cloud.

        Returns True if connection succeeded.
        """
        if not self.api_key:
            logger.warning("No API key provided. Set %s or pass api_key=.", ENV_API_KEY)
            return False

        try:
            manifest = self._read_local_manifest()
            resp = self._post(
                "/brains/connect",
                {
                    "brain_name": manifest.get("metadata", {}).get("name", self.brain_dir.name),
                    "domain": manifest.get("metadata", {}).get("domain", ""),
                    "manifest": manifest,
                },
            )
            self._brain_id = resp.get("brain_id")
            self.connected = True
            logger.info("Connected to Gradata Cloud: brain_id=%s", self._brain_id)
            return True
        except Exception as e:
            logger.warning("Cloud connection failed: %s", e)
            self.connected = False
            return False

    def correct(
        self,
        draft: str,
        final: str,
        category: str | None = None,
        context: dict | None = None,
        session: int | None = None,
        applies_to: str | None = None,
    ) -> dict:
        """Send correction to cloud for server-side graduation.

        The cloud runs the full pipeline: diff -> classify -> extract
        patterns -> graduate -> update rules. Returns the same event
        dict format as local Brain.correct().

        ``applies_to`` is an optional free-form scope token (e.g.
        ``"client:acme"``) forwarded to the cloud payload for persistence.
        """
        payload = {
            "brain_id": self._brain_id,
            "draft": draft[:2000],
            "final": final[:2000],
            "category": category,
            "context": context,
            "session": session,
        }
        if applies_to:
            payload["applies_to"] = applies_to
        try:
            return self._post("/brains/correct", payload)
        except Exception as e:
            logger.warning("Cloud correct() failed, falling back to local: %s", e)
            raise  # Let Brain.correct() catch and fall back

    # REMOVED: apply_rules() — pulling rules from cloud is a security risk.
    # A compromised cloud server could inject malicious prompt instructions.
    # Rules are ALWAYS computed locally from the brain's own lessons.

    def sync(self, batch_size: int = 500) -> int:
        """Sync raw events from events.jsonl to cloud with watermark cursor.

        Reads events.jsonl, filters to events newer than the last watermark,
        and batches them to /sync in chunks of `batch_size`. Advances the
        cursor after each successful batch so the method is resumable and
        idempotent (server upserts on event_id).

        Returns total number of events ingested (0 if not connected or no events).
        """
        if not self.connected:
            return 0

        events_path = self.brain_dir / "events.jsonl"
        if not events_path.exists():
            return 0

        state = self._read_sync_state()
        last_watermark = state.get("last_sync_at", "")

        try:
            all_lines = events_path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            logger.warning("Sync: cannot read events.jsonl: %s", e)
            return 0

        pending: list[dict] = []
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = ev.get("ts", "")
            # Coerce non-string ts (e.g. float epoch) to string for safe compare
            if not isinstance(ts, str):
                ts = str(ts)
                ev["ts"] = ts
            if ts > last_watermark:
                pending.append(ev)

        if not pending:
            logger.debug("Sync: no new events since watermark=%r", last_watermark)
            return 0

        manifest = self._read_local_manifest()
        total_ingested = 0
        offset = 0
        current_batch = batch_size

        while offset < len(pending):
            chunk = pending[offset : offset + current_batch]
            payload_events = [self._format_event(ev) for ev in chunk]

            try:
                resp = self._post(
                    "/sync",
                    {
                        "brain_name": manifest.get("metadata", {}).get("name", self.brain_dir.name),
                        "manifest": manifest,
                        "events": payload_events,
                        "cursor": last_watermark,
                    },
                )
            except _TooLargeError:
                # Server returned 413 — halve the batch and retry this chunk.
                current_batch = max(1, current_batch // 2)
                logger.warning(
                    "Sync: 413 from server — reducing batch size to %d", current_batch
                )
                continue
            except Exception as e:
                logger.error("Sync: POST failed at offset=%d: %s", offset, e)
                return total_ingested

            ingested = resp.get("ingested_count", 0)
            watermark = resp.get("new_watermark")
            total_ingested += ingested
            if watermark:
                last_watermark = watermark
                self._write_sync_state({"last_sync_at": last_watermark})

            offset += len(chunk)
            # Reset batch size to default for next chunk after a 413 recovery.
            current_batch = batch_size

        logger.info(
            "Sync: ingested %d events (watermark=%r)", total_ingested, last_watermark
        )
        return total_ingested

    # ── Sync state helpers ────────────────────────────────────────────────────

    def _read_sync_state(self) -> dict:
        state_path = self.brain_dir / ".gradata-sync-state.json"
        if state_path.exists():
            try:
                return json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _write_sync_state(self, state: dict) -> None:
        state_path = self.brain_dir / ".gradata-sync-state.json"
        try:
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("Sync: cannot write sync state: %s", e)

    @staticmethod
    def _format_event(ev: dict) -> dict:
        """Convert an events.jsonl row to the /sync EventPayload shape.

        Computes a deterministic event_id from (ts, type, source) so the
        server can upsert idempotently on (brain_id, event_id).
        """
        ts = ev.get("ts", "")
        if not isinstance(ts, str):
            ts = str(ts)
        event_type = ev.get("type", "")
        source = ev.get("source", "")
        raw = f"{ts}:{event_type}:{source}"
        event_id = hashlib.sha256(raw.encode()).hexdigest()[:32]
        # Coerce session to int|None — server schema rejects floats/strings
        session_raw = ev.get("session")
        session_val: int | None
        try:
            if session_raw is None:
                session_val = None
            elif isinstance(session_raw, bool):
                session_val = None
            elif isinstance(session_raw, int):
                session_val = session_raw
            elif isinstance(session_raw, float):
                session_val = int(session_raw)
            else:
                session_val = int(str(session_raw))
        except (ValueError, TypeError):
            session_val = None
        return {
            "event_id": event_id,
            "type": event_type,
            "source": source,
            "data": ev.get("data", {}),
            "tags": ev.get("tags", []),
            "session": session_val,
            "created_at": ts or None,
        }

    # ── Internal helpers ──────────────────────────────────────────────

    def _post(self, path: str, data: dict) -> dict[str, Any]:
        """Make an authenticated POST request to the cloud API."""
        url = f"{self.endpoint}{path}"
        body = json.dumps(data, default=str).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "gradata-sdk/0.1.0",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 413:
                raise _TooLargeError() from e
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                body = ""
            raise ConnectionError(f"Cloud API request failed: {e} body={body}") from e
        except URLError as e:
            raise ConnectionError(f"Cloud API request failed: {e}") from e

    def _read_local_manifest(self) -> dict:
        """Read the local brain.manifest.json if it exists."""
        manifest_path = self.brain_dir / "brain.manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(
                    "Failed to parse %s: %s — sending empty manifest to cloud",
                    manifest_path,
                    exc,
                )
                return {}
        return {}
