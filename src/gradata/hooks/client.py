"""Daemon-aware hook entrypoint. Used as ``python -m gradata.hooks.client <name>``.

Tries the local hook daemon first (fast: no Python spawn cost); falls back to
direct module import if the daemon isn't running. Used by ``settings.json``
hook commands so users can opt in to the daemon without any config change
other than changing the command to route through this module.

Exits 0 on success, 127 on unknown hook, 1 on transport errors (after
fallback also fails).
"""
from __future__ import annotations

import importlib
import json
import sys
import urllib.error
import urllib.request

from .daemon import HOST, PORT


def _try_daemon(name: str, body: str, timeout: float = 5.0) -> dict | None:
    """POST the hook payload to the running daemon. Returns None on failure."""
    data = body.encode("utf-8")
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/hook/{name}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: python -m gradata.hooks.client <hook_name>\n")
        return 2
    name = sys.argv[1]
    body = sys.stdin.read() if not sys.stdin.isatty() else ""

    resp = _try_daemon(name, body)
    if resp is not None:
        sys.stdout.write(resp.get("stdout", ""))
        sys.stderr.write(resp.get("stderr", ""))
        return int(resp.get("exit_code", 0))

    try:
        _fi_mod = importlib.import_module(f"gradata.hooks.{name}")
    except ImportError:
        sys.stderr.write(f"unknown hook: {name}\n")
        return 127
    if not hasattr(_fi_mod, "main"):
        sys.stderr.write(f"hook {name} has no main()\n")
        return 127
    try:
        _fi_data = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"invalid JSON stdin: {exc}\n")
        return 2
    _fi_result = _fi_mod.main(_fi_data)
    if isinstance(_fi_result, dict):
        sys.stdout.write(json.dumps(_fi_result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
