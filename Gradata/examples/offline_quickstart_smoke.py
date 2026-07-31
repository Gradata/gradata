#!/usr/bin/env python3
"""Offline smoke test for the public Gradata quickstart.

This script exercises the install/onboarding path without network access or
external credentials. Run it from a source checkout with `PYTHONPATH=src`, or
after installing the package with `pip install gradata`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run(args: list[str], *, env: dict[str, str]) -> str:
    cmd = [sys.executable, "-m", "gradata.cli", *args]
    print("$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd,
        check=False,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(proc.stdout.strip())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gradata-quickstart-") as tmp:
        root = Path(tmp)
        brain = root / "my-brain"
        home = root / "home"
        home.mkdir()

        env = os.environ.copy()
        env["HOME"] = str(home)
        env["GRADATA_BRAIN_DIR"] = str(brain)
        env.setdefault("GRADATA_LOG", "WARNING")
        # Make this smoke deterministic when run by developers/agents that already
        # export a live Gradata brain path in their shell.
        env.pop("BRAIN_DIR", None)
        env.pop("GRADATA_BRAIN", None)

        run(["--help"], env=env)
        run(["init", str(brain), "--domain", "Smoke", "--name", "Quickstart Smoke", "--no-interactive"], env=env)
        run(["--brain-dir", str(brain), "install", "--agent", "claude-code", "--brain", str(brain), "--dry-run"], env=env)
        run([
            "--brain-dir",
            str(brain),
            "correct",
            "--draft",
            "We are pleased to inform you of our new product offering.",
            "--final",
            "Hey, check out what we just shipped.",
        ], env=env)
        run(["--brain-dir", str(brain), "recall", "draft a launch email", "--max-tokens", "400"], env=env)
        stats = run(["--brain-dir", str(brain), "stats"], env=env)
        run(["--brain-dir", str(brain), "audit"], env=env)

        if f"Brain: {brain}" not in stats:
            raise SystemExit(f"stats used the wrong brain directory:\n{stats}")
        if not (brain / "system.db").exists():
            raise SystemExit(f"missing expected brain database: {brain / 'system.db'}")

    print("✓ offline quickstart smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
