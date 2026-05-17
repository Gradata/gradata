"""Tests for `gradata install --systemd` user-unit installation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gradata._systemd_installer import (
    DEFAULT_PORT,
    install_systemd_unit,
    render_unit,
    unit_path,
)


def test_render_unit_contains_all_required_fields(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    brain.mkdir()

    rendered = render_unit(
        brain_dir=brain,
        token="tok-abc123",
        port=8765,
        python="/usr/bin/python3",
    )

    # ExecStart with module + brain-dir + port
    assert (
        f"ExecStart=/usr/bin/python3 -m gradata.daemon --brain-dir {brain} --port 8765"
        in rendered
    )
    # Environment lines
    assert "Environment=GRADATA_API_KEY=tok-abc123" in rendered
    assert "Environment=GRADATA_DAEMON_IDLE_TIMEOUT=0" in rendered
    # Service hardening / restart
    assert "Restart=on-failure" in rendered
    assert "RestartSec=10" in rendered
    # Install target
    assert "WantedBy=default.target" in rendered


def test_install_systemd_unit_writes_file_with_token_from_cloud_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sandbox HOME / XDG so no global state is touched.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)

    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "cloud-config.json").write_text(
        json.dumps({"token": "from-cloud-config"}), encoding="utf-8"
    )

    written = install_systemd_unit(brain_dir=brain, port=8765)

    # File exists at the right location
    expected = tmp_path / ".config" / "systemd" / "user" / "gradata-daemon.service"
    assert written == expected
    assert written.exists()

    contents = written.read_text(encoding="utf-8")
    # Token came from cloud-config.json
    assert "Environment=GRADATA_API_KEY=from-cloud-config" in contents
    # And the brain-dir + port made it into ExecStart
    assert "-m gradata.daemon --brain-dir" in contents
    assert str(brain.resolve()) in contents
    assert "--port 8765" in contents
    # Idle timeout disabled so the daemon doesn't self-shutdown
    assert "Environment=GRADATA_DAEMON_IDLE_TIMEOUT=0" in contents
    # Restart policy
    assert "Restart=on-failure" in contents
    assert "RestartSec=10" in contents
    # Install section
    assert "WantedBy=default.target" in contents


def test_install_systemd_unit_prefers_env_token_over_cloud_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("GRADATA_API_KEY", "from-env-var")

    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "cloud-config.json").write_text(
        json.dumps({"token": "from-cloud-config"}), encoding="utf-8"
    )

    written = install_systemd_unit(brain_dir=brain)
    contents = written.read_text(encoding="utf-8")
    assert "Environment=GRADATA_API_KEY=from-env-var" in contents
    assert "from-cloud-config" not in contents


def test_install_systemd_unit_raises_when_no_token_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)

    brain = tmp_path / "brain"
    brain.mkdir()
    # No cloud-config.json, no env var → should fail loudly.

    with pytest.raises(RuntimeError, match="No API token"):
        install_systemd_unit(brain_dir=brain)


def test_unit_path_honors_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom-xdg"))
    p = unit_path()
    assert p == tmp_path / "custom-xdg" / "systemd" / "user" / "gradata-daemon.service"


def test_default_port_constant() -> None:
    assert DEFAULT_PORT == 8765


def _run_cli(
    tmp_path: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
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


def test_cli_install_systemd_flag_writes_unit_file(tmp_path: Path) -> None:
    """End-to-end: `gradata install --systemd --brain ...` writes the unit."""
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "cloud-config.json").write_text(
        json.dumps({"token": "cli-token-xyz"}), encoding="utf-8"
    )

    result = _run_cli(tmp_path, "install", "--systemd", "--brain", str(brain))

    assert result.returncode == 0, result.stderr
    unit = tmp_path / ".config" / "systemd" / "user" / "gradata-daemon.service"
    assert unit.exists(), f"expected {unit} to exist, stdout={result.stdout!r}"
    text = unit.read_text(encoding="utf-8")
    assert "Environment=GRADATA_API_KEY=cli-token-xyz" in text
    assert "--port 8765" in text
    assert "Restart=on-failure" in text
    assert "WantedBy=default.target" in text
    # And the CLI tells the user the post-install commands
    assert "systemctl --user daemon-reload" in result.stdout
    assert "systemctl --user enable --now gradata-daemon" in result.stdout
