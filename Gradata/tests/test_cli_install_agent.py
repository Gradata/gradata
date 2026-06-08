from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(tmp_path: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base_env = os.environ.copy()
    for key in list(base_env):
        if key.startswith("GRADATA_"):
            base_env.pop(key, None)
    base_env["HOME"] = str(tmp_path)
    base_env["USERPROFILE"] = str(tmp_path)
    base_env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    base_env["PYTHONPATH"] = str(Path.cwd() / "src")
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "gradata.cli", *args],
        cwd=Path.cwd(),
        env=base_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_install_agent_writes_config_under_fake_home(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()

    result = _run_cli(tmp_path, "install", "--agent", "codex", "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    config = tmp_path / ".codex" / "config.toml"
    assert config.exists()
    assert "gradata:codex" in config.read_text(encoding="utf-8")
    assert "codex" in result.stdout


def test_cli_install_agent_all_detects_existing_configs(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("", encoding="utf-8")
    (tmp_path / ".hermes").mkdir()
    (tmp_path / ".hermes" / "config.yaml").write_text("", encoding="utf-8")

    result = _run_cli(tmp_path, "install", "--agent", "all", "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    assert "codex" in result.stdout
    assert "hermes" in result.stdout


@pytest.mark.parametrize(
    ("agent", "config_relpath", "expected_tokens"),
    [
        pytest.param(
            "claude-code",
            Path(".claude/settings.json"),
            [
                "PreToolUse",
                "PostToolUse",
                "Stop",
                "PreCompact",
                "UserPromptSubmit",
                "gradata.hooks.inject_brain_rules",
                "gradata.hooks.auto_correct",
                "gradata.hooks.session_close",
                "gradata.hooks.pre_compact",
                "gradata.hooks.context_inject",
            ],
            id="claude-code-hooks",
        ),
        pytest.param(
            "codex",
            Path(".codex/config.toml"),
            [
                "[[hooks.pre_tool]]",
                "gradata.hooks.inject_brain_rules",
            ],
            id="codex-pre-tool-hook",
        ),
        pytest.param(
            "hermes",
            Path(".hermes/config.yaml"),
            [
                "pre_tool_call:",
                "post_tool_call:",
                "on_session_end:",
                "gradata.hooks.inject_brain_rules",
                "gradata.hooks.auto_correct",
                "gradata.hooks.session_close",
            ],
            id="hermes-native-hook-names",
        ),
        pytest.param(
            "opencode",
            Path(".config/opencode/config.json"),
            [
                "preTool",
                "gradata.hooks.inject_brain_rules",
            ],
            id="opencode-pre-tool-hook",
        ),
        pytest.param(
            "cursor",
            Path(".cursor/mcp.json"),
            [],
            marks=pytest.mark.skip(
                reason="GRA-1680: Cursor is MCP-only; no hook/slash-command install path to smoke-test"
            ),
            id="cursor-mcp-only-skipped",
        ),
    ],
)
def test_cli_install_agent_smoke_matrix_writes_expected_host_config(
    tmp_path: Path,
    agent: str,
    config_relpath: Path,
    expected_tokens: list[str],
) -> None:
    """Show-HN smoke matrix for supported hook/MCP config install paths.

    Slash-command artifact files are intentionally not asserted here: the SDK's
    current one-command surface (`gradata install --agent ...`) writes native
    host config hooks, and no separate slash-command artifact installer exists.
    Cursor is represented as an explicit skipped matrix row because it is
    MCP-only rather than a hook/slash-command install path.
    """
    brain = tmp_path / "brain"
    brain.mkdir()

    result = _run_cli(tmp_path, "install", "--agent", agent, "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    assert agent in result.stdout
    config = tmp_path / config_relpath
    assert config.exists()
    contents = config.read_text(encoding="utf-8")
    assert f"gradata:{agent}:{brain.resolve().as_posix()}" in contents
    assert "BRAIN_DIR=" in contents
    for token in expected_tokens:
        assert token in contents

    manifest = tmp_path / ".gradata" / "install_manifest.json"
    assert manifest.exists()
    assert f'"{agent}"' in manifest.read_text(encoding="utf-8")

    rerun = _run_cli(tmp_path, "install", "--agent", agent, "--brain", str(brain))
    assert rerun.returncode == 0, rerun.stderr
    assert "already_present" in rerun.stdout


def test_cli_install_agent_verify_flag_off_preserves_current_behavior(tmp_path: Path) -> None:
    """Without GRADATA_VERIFY_INSTALL, output must NOT contain verify lines."""
    brain = tmp_path / "brain"
    brain.mkdir()

    result = _run_cli(tmp_path, "install", "--agent", "codex", "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    # Verify output lines start with "  ✓ verify:" / "  ✗ verify" / "  ⚠ verify"
    for line in result.stdout.splitlines():
        suffix = line.lstrip()
        if suffix.startswith("✓ verify:") or suffix.startswith("✗ verify") or suffix.startswith("⚠ verify"):
            raise AssertionError(f"unexpected verify line: {line}")


def test_cli_install_agent_verify_flag_on_shows_confirmation(tmp_path: Path) -> None:
    """With GRADATA_VERIFY_INSTALL=1, successful install shows verify line."""
    brain = tmp_path / "brain"
    brain.mkdir()

    # Brain needs initialization for correct() + search() to work
    from gradata import Brain

    Brain.init(brain)

    env_extra = {"GRADATA_VERIFY_INSTALL": "1"}
    result = _run_cli(tmp_path, "install", "--agent", "codex", "--brain", str(brain), env=env_extra)

    assert result.returncode == 0, result.stderr
    if "already_present" not in result.stdout:
        assert "verify" in result.stdout


def test_cli_install_agent_verify_flag_skips_on_failed_install(tmp_path: Path) -> None:
    """Verify is NOT attempted when install itself reports 'failed'."""
    brain = tmp_path / "brain"
    brain.mkdir()

    # claude-code adapter parses JSON and will fail on corrupt input
    bad_config_dir = tmp_path / ".claude"
    bad_config_dir.mkdir(parents=True)
    (bad_config_dir / "settings.json").write_text("{{{bad json", encoding="utf-8")

    env_extra = {"GRADATA_VERIFY_INSTALL": "1"}
    result = _run_cli(
        tmp_path,
        "install",
        "--agent",
        "claude-code",
        "--brain",
        str(brain),
        env=env_extra,
    )

    # Should fail from install itself, not from verify
    assert result.returncode != 0
    for line in result.stdout.splitlines():
        suffix = line.lstrip()
        if suffix.startswith("✓ verify:") or suffix.startswith("✗ verify") or suffix.startswith("⚠ verify"):
            raise AssertionError(f"unexpected verify line on failed install: {line}")


def _read_install_measurements(tmp_path: Path) -> list[dict[str, object]]:
    import json

    path = tmp_path / ".config" / "gradata" / "install_measurements.jsonl"
    assert path.exists()
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_cli_install_agent_records_success_measurement_for_measured_cli(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()

    result = _run_cli(tmp_path, "install", "--agent", "codex", "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    measurements = _read_install_measurements(tmp_path)
    assert measurements[-1]["agent"] == "codex"
    assert measurements[-1]["status"] == "success"
    assert measurements[-1]["failure_kind"] == "none"
    assert measurements[-1]["action"] == "added"


def test_cli_install_agent_records_code_failure_measurement(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    bad_config_dir = tmp_path / ".claude"
    bad_config_dir.mkdir(parents=True)
    (bad_config_dir / "settings.json").write_text("{{{bad json", encoding="utf-8")

    result = _run_cli(tmp_path, "install", "--agent", "claude-code", "--brain", str(brain))

    assert result.returncode != 0
    measurements = _read_install_measurements(tmp_path)
    assert measurements[-1]["agent"] == "claude-code"
    assert measurements[-1]["status"] == "failure"
    assert measurements[-1]["failure_kind"] == "code_failure"


def test_cli_install_agent_all_records_docs_friction_for_missing_measured_cli_configs(
    tmp_path: Path,
) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("", encoding="utf-8")

    result = _run_cli(tmp_path, "install", "--agent", "all", "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    measurements = _read_install_measurements(tmp_path)
    by_agent = {m["agent"]: m for m in measurements}
    assert by_agent["codex"]["status"] == "success"
    assert by_agent["claude-code"]["failure_kind"] == "docs_friction"
    assert by_agent["hermes"]["failure_kind"] == "docs_friction"
    assert by_agent["cursor"]["failure_kind"] == "docs_friction"
