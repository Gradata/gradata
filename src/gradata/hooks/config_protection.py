"""PreToolUse hook: block modifications to linter/formatter config files."""
from __future__ import annotations

import os

from ._base import run_hook
from ._base import Profile

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Write|Edit|MultiEdit",
    "profile": Profile.STANDARD,
    "timeout": 3000,
    "blocking": True,
}

PROTECTED_FILES = {
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml",
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
    ".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierrc.yml",
    "prettier.config.js", "prettier.config.mjs",
    "biome.json", "biome.jsonc",
    "ruff.toml", ".ruff.toml", "pyproject.toml",
    ".shellcheckrc",
    ".stylelintrc", ".stylelintrc.json",
    ".markdownlint.json", ".markdownlintrc",
}


def main(data: dict) -> dict | None:
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return None

    basename = os.path.basename(file_path)
    if basename in PROTECTED_FILES:
        return {
            "decision": "block",
            "reason": f"BLOCKED: {basename} is a linter/formatter config. Fix your code to match the rules, don't weaken the rules to match your code.",
        }
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
