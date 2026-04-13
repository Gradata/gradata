"""Shared implementation for PreToolUse / PostToolUse generated-hook runners."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_generated_hooks(*, env_var: str, default_dir: str, per_hook_timeout: int) -> int:
    """Iterate generated hooks in the configured dir, run each, relay first block."""
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

    if os.environ.get("GRADATA_BYPASS") == "1":
        return 0

    for hook_path in hooks:
        try:
            proc = subprocess.run(
                ["node", str(hook_path)],
                input=payload_json,
                capture_output=True, text=True, timeout=per_hook_timeout,
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
