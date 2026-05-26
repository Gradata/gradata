from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER_JS = REPO_ROOT / "gradata-install" / "bin" / "gradata-install.js"


def _cli_env(home: Path, brain: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GRADATA_"):
            env.pop(key, None)
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "BRAIN_DIR": str(brain),
            "PYTHONPATH": str(REPO_ROOT / "src"),
        }
    )
    return env


SHOW_HN_SLASH_COMMAND_SKIP = (
    "GRA-1680: legacy slash-command/one-command installer only accepts "
    "claude-code and codex before Show HN; use `gradata install --agent <host>` "
    "for this host until it is promoted into the slash-command path."
)


@pytest.mark.parametrize(
    ("ide", "expected_config", "expected_text"),
    [
        ("claude-code", ".claude/settings.json", "gradata.hooks.inject_brain_rules"),
        ("codex", ".codex/config.toml", "gradata:codex"),
        pytest.param(
            "hermes",
            ".hermes/config.yaml",
            "pre_tool_call",
            marks=pytest.mark.skip(reason=SHOW_HN_SLASH_COMMAND_SKIP),
        ),
        pytest.param(
            "opencode",
            ".config/opencode/config.json",
            "preTool",
            marks=pytest.mark.skip(reason=SHOW_HN_SLASH_COMMAND_SKIP),
        ),
    ],
)
def test_hooks_install_smoke_matrix_for_show_hn_hosts(
    tmp_path: Path, ide: str, expected_config: str, expected_text: str
) -> None:
    """Slash-command hook install smoke matrix used by Show HN completion notes.

    Runs with a mocked HOME/BRAIN_DIR so it proves the installer writes the
    host-specific hook config without touching a developer's real agent config.
    """
    home = tmp_path / "home"
    brain = tmp_path / "brain"
    project = tmp_path / "project"
    brain.mkdir(parents=True)
    project.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gradata.cli",
            "hooks",
            "install",
            "--ide",
            ide,
            "--project-dir",
            str(project),
        ],
        cwd=REPO_ROOT,
        env=_cli_env(home, brain),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    config = home / expected_config
    assert config.is_file(), f"missing {ide} config at {config}"
    text = config.read_text(encoding="utf-8")
    assert expected_text in text
    if ide != "claude-code":
        assert str(brain) in text

    if ide == "claude-code":
        # Claude's richer hook installer should also copy/register the bundled
        # JS assets when project-dir is supplied.
        assert (project / ".claude/hooks/user-prompt/handoff-watchdog.js").is_file()
        data = json.loads(text)
        assert "PreToolUse" in data.get("hooks", {})


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime not installed")
@pytest.mark.parametrize(
    ("ide", "expected_hook_args"),
    [
        ("claude-code", ["hooks", "install"]),
        ("codex", ["hooks", "install", "--ide", "codex"]),
        pytest.param(
            "hermes",
            ["hooks", "install", "--ide", "hermes"],
            marks=pytest.mark.skip(reason=SHOW_HN_SLASH_COMMAND_SKIP),
        ),
        pytest.param(
            "opencode",
            ["hooks", "install", "--ide", "opencode"],
            marks=pytest.mark.skip(reason=SHOW_HN_SLASH_COMMAND_SKIP),
        ),
    ],
)
def test_one_command_installer_routes_hook_install_matrix(
    tmp_path: Path, ide: str, expected_hook_args: list[str]
) -> None:
    """Legacy one-command installer smoke: Claude + Codex reach hook install.

    Python/package installation is stubbed so the test is deterministic and
    offline; the assertion is on the actual hook command the JS wrapper invokes.
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls.jsonl"

    _write_executable(
        fake_bin / "python3",
        """#!/bin/sh
printf '%s\n' "python3 $*" >> "$GRADATA_INSTALL_SMOKE_CALLS"
if [ "$*" = "--version" ]; then
  printf '%s\n' "Python 3.11.9"
fi
exit 0
""",
    )
    _write_executable(
        fake_bin / "gradata",
        """#!/bin/sh
printf '%s\n' "gradata $*" >> "$GRADATA_INSTALL_SMOKE_CALLS"
exit 0
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "USERPROFILE": str(tmp_path / "home"),
            "PATH": str(fake_bin),
            "GRADATA_INSTALL_SMOKE_CALLS": str(calls),
        }
    )

    result = subprocess.run(
        [shutil.which("node") or "node", str(INSTALLER_JS), "install", "--ide", ide],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert f"[gradata-install] Target IDE: {ide}" in result.stdout
    recorded = calls.read_text(encoding="utf-8").splitlines()
    assert "gradata " + " ".join(expected_hook_args) in recorded


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
