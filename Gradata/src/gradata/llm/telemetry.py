"""Best-effort local telemetry for LLM provider calls."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


def record_llm_call(payload: dict[str, Any]) -> None:
    """Append one LLM call row to the active brain telemetry log if configured."""
    brain_dir = os.environ.get("BRAIN_DIR") or os.environ.get("GRADATA_BRAIN")
    if not brain_dir:
        return
    row = {"ts": time.time(), "type": "llm_call", **payload}
    try:
        path = Path(brain_dir) / "telemetry.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError as exc:
        _log.debug("failed to write LLM telemetry: %s", exc)
