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

import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("gradata.cloud")

DEFAULT_ENDPOINT = "https://api.gradata.com/v1"
ENV_API_KEY = "GRADATA_API_KEY"
ENV_ENDPOINT = "GRADATA_ENDPOINT"


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
        self.endpoint = (
            endpoint or os.environ.get(ENV_ENDPOINT, "") or DEFAULT_ENDPOINT
        ).rstrip("/")
        if self.endpoint and not self.endpoint.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(self.endpoint)
            if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError(f"GRADATA_ENDPOINT must use HTTPS: {self.endpoint}")
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
            resp = self._post("/brains/connect", {
                "brain_name": manifest.get("metadata", {}).get("name", self.brain_dir.name),
                "domain": manifest.get("metadata", {}).get("domain", ""),
                "manifest": manifest,
            })
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
    ) -> dict:
        """Send correction to cloud for server-side graduation.

        The cloud runs the full pipeline: diff -> classify -> extract
        patterns -> graduate -> update rules. Returns the same event
        dict format as local Brain.correct().
        """
        try:
            return self._post("/brains/correct", {
                "brain_id": self._brain_id,
                "draft": draft[:2000],
                "final": final[:2000],
                "category": category,
                "context": context,
                "session": session,
            })
        except Exception as e:
            logger.warning("Cloud correct() failed, falling back to local: %s", e)
            raise  # Let Brain.correct() catch and fall back

    def apply_rules(self, task: str, context: dict | None = None) -> str:
        """Get applicable rules from cloud (server-side graduation state).

        Returns formatted rules string for prompt injection.
        """
        try:
            resp = self._post("/brains/rules", {
                "brain_id": self._brain_id,
                "task": task,
                "context": context,
            })
            return resp.get("rules_text", "")
        except Exception as e:
            logger.warning("Cloud apply_rules() failed, falling back to local: %s", e)
            raise

    def sync(self) -> dict:
        """Sync local brain state to cloud.

        Uploads new events since last sync. Returns sync status.
        """
        if not self.connected:
            return {"status": "not_connected"}

        try:
            return self._post("/brains/sync", {
                "brain_id": self._brain_id,
                "manifest": self._read_local_manifest(),
            })
        except Exception as e:
            logger.warning("Sync failed: %s", e)
            return {"status": "error", "error": str(e)}

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
        except URLError as e:
            raise ConnectionError(f"Cloud API request failed: {e}") from e

    def _read_local_manifest(self) -> dict:
        """Read the local brain.manifest.json if it exists."""
        manifest_path = self.brain_dir / "brain.manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
