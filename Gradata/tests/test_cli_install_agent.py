from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


AGENT_INSTALL_SMOKE_MATRIX = [
    pytest.param(
        "claude-code", ".claude/settings.json", "gradata:claude-code", id="claude-code-hook"
    ),
    pytest.param("codex", ".codex/config.toml", "gradata:codex", id="codex-hook"),
    pytest.param("hermes", ".hermes/config.yaml", "gradata:hermes", id="hermes-hook"),
    pytest.param(
        "opencode", ".config/opencode/config.json", "gradata:opencode", id="opencode-hook"
    ),
    pytest.param("gemini", ".gemini/settings.json", "gradata:gemini", id="gemini-hook"),
    pytest.param("cursor", ".cursor/mcp.json", "gradata.mcp_server", id="cursor-mcp"),
]


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


@pytest.mark.parametrize(("agent", "config_relpath", "expected_marker"), AGENT_INSTALL_SMOKE_MATRIX)
def test_cli_install_agent_smoke_matrix_with_mocked_home(
    tmp_path: Path,
    agent: str,
    config_relpath: str,
    expected_marker: str,
) -> None:
    """SDK-native one-command install writes each supported host config under fake HOME.

    This is the pre-Show-HN smoke matrix replacing gradata-plugin install checks.
    Hosts that are unsupported should be represented here as explicit pytest.skip(...)
    entries with the tracked reason; the current SDK matrix has no silent skips.
    """
    brain = tmp_path / "brain"
    brain.mkdir()

    result = _run_cli(tmp_path, "install", "--agent", agent, "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    config = tmp_path / config_relpath
    assert config.exists(), result.stdout
    config_text = config.read_text(encoding="utf-8")
    assert expected_marker in config_text
    assert str(brain) in config_text
    assert agent in result.stdout
    assert "added" in result.stdout or "already_present" in result.stdout


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
