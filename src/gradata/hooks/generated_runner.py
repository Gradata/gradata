"""Claude Code PreToolUse hook that relays to every user-installed generated hook.

`gradata rule add` installs deterministic rule hooks under
`$GRADATA_HOOK_ROOT/<slug>.js` (defaulting to `.claude/hooks/pre-tool/generated/`).
Claude Code only runs hooks listed in settings.json — this runner is the
single entry point registered there. It iterates the generated dir at runtime
and invokes each .js hook. If any hook exits with code 2 (block), we relay
that decision back to Claude Code.

Safety: never raises out of the runner. Any internal error → exit 0 so the
session is never broken by a bad generated hook.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _hook_root() -> Path:
    override = os.environ.get("GRADATA_HOOK_ROOT")
    if override:
        return Path(override)
    return Path(".claude/hooks/pre-tool/generated")


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
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue  # Never break on a single hook failure
        except Exception:
            continue

        if proc.returncode == 2:
            # Relay the first block decision back to Claude Code verbatim
            if proc.stdout:
                sys.stdout.write(proc.stdout)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
