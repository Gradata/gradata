"""
Gradata systemd user-unit installer.

Writes a `gradata-daemon.service` user unit under
``~/.config/systemd/user/`` so the HTTP daemon survives shell-session exit
and is automatically restarted on failure.

This module only WRITES the unit file and prints the post-install
``systemctl --user`` commands the user should run. It deliberately does
NOT shell out to ``systemctl`` itself — that keeps the function safe to
unit-test in CI (which has no user systemd instance), and keeps the
SDK's install path side-effect minimal.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_UNIT_NAME = "gradata-daemon.service"
DEFAULT_PORT = 8765

# Template lives next to this module so it ships in the wheel.
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "gradata-daemon.service"


def _read_token(brain_dir: Path) -> str:
    """Resolve the cloud API token.

    Precedence:
      1. ``GRADATA_API_KEY`` env var
      2. ``<brain_dir>/cloud-config.json`` ``token`` field
    """
    env_token = os.environ.get("GRADATA_API_KEY", "").strip()
    if env_token:
        return env_token

    cfg = brain_dir / "cloud-config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        token = str(data.get("token", "")).strip()
        if token:
            return token

    return ""


def render_unit(
    *,
    brain_dir: Path,
    token: str,
    port: int = DEFAULT_PORT,
    python: str | None = None,
) -> str:
    """Render the systemd user unit file as a string.

    Pure function — does no filesystem writes — so it is trivial to test.
    """
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(
        python=python or sys.executable or "python3",
        brain_dir=str(brain_dir),
        port=port,
        token=token,
    )


def unit_path(unit_name: str = DEFAULT_UNIT_NAME) -> Path:
    """Return the canonical path the unit file is installed at.

    Honors ``XDG_CONFIG_HOME`` so tests can sandbox via ``$HOME`` / XDG.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "systemd" / "user" / unit_name


def install_systemd_unit(
    *,
    brain_dir: Path,
    port: int = DEFAULT_PORT,
    token: str | None = None,
    unit_name: str = DEFAULT_UNIT_NAME,
    python: str | None = None,
) -> Path:
    """Write ``gradata-daemon.service`` into the user's systemd config dir.

    Returns the absolute path the unit was written to.

    Note: this does NOT run ``systemctl daemon-reload`` / ``enable --now``
    itself. The caller (CLI) prints those commands for the user to run.
    """
    brain_dir = Path(brain_dir).expanduser().resolve()
    resolved_token = token if token is not None else _read_token(brain_dir)

    if not resolved_token:
        raise RuntimeError(
            "No API token found. Set GRADATA_API_KEY or write "
            f"{brain_dir / 'cloud-config.json'} with a 'token' field "
            "before running `gradata install --systemd`."
        )

    rendered = render_unit(
        brain_dir=brain_dir,
        token=resolved_token,
        port=port,
        python=python,
    )

    target = unit_path(unit_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        # chmod can fail on tmpfs/WSL-mounted Windows paths — non-fatal,
        # the file is still in the user's own config dir.
        pass
    return target


def post_install_message(unit_path_: Path) -> str:
    """Return the message printed after a successful install."""
    return (
        f"✓ Wrote systemd user unit: {unit_path_}\n"
        "  To activate, run:\n"
        "    systemctl --user daemon-reload\n"
        "    systemctl --user enable --now gradata-daemon\n"
        "  To check status:\n"
        "    systemctl --user status gradata-daemon\n"
        "    journalctl --user -u gradata-daemon -f"
    )
