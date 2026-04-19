"""SessionStart hook: validate Claude Code settings.json configuration."""
from __future__ import annotations

import json
from pathlib import Path

from ._base import run_hook
from ._base import Profile

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


def main(data: dict) -> dict | None:
    try:
        settings_path = _find_settings()
        if not settings_path:
            return None
        warnings: list[str] = []
        try:
            parsed = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            warnings = [f"Invalid JSON in {settings_path.name}: {e}"]
            parsed = None
        except Exception as e:
            warnings = [f"Cannot read {settings_path.name}: {e}"]
            parsed = None
        if parsed is not None:
            hooks = parsed.get("hooks", {})
            if not isinstance(hooks, dict):
                warnings.append("'hooks' should be a dict, got " + type(hooks).__name__)
            else:
                for event_name, hook_list in hooks.items():
                    if not isinstance(hook_list, list):
                        warnings.append(f"hooks.{event_name} should be a list")
                        continue
                    for i, group in enumerate(hook_list):
                        if not isinstance(group, dict):
                            continue
                        inner = group.get("hooks", [])
                        if not isinstance(inner, list):
                            inner = [group]
                        for j, hook in enumerate(inner):
                            if not isinstance(hook, dict):
                                continue
                            cmd = hook.get("command", "")
                            if " -m gradata.hooks." in cmd:
                                mod = cmd.split("gradata.hooks.")[-1].split()[0].strip('"\'')
                                try:
                                    import gradata.hooks as _hp
                                    if not (Path(_hp.__file__).parent / f"{mod}.py").is_file():
                                        warnings.append(
                                            f"hooks.{event_name}[{i}].hooks[{j}] references "
                                            f"gradata.hooks.{mod} but module not found"
                                        )
                                except Exception:
                                    pass
        if warnings:
            return {"result": "Config warnings: " + "; ".join(warnings)}
        return None
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
