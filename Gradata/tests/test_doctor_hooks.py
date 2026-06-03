from __future__ import annotations

import json
from pathlib import Path

from gradata import _doctor


def test_doctor_warns_and_removes_missing_gradata_hook_brain_dirs(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    missing_brain = tmp_path / "pytest-55" / "test_hook_adapter_install_is_i0" / "brain"
    live_brain = tmp_path / "live-brain"
    live_brain.mkdir()
    settings_path = home / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"BRAIN_DIR={missing_brain} python -m gradata.hooks.inject_brain_rules",
                                }
                            ],
                        },
                        {
                            "matcher": "*",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f"BRAIN_DIR={live_brain} python -m gradata.hooks.inject_brain_rules",
                                }
                            ],
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    check = _doctor._check_missing_hook_brain_dirs(auto_remove=True)

    assert check["status"] == "warn"
    assert str(missing_brain) in check["detail"]
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    commands = [
        hook["command"] for group in settings["hooks"]["PreToolUse"] for hook in group["hooks"]
    ]
    assert all(str(missing_brain) not in command for command in commands)
    assert any(str(live_brain) in command for command in commands)
