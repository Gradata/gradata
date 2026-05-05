from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    env["XDG_CONFIG_HOME"] = str(tmp_path / ".config")
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    return subprocess.run(
        [sys.executable, "-m", "gradata.cli", *args],
        cwd=Path.cwd(),
        env=env,
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
