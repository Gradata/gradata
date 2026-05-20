"""Install manifest for ``gradata install --agent <host>``.

Records, per host, the config file we wrote into and the SHA256 of that
file *immediately after* the install. ``gradata uninstall --agent <host>``
reads this manifest and:

- If the config file's current SHA matches the recorded SHA, the user
  hasn't touched the file since install — safe to remove our entry.
- If the SHA differs, the user has edited the file by hand. Skip with a
  ``skipped X — modified since install`` message and leave the file
  alone. (Better to leak one harmless hook entry than to clobber a
  user-customized config.)

The manifest lives at ``~/.gradata/install_manifest.json`` so it survives
between ``install`` and ``uninstall`` invocations and is independent of
any single brain directory.

Schema (v1)::

    {
      "schema_version": 1,
      "agents": {
        "claude-code": {
          "config_path": "/home/olive/.claude/settings.json",
          "signature": "gradata:claude-code:/home/olive/brain",
          "sha256_after_install": "abcdef…"
        },
        ...
      }
    }
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from gradata._atomic import atomic_write_text

SCHEMA_VERSION = 1


def manifest_path(home: Path | None = None) -> Path:
    """Return the on-disk manifest path. Honors $GRADATA_HOME if set."""
    override = os.environ.get("GRADATA_HOME")
    if override:
        return Path(override) / "install_manifest.json"
    resolved_home = home or Path(
        os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")
    )
    return resolved_home / ".gradata" / "install_manifest.json"


@dataclass(frozen=True)
class AgentRecord:
    config_path: Path
    signature: str
    sha256_after_install: str


def file_sha256(path: Path) -> str:
    """Return SHA256 of *path*'s bytes, or '' if it doesn't exist."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path | None = None) -> dict:
    """Load the manifest as a plain dict. Returns empty structure if missing."""
    p = path or manifest_path()
    if not p.exists():
        return {"schema_version": SCHEMA_VERSION, "agents": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupt manifest — start fresh rather than crash uninstall.
        return {"schema_version": SCHEMA_VERSION, "agents": {}}
    if not isinstance(data, dict):
        return {"schema_version": SCHEMA_VERSION, "agents": {}}
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("agents", {})
    return data


def save(data: dict, path: Path | None = None) -> None:
    p = path or manifest_path()
    atomic_write_text(p, json.dumps(data, indent=2, sort_keys=True) + "\n")


def record_install(
    agent: str,
    config_path: Path,
    signature: str,
    *,
    path: Path | None = None,
) -> None:
    """Record that *agent* installed a hook with *signature* into *config_path*.

    Computes SHA256 of the config file after install and stores it. If a
    record already exists for this agent we overwrite it (re-installs win).
    """
    data = load(path)
    agents = data.setdefault("agents", {})
    agents[agent] = {
        "config_path": str(config_path),
        "signature": signature,
        "sha256_after_install": file_sha256(config_path),
    }
    save(data, path)


def get_record(agent: str, path: Path | None = None) -> AgentRecord | None:
    data = load(path)
    raw = data.get("agents", {}).get(agent)
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return AgentRecord(
            config_path=Path(raw["config_path"]),
            signature=raw["signature"],
            sha256_after_install=raw.get("sha256_after_install", ""),
        )
    except KeyError:
        return None


def drop_record(agent: str, path: Path | None = None) -> bool:
    """Remove *agent*'s record. Returns True if it existed."""
    data = load(path)
    agents = data.setdefault("agents", {})
    if agent in agents:
        del agents[agent]
        save(data, path)
        return True
    return False
