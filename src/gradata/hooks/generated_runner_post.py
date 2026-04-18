"""Claude Code PostToolUse runner for user-installed generated hooks."""
from __future__ import annotations

import sys

from ._generated_runner_core import run_generated_hooks


def main() -> int:
    return run_generated_hooks(
        env_var="GRADATA_HOOK_ROOT_POST",
        default_dir=".claude/hooks/post-tool/generated",
        per_hook_timeout=30,
    )


if __name__ == "__main__":
    sys.exit(main())
