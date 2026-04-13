"""Claude Code PreToolUse runner for user-installed generated hooks."""
from __future__ import annotations

import sys

from gradata.hooks._generated_runner_core import run_generated_hooks


def main() -> int:
    return run_generated_hooks(
        env_var="GRADATA_HOOK_ROOT",
        default_dir=".claude/hooks/pre-tool/generated",
        per_hook_timeout=5,
    )


if __name__ == "__main__":
    sys.exit(main())
