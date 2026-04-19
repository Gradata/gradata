"""Cloud sync client — opt-in metrics telemetry. POST /v1/telemetry/metrics (Bearer token);
aggregated MetricsWindow only, never raw corrections. Default OFF; corpus via CloudClient."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .._http import require_https

log = logging.getLogger(__name__)

_DEFAULT_API_BASE = os.environ.get("GRADATA_CLOUD_API_BASE", "https://api.gradata.ai")
_CONFIG_FILE_NAME = "cloud-config.json"


@dataclass
class CloudConfig:
    """Per-brain cloud sync configuration, persisted to brain_dir/cloud-config.json."""

    sync_enabled: bool = False
    token: str = ""
    api_base: str = _DEFAULT_API_BASE
    contribute_corpus: bool = False  # Separate, stricter opt-in
    last_sync_at: str = ""


def _config_path(brain_dir: Path) -> Path:
    return brain_dir / _CONFIG_FILE_NAME


def load_config(brain_dir: Path) -> CloudConfig:
    """Load per-brain cloud config, or return defaults if missing."""
    cfg_path = _config_path(brain_dir)
    if not cfg_path.is_file():
        return CloudConfig()
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return CloudConfig(
            sync_enabled=bool(data.get("sync_enabled", False)),
            token=str(data.get("token", "")),
            api_base=str(data.get("api_base", _DEFAULT_API_BASE)),
            contribute_corpus=bool(data.get("contribute_corpus", False)),
            last_sync_at=str(data.get("last_sync_at", "")),
        )
    except Exception as e:
        log.debug("cloud config load failed: %s", e)
        return CloudConfig()


def save_config(brain_dir: Path, cfg: CloudConfig) -> None:
    """Persist cloud config."""
    try:
        _config_path(brain_dir).write_text(
            json.dumps(asdict(cfg), indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.error("cloud config save failed: %s", e)


@dataclass
class TelemetryPayload:
    """Metrics payload sent to cloud — contains NO correction content."""

    brain_id: str
    session: int
    window_size: int
    sample_size: int
    rewrite_rate: float
    edit_distance_avg: float
    correction_density: float
    blandness_score: float
    rule_success_rate: float
    rule_misfire_rate: float
    rules_active: int
    rules_graduated: int
    sent_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class CloudClient:
    """Thin HTTP client for Gradata Cloud API.

    Only instantiate when user has opted into cloud sync. Defaults to noop
    behavior when config.sync_enabled is False.
    """

    def __init__(self, brain_dir: Path, config: CloudConfig | None = None):
        self.brain_dir = Path(brain_dir)
        self.config = config or load_config(self.brain_dir)
        require_https(self.config.api_base, "GRADATA_CLOUD_API_BASE")

    @property
    def enabled(self) -> bool:
        """True iff sync is on AND a token is configured."""
        return bool(self.config.sync_enabled and self.config.token.strip())

    def _post(self, path: str, payload: dict, timeout: float = 10.0) -> dict | None:
        """POST JSON to cloud, return response dict or None on failure. Never raises."""
        if not self.enabled:
            return None

        try:
            require_https(self.config.api_base, "api_base")
        except ValueError as exc:
            log.error("Refusing cloud POST — %s", exc)
            return None

        url = f"{self.config.api_base.rstrip('/')}{path}"
        data = json.dumps(payload).encode()
        headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Content-Type": "application/json",
            "User-Agent": "gradata-sdk/0.6",
        }

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode()
                return json.loads(body) if body else {}
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            log.debug("cloud POST %s failed: %s", path, e)
            return None
        except json.JSONDecodeError:
            log.debug("cloud response non-JSON for %s", path)
            return {}

    def sync_metrics(self, payload: TelemetryPayload) -> bool:
        """Send metrics snapshot to cloud dashboard. Returns True on success.

        Idempotent: cloud side dedups by (brain_id, session, sent_at).
        """
        if not self.enabled:
            return False
        result = self._post("/v1/telemetry/metrics", asdict(payload))
        if result is not None:
            self.config.last_sync_at = payload.sent_at
            save_config(self.brain_dir, self.config)
            return True
        return False

    def contribute_corpus(self, anonymized_patterns: list[dict]) -> bool:
        """Opt-in: contribute anonymized graduated patterns to the cloud corpus.

        Privacy: only patterns at PATTERN/RULE confidence (>=0.60) are eligible.
        Caller must have already anonymized (no raw correction text, no PII).
        This is a SEPARATE opt-in from metrics sync — requires both flags true.
        """
        if not self.enabled or not self.config.contribute_corpus:
            return False
        result = self._post("/v1/corpus/contribute", {"patterns": anonymized_patterns})
        return result is not None


def sync_metrics(brain_dir: Path, payload: TelemetryPayload) -> bool:
    """Convenience: load config for brain_dir and sync one metrics payload.

    Returns False silently if sync is disabled or cloud is unreachable.
    Never raises — cloud sync must never block the learning loop.
    """
    try:
        client = CloudClient(brain_dir)
        return client.sync_metrics(payload)
    except Exception as e:
        log.debug("sync_metrics wrapper failed: %s", e)
        return False
