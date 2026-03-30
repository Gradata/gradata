"""Brain mixin — Cloud connection methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainCloudMixin:
    """Cloud connectivity for Brain."""

    # ── Cloud ──────────────────────────────────────────────────────────

    def connect_cloud(self, api_key: str = None, endpoint: str = None) -> "Brain":
        """Connect this brain to Gradata Cloud for server-side graduation.

        When connected, correct() and apply_brain_rules() route to the cloud
        API instead of running enhancements locally. The cloud runs the full
        graduation pipeline, meta-learning, and marketplace readiness scoring.

        Falls back to local mode if connection fails.

        Args:
            api_key: Gradata API key. If None, reads from GRADATA_API_KEY env var.
            endpoint: Cloud API endpoint. Defaults to https://api.gradata.com/v1.
        """
        import logging
        logger = logging.getLogger("gradata")

        try:
            from gradata.cloud import CloudClient
            self._cloud = CloudClient(
                brain_dir=self.dir,
                api_key=api_key,
                endpoint=endpoint,
            )
            self._cloud.connect()
        except ImportError:
            logger.warning("Cloud client not installed: pip install gradata[cloud]")
        except Exception as e:
            logger.warning("Cloud connection failed, using local mode: %s", e)
        return self

    @property
    def cloud_connected(self) -> bool:
        """True if this brain is connected to Gradata Cloud."""
        return self._cloud is not None and self._cloud.connected
