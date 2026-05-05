"""
Shared User-Level Config Path Resolver
========================================

Centralizes platform-aware resolution of the Gradata user config directory
(where opt-in flags, telemetry state, install manifests, etc. live) so no
individual SDK module has to hardcode ``Path.home() / ".gradata"``.

Resolution order:
1. ``GRADATA_CONFIG_DIR`` environment variable (absolute path override).
2. ``XDG_CONFIG_HOME/gradata`` on POSIX when the env var is set.
3. ``Path.home() / ".gradata"`` as the portable fallback.

Callers should ALWAYS go through :func:`get_config_dir` instead of building
paths from ``Path.home()`` directly. That keeps future work (XDG compliance,
Windows %APPDATA%, sandboxed test overrides) in one place.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

ENV_CONFIG_DIR: Final[str] = "GRADATA_CONFIG_DIR"
ENV_XDG_CONFIG_HOME: Final[str] = "XDG_CONFIG_HOME"
_APP_DIR_NAME: Final[str] = ".gradata"


def get_config_dir() -> Path:
    """Return the user-level Gradata config directory.

    Does NOT create the directory — callers that need to write to it should
    call ``get_config_dir().mkdir(parents=True, exist_ok=True)`` themselves.
    """
    override = os.environ.get(ENV_CONFIG_DIR, "").strip()
    if override:
        override_path = Path(override).expanduser()
        if not override_path.is_absolute():
            raise ValueError(f"{ENV_CONFIG_DIR} must be an absolute path")
        return override_path.resolve()

    xdg = os.environ.get(ENV_XDG_CONFIG_HOME, "").strip()
    if xdg and os.name != "nt":
        return (Path(xdg).expanduser() / "gradata").resolve()

    return (Path.home() / _APP_DIR_NAME).resolve()


def get_config_file(name: str) -> Path:
    """Return ``<config_dir>/<name>``. Convenience wrapper."""
    requested = Path(name)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("config file name must be a relative path inside the config directory")
    config_dir = get_config_dir()
    resolved = (config_dir / requested).resolve()
    if config_dir.resolve() not in (resolved, *resolved.parents):
        raise ValueError("config file path escapes the config directory")
    return resolved
