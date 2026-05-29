#!/usr/bin/env python3
"""Offline quickstart smoke test for Show HN/readme proof.

This intentionally uses only the local SDK/CLI path:
- no Gradata Cloud key
- no daemon requirement
- no network calls
- no LLM/provider credentials

Run from a checkout:
    python3 scripts/smoke_quickstart.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _run(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        cmd = " ".join(args)
        raise RuntimeError(
            f"command failed ({result.returncode}): {cmd}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )
    return result


def smoke(tmp_root: Path) -> dict[str, object]:
    brain_dir = tmp_root / "show-hn-brain"
    home_dir = tmp_root / "home"
    home_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "PYTHONPATH": str(SRC),
            "GRADATA_TELEMETRY": "0",
            "GRADATA_DISABLE_WRITE_THROUGH": "1",
            "GRADATA_BRAIN": str(brain_dir),
        }
    )
    env.pop("GRADATA_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("GOOGLE_API_KEY", None)

    py = sys.executable
    commands = [
        [
            py,
            "-m",
            "gradata.cli",
            "init",
            str(brain_dir),
            "--domain",
            "Sales",
            "--name",
            "Show HN Smoke Brain",
            "--no-interactive",
        ],
        [
            py,
            "-m",
            "gradata.cli",
            "--brain-dir",
            str(brain_dir),
            "correct",
            "--draft",
            "We are pleased to inform you of our new product offering.",
            "--final",
            "Hey, check out what we just shipped.",
            "--category",
            "tone",
            "--session",
            "1",
        ],
        [py, "-m", "gradata.cli", "--brain-dir", str(brain_dir), "recall", "draft a launch email"],
        [py, "-m", "gradata.cli", "--brain-dir", str(brain_dir), "manifest", "--json"],
        [py, "-m", "gradata.cli", "--brain-dir", str(brain_dir), "stats"],
    ]

    outputs: list[str] = []
    for cmd in commands:
        result = _run(cmd, cwd=ROOT, env=env)
        outputs.append(result.stdout.strip())

    manifest = json.loads(outputs[3])
    system_db = brain_dir / "system.db"
    if not system_db.exists():
        raise AssertionError(f"expected local brain database at {system_db}")

    return {
        "brain_dir": str(brain_dir),
        "database_created": system_db.exists(),
        "sessions_trained": manifest.get("metadata", {}).get("sessions_trained"),
        "commands": [" ".join(cmd) for cmd in commands],
    }


def main() -> int:
    keep = os.environ.get("GRADATA_SMOKE_KEEP_TMP") == "1"
    tmp_root = Path(tempfile.mkdtemp(prefix="gradata-quickstart-smoke-"))
    try:
        result = smoke(tmp_root)
        print("Gradata offline quickstart smoke: PASS")
        print(json.dumps(result, indent=2))
        return 0
    finally:
        if keep:
            print(f"kept temp dir: {tmp_root}")
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
