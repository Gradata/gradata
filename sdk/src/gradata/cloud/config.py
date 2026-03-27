"""
Cloud configuration — manages Gradata API credentials and sync settings.
==========================================================================
Configuration is read from (in priority order):
  1. Explicit arguments to CloudClient()
  2. Environment variables (GRADATA_API_KEY, GRADATA_ENDPOINT)
  3. Config file at ~/.gradata/config.json
  4. Brain-local config at <brain_dir>/.cloud.json
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".gradata"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class CloudConfig:
    """Gradata Cloud configuration."""

    api_key: str = ""
    endpoint: str = "https://api.gradata.com/v1"
    auto_sync: bool = True          # Sync at session start/end
    sync_interval_minutes: int = 30  # Background sync interval
    include_prospects: bool = False   # Exclude prospect data from sync by default

    @classmethod
    def load(cls, brain_dir: Path | None = None) -> "CloudConfig":
        """Load config from all sources, merged by priority."""
        config = cls()

        # 4. Brain-local config (lowest priority)
        if brain_dir:
            local_path = Path(brain_dir) / ".cloud.json"
            if local_path.exists():
                config._merge(json.loads(local_path.read_text(encoding="utf-8")))

        # 3. Global config file
        if CONFIG_FILE.exists():
            config._merge(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))

        # 2. Environment variables (higher priority)
        if os.environ.get("GRADATA_API_KEY"):
            config.api_key = os.environ["GRADATA_API_KEY"]
        if os.environ.get("GRADATA_ENDPOINT"):
            config.endpoint = os.environ["GRADATA_ENDPOINT"]

        return config

    def save(self, brain_dir: Path | None = None) -> None:
        """Save config to brain-local or global location."""
        data = {
            "endpoint": self.endpoint,
            "auto_sync": self.auto_sync,
            "sync_interval_minutes": self.sync_interval_minutes,
            "include_prospects": self.include_prospects,
        }
        # Never write API key to brain-local (it would be committed to git)
        if brain_dir:
            path = Path(brain_dir) / ".cloud.json"
        else:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            path = CONFIG_FILE
            data["api_key"] = self.api_key

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _merge(self, data: dict) -> None:
        """Merge a dict into this config (only known fields)."""
        for key in ("api_key", "endpoint", "auto_sync",
                     "sync_interval_minutes", "include_prospects"):
            if key in data:
                setattr(self, key, data[key])
