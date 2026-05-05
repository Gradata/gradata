"""Shared implementation for PreToolUse / PostToolUse generated-hook runners."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from gradata._env import env_str
from gradata.hooks._base import should_run
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)


def run_generated_hooks(*, env_var: str, default_dir: str, per_hook_timeout: int) -> int:
    """Iterate generated hooks in the configured dir, run each, relay first block.

    Respects ``GRADATA_HOOK_PROFILE=minimal`` — under the minimal profile
    the runner no-ops (logs a debug line + exits 0). This matches every
    other Gradata hook, which is registered at ``Profile.STANDARD`` in
    ``_installer.HOOK_REGISTRY`` and gated via ``run_hook``. Without this
    check, ``minimal`` users would still have generated rule-hooks
    executed on every Edit/Write/Bash.
    """
    # Short-circuit before any I/O so GRADATA_BYPASS truly zeros the overhead
    # (no stdin drain, no filesystem scan).
    if env_str("GRADATA_BYPASS") == "1":
        return 0

    # Profile gating — match the registry entry in _installer.HOOK_REGISTRY
    # (both generated_runner + generated_runner_post are Profile.STANDARD).
    if not should_run(Profile.STANDARD):
        _log.debug("generated_runner: skipped (profile=minimal, env_var=%s)", env_var)
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

    hooks = sorted(root.glob("*.js"))
    if not hooks:
        return 0

    for hook_path in hooks:
        try:
            proc = subprocess.run(
                ["node", str(hook_path)],
                input=payload_json,
                capture_output=True,
                timeout=per_hook_timeout,
                encoding="utf-8",
                errors="replace",
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
        except Exception:
            continue
        if proc.returncode == 2:
            if proc.stdout:
                sys.stdout.write(proc.stdout)
            return 2
    return 0
