#!/usr/bin/env python3
"""Offline quickstart smoke test for Show HN readers.

Runs the documented install/quickstart path without cloud credentials or
network access:
1. invoke the CLI entrypoint to create a brain;
2. exercise the SDK learning loop from docs/getting-started/quickstart.md;
3. verify local SQLite/manifest/search artifacts exist.

Usage:
    python3 examples/offline_quickstart_smoke.py
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))


def _offline_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GRADATA_TELEMETRY"] = "0"
    env["PYTHONPATH"] = str(SRC_ROOT) if SRC_ROOT.exists() else env.get("PYTHONPATH", "")
    env.pop("GRADATA_API_KEY", None)
    env.pop("GRADATA_CLOUD_API_BASE", None)
    return env


def _run_cli_init(brain_dir: Path, home: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "gradata.cli",
        "init",
        str(brain_dir),
        "--domain",
        "Sales",
        "--name",
        "Offline Quickstart Brain",
        "--no-interactive",
    ]
    subprocess.run(cmd, check=True, env=_offline_env(home), cwd=Path.cwd())


def _assert_event_count(brain_dir: Path, event_type: str, minimum: int) -> None:
    db_path = brain_dir / "system.db"
    with sqlite3.connect(db_path) as con:
        count = con.execute("SELECT COUNT(*) FROM events WHERE type = ?", (event_type,)).fetchone()[0]
    if count < minimum:
        raise AssertionError(f"expected at least {minimum} {event_type} event(s), found {count}")


def run_smoke(root: Path) -> Path:
    home = root / "home"
    brain_dir = root / "my-brain"
    home.mkdir(parents=True, exist_ok=True)

    # Keep the smoke deterministic and credential-free even on a configured dev box.
    os.environ.update(_offline_env(home))

    _run_cli_init(brain_dir, home)
    cli_manifest = json.loads((brain_dir / "brain.manifest.json").read_text(encoding="utf-8"))
    if cli_manifest.get("metadata", {}).get("domain") != "Sales":
        raise AssertionError("CLI init manifest did not preserve --domain Sales")

    from gradata import Brain, __version__

    brain = Brain(brain_dir)
    draft = "Hi John, I wanted to reach out about our AI platform."
    final = "John, saw your team is scaling paid ads. We cut creative testing time in half."

    brain.log_output(draft, output_type="email", self_score=7.0, session=1)
    correction = brain.correct(draft=draft, final=final, session=1)
    rules = brain.apply_brain_rules("email_draft", {"audience": "marketing_manager"})
    manifest = brain.manifest()
    results = brain.search("paid ads", top_k=5)
    health = brain.health()
    brain.close()

    required_files = [
        brain_dir / "system.db",
        brain_dir / "brain.manifest.json",
        brain_dir / "lessons.md",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise AssertionError(f"missing quickstart artifacts: {missing}")

    _assert_event_count(brain_dir, "OUTPUT", 1)
    _assert_event_count(brain_dir, "CORRECTION", 1)

    if not isinstance(correction, dict):
        raise AssertionError("brain.correct() did not return an event dict")
    if not isinstance(rules, str):
        raise AssertionError("brain.apply_brain_rules() did not return a string")
    if not isinstance(results, list):
        raise AssertionError("brain.search() did not return a list")
    if not isinstance(health, dict):
        raise AssertionError("brain.health() did not return a dict")
    if not manifest.get("schema_version"):
        raise AssertionError("manifest did not include a schema_version")

    summary = {
        "ok": True,
        "sdk_version": __version__,
        "brain_dir": str(brain_dir),
        "events": {"OUTPUT": 1, "CORRECTION": 1},
        "cli_manifest_domain": cli_manifest.get("metadata", {}).get("domain"),
        "search_results": len(results),
        "rules_chars": len(rules),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return brain_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temporary smoke brain and print its path for inspection.",
    )
    args = parser.parse_args()

    if args.keep:
        root = Path(tempfile.mkdtemp(prefix="gradata-offline-smoke-"))
        run_smoke(root)
        print(f"kept smoke directory: {root}")
        return 0

    with tempfile.TemporaryDirectory(prefix="gradata-offline-smoke-") as td:
        run_smoke(Path(td))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
