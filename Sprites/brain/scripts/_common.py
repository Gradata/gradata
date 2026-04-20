"""Shared helpers for tracked brain/scripts/* operational scripts.

Consolidates two duplicated bits of plumbing:

1. ``ensure_sdk_on_path()`` — wires ``<repo>/sdk/src`` into ``sys.path`` so
   ``from gradata...`` imports resolve when a script is invoked directly.
2. ``ollama_generate()`` — a thin POST wrapper around Ollama's
   ``/api/generate`` endpoint with sensible timeouts and a uniform
   error-marker return value.

Keep this module dependency-free (stdlib only) — these scripts run in
minimal environments (cron, worktrees, one-off invocations).
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "gemma4:e4b"


def ensure_sdk_on_path() -> Path:
    """Insert the repo's SDK source root into ``sys.path`` so ``from gradata...``
    resolves when a script is invoked directly.

    Prefers ``src/`` (legacy root layout) then falls back to ``sdk/src/``.
    Returns the resolved SDK root so callers can log it if they want.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    for candidate in (repo_root / "src", repo_root / "sdk" / "src"):
        if (candidate / "gradata").is_dir():
            sdk_root = candidate
            break
    else:
        sdk_root = repo_root / "src"
    sdk_root_str = str(sdk_root)
    if sdk_root_str not in sys.path:
        sys.path.insert(0, sdk_root_str)
    return sdk_root


def ollama_generate(
    prompt: str,
    *,
    system: str = "",
    model: str = DEFAULT_OLLAMA_MODEL,
    url: str = DEFAULT_OLLAMA_URL,
    timeout: int = 120,
    num_predict: int = 500,
    temperature: float = 0.7,
) -> str:
    """Call Ollama ``/api/generate``. Returns response text or an error marker.

    The error-marker shape (``"[Generation failed: ...]"``) is load-bearing —
    callers downstream (A/B judge parse, MiroFish post body) tolerate it as
    a regular string rather than raising.
    """
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        log.warning("Ollama call failed: %s", e)
        return f"[Generation failed: {e}]"
