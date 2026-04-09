"""SessionStart hook: validate Claude Code settings.json configuration."""
from __future__ import annotations

import json
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "SessionStart",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}


def _find_settings() -> Path | None:
    candidates = [
        Path.home() / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.local.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _validate_json(path: Path) -> list[str]:
    warnings = []
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {path.name}: {e}"]
    except Exception as e:
        return [f"Cannot read {path.name}: {e}"]

    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        warnings.append("'hooks' should be a dict, got " + type(hooks).__name__)
        return warnings

    for event_name, hook_list in hooks.items():
        if not isinstance(hook_list, list):
            warnings.append(f"hooks.{event_name} should be a list")
            continue
        for i, group in enumerate(hook_list):
            if not isinstance(group, dict):
                continue
            # Validate nested hook entries within each group
            inner_hooks = group.get("hooks", [])
            if not isinstance(inner_hooks, list):
                # Fallback: check if this is a flat hook entry (legacy format)
                inner_hooks = [group]
            for j, hook in enumerate(inner_hooks):
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command", "")
                if "python -m gradata.hooks." in command:
                    module_name = command.split("gradata.hooks.")[-1].split()[0].strip('"\'')
                    try:
                        import gradata.hooks as hooks_pkg
                        hooks_dir = Path(hooks_pkg.__file__).parent
                        module_path = hooks_dir / f"{module_name}.py"
                        if not module_path.is_file():
                            warnings.append(
                                f"hooks.{event_name}[{i}].hooks[{j}] references "
                                f"gradata.hooks.{module_name} but module not found"
                            )
                    except Exception:
                        pass

    return warnings


def main(data: dict) -> dict | None:
    try:
        settings_path = _find_settings()
        if not settings_path:
            return None

        warnings = _validate_json(settings_path)
        if warnings:
            return {"result": "Config warnings: " + "; ".join(warnings)}
        return None
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
