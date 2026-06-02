from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


HOST_MATRIX = (
    pytest.param(
        "claude-code",
        Path(".claude/settings.json"),
        {"PreToolUse"},
        id="claude-code",
    ),
    pytest.param(
        "codex",
        Path(".codex/config.toml"),
        {"pre_tool"},
        id="codex",
    ),
    pytest.param(
        "hermes",
        Path(".hermes/config.yaml"),
        {"pre_tool_call"},
        id="hermes",
    ),
    pytest.param(
        "opencode",
        Path(".config/opencode/config.json"),
        {"preTool"},
        id="opencode",
    ),
    pytest.param(
        "cursor",
        Path(".cursor/mcp.json"),
        set(),
        marks=pytest.mark.skip(reason="GRA-1680: Cursor is MCP-only; no hook/slash-command install path to smoke-test"),
        id="cursor-mcp-only-skipped",
    ),
)


def _run_install(tmp_path: Path, host: str, brain: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GRADATA_"):
            env.pop(key, None)
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    return subprocess.run(
        [sys.executable, "-m", "gradata.cli", "install", "--agent", host, "--brain", str(brain)],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(("host", "config_relpath", "expected_events"), HOST_MATRIX)
def test_cli_install_smoke_matrix_writes_host_hook_config(
    tmp_path: Path,
    host: str,
    config_relpath: Path,
    expected_events: set[str],
) -> None:
    """Smoke the current Python CLI install path for supported hook hosts.

    The deprecated npm one-command installer is intentionally not part of this
    matrix: it predates Hermes/OpenCode and is documented as superseded by the
    Python package install path. The matrix pins the hook events emitted by the
    current main-branch adapters; hosts with only a pre-tool hook are covered by
    that supported path instead of silently pretending they have broader hooks.
    """
    brain = tmp_path / "brain"
    brain.mkdir()

    result = _run_install(tmp_path, host, brain)

    assert result.returncode == 0, result.stderr
    assert host in result.stdout
    config_path = tmp_path / config_relpath
    assert config_path.exists(), f"missing {host} config at {config_path}"

    content = config_path.read_text(encoding="utf-8")
    assert f"gradata:{host}:" in content
    assert "BRAIN_DIR=" in content
    assert brain.resolve().as_posix() in content

    if host == "claude-code":
        settings = json.loads(content)
        hooks = settings["hooks"]
        assert expected_events <= set(hooks)
        for event in expected_events:
            assert hooks[event], f"missing Claude hook entries for {event}"
    elif host == "codex":
        config = tomllib.loads(content)
        pre_tool_hooks = config["hooks"]["pre_tool"]
        assert pre_tool_hooks[0]["id"].startswith("gradata:codex:")
        assert "gradata.hooks.inject_brain_rules" in pre_tool_hooks[0]["command"]
    elif host == "hermes":
        for event in expected_events:
            assert f"{event}:" in content
        # Hermes ignores Claude-style legacy names; pin the supported event names.
        legacy_event_lines = content.splitlines()
        assert not any(re.search(r"(^|\s)pre_tool_use\s*:", line) for line in legacy_event_lines)
        assert not any(re.search(r"(^|\s)post_tool_use\s*:", line) for line in legacy_event_lines)
        assert not any(re.search(r"(^|\s)session_end\s*:", line) for line in legacy_event_lines)
    elif host == "opencode":
        config = json.loads(content)
        pre_tool_hooks = config["hooks"]["preTool"]
        assert pre_tool_hooks[0]["id"].startswith("gradata:opencode:")
        assert "gradata.hooks.inject_brain_rules" in pre_tool_hooks[0]["command"]
    else:  # pragma: no cover - matrix guard
        raise AssertionError(f"unhandled host {host}")
