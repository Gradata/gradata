"""Tests for the Gradata daemon — telemetry opt-in behavior."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from gradata.daemon import GradataDaemon

if TYPE_CHECKING:
    from pathlib import Path

# ── Telemetry opt-out / missing config ───────────────────────────────


def test_telemetry_not_sent_when_config_missing(tmp_path: Path) -> None:
    """Telemetry should not send when ~/.gradata/config.toml doesn't exist."""
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()

    d = GradataDaemon(brain_dir, port=0)
    with patch("gradata.daemon.Path.home", return_value=fake_home):
        d._maybe_send_telemetry()

    # No config.toml → no telemetry_last_sent written anywhere
    assert not (fake_home / ".gradata" / "config.toml").exists()


def test_telemetry_not_sent_when_opted_out(tmp_path: Path) -> None:
    """Telemetry should NOT send when config says telemetry = false."""
    fake_home = tmp_path / "fakehome"
    config_dir = fake_home / ".gradata"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text('python_path = "python3"\ntelemetry = false\n', encoding="utf-8")

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    d = GradataDaemon(brain_dir, port=0)
    with patch("gradata.daemon.Path.home", return_value=fake_home):
        d._maybe_send_telemetry()

    config_after = config_path.read_text(encoding="utf-8")
    assert "telemetry_last_sent" not in config_after


def test_telemetry_not_sent_when_key_missing(tmp_path: Path) -> None:
    """Telemetry should NOT send when config has no telemetry key at all."""
    fake_home = tmp_path / "fakehome"
    config_dir = fake_home / ".gradata"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text('python_path = "python3"\n', encoding="utf-8")

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    d = GradataDaemon(brain_dir, port=0)
    with patch("gradata.daemon.Path.home", return_value=fake_home):
        d._maybe_send_telemetry()

    config_after = config_path.read_text(encoding="utf-8")
    assert "telemetry_last_sent" not in config_after


# ── Telemetry opt-in ─────────────────────────────────────────────────


def test_telemetry_sent_when_opted_in(tmp_path: Path) -> None:
    """Telemetry should fire background thread when telemetry = true."""
    fake_home = tmp_path / "fakehome"
    config_dir = fake_home / ".gradata"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text('telemetry = true\n', encoding="utf-8")

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    d = GradataDaemon(brain_dir, port=0)

    # Mock urlopen so we don't make real HTTP calls
    with (
        patch("gradata.daemon.Path.home", return_value=fake_home),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        d._maybe_send_telemetry()
        # Poll for up to 2 seconds for the background thread to complete
        timeout = 2.0
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if mock_urlopen.called:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Telemetry thread did not complete within timeout")

    # The background thread should have attempted a POST
    assert mock_urlopen.called

    # And written telemetry_last_sent to config
    config_after = config_path.read_text(encoding="utf-8")
    assert "telemetry_last_sent" in config_after


def test_telemetry_skipped_when_sent_recently(tmp_path: Path) -> None:
    """Telemetry should skip if last_sent is within 24h."""
    fake_home = tmp_path / "fakehome"
    config_dir = fake_home / ".gradata"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    now = datetime.now(UTC).isoformat()
    config_path.write_text(
        f'telemetry = true\ntelemetry_last_sent = "{now}"\n',
        encoding="utf-8",
    )

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    d = GradataDaemon(brain_dir, port=0)

    with (
        patch("gradata.daemon.Path.home", return_value=fake_home),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        d._maybe_send_telemetry()

    # Should NOT have sent — last_sent is too recent
    mock_urlopen.assert_not_called()