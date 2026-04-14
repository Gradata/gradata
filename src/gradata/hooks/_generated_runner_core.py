"""Shared implementation for PreToolUse / PostToolUse generated-hook runners.

Dispatch order per invocation:

1. If `_dispatcher.js` + `_manifest.json` exist in the hook root, run ONE
   node process against the whole manifest. This is the fast path — at 6+
   rules it shaves hundreds of milliseconds per tool call compared to
   spawning one node per rule.

2. Whether or not the dispatcher fired, iterate any remaining legacy
   per-rule .js files that are NOT represented in the manifest. This keeps
   orphan files (rules installed before migration) working until
   `gradata hooks migrate` folds them in.

   If the dispatcher already emitted a block (exit 2), we return immediately
   — no further legacy scanning.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from pathlib import Path

_DISPATCHER_FILENAME = "_dispatcher.js"
_MANIFEST_FILENAME = "_manifest.json"


def _read_manifest_slugs(manifest_file: Path) -> set[str]:
    """Return the set of slugs registered in the manifest, or an empty set."""
    try:
        import json

        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(data, list):
        return set()
    return {e["slug"] for e in data if isinstance(e, dict) and e.get("slug")}


def run_generated_hooks(*, env_var: str, default_dir: str, per_hook_timeout: int) -> int:
    """Iterate generated hooks in the configured dir, run each, relay first block."""
    # Short-circuit before any I/O so GRADATA_BYPASS truly zeros the overhead
    # (no stdin drain, no filesystem scan).
    if os.environ.get("GRADATA_BYPASS") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload_json = raw
    except Exception:
        return 0

    override = os.environ.get(env_var)
    root = Path(override) if override else Path(default_dir)
    if not root.exists():
        return 0

    dispatcher = root / _DISPATCHER_FILENAME
    manifest = root / _MANIFEST_FILENAME
    dispatcher_ran = False

    # Capture node stdout/stderr as bytes so we can decode UTF-8 explicitly —
    # Windows consoles default to cp1252 and will choke on the block-emoji
    # in dispatcher output otherwise.
    payload_bytes = payload_json.encode("utf-8")

    def _decode(b: bytes) -> str:
        try:
            return b.decode("utf-8", errors="replace")
        except Exception:
            return ""

    # Fast path: bundled dispatcher.
    if dispatcher.exists() and manifest.exists():
        dispatcher_ran = True
        try:
            proc = subprocess.run(
                ["node", str(dispatcher)],
                input=payload_bytes,
                capture_output=True,
                timeout=per_hook_timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            proc = None
        except Exception:
            proc = None
        if proc is not None and proc.returncode == 2:
            if proc.stdout:
                with contextlib.suppress(Exception):
                    sys.stdout.write(_decode(proc.stdout))
            if proc.stderr:
                with contextlib.suppress(Exception):
                    sys.stderr.write(_decode(proc.stderr))
            return 2

    # Fallback / compat path: iterate any legacy per-file hooks not represented
    # in the manifest. Skips internal files (dispatcher + manifest). Only read
    # the manifest slugs here — when the dispatcher blocked we already returned,
    # and when no dispatcher is installed there's nothing to skip.
    manifest_slugs = _read_manifest_slugs(manifest) if dispatcher_ran else set()
    for hook_path in sorted(root.glob("*.js")):
        if hook_path.name == _DISPATCHER_FILENAME:
            continue
        if hook_path.stem in manifest_slugs:
            continue
        try:
            proc = subprocess.run(
                ["node", str(hook_path)],
                input=payload_bytes,
                capture_output=True, timeout=per_hook_timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        except Exception:
            continue
        if proc.returncode == 2:
            if proc.stdout:
                with contextlib.suppress(Exception):
                    sys.stdout.write(_decode(proc.stdout))
            return 2
    return 0
