"""Claude Code PostToolUse hook that relays to every user-installed post-tool hook.

Companion to generated_runner.py. Reads from GRADATA_HOOK_ROOT_POST
(default `.claude/hooks/post-tool/generated/`).

Runs each .js hook with the PostToolUse payload. Relays first exit-2 decision.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _hook_root() -> Path:
    override = os.environ.get("GRADATA_HOOK_ROOT_POST")
    if override:
        return Path(override)
    return Path(".claude/hooks/post-tool/generated")


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload_json = raw
    except Exception:
        return 0

    root = _hook_root()
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
                capture_output=True, text=True, timeout=30,
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


if __name__ == "__main__":
    sys.exit(main())
