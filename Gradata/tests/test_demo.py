from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def _run_demo(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("BRAIN_DIR", None)
    env.pop("GRADATA_BRAIN", None)
    return subprocess.run(
        [sys.executable, "-m", "gradata.cli", "demo", *args],
        cwd=Path.cwd(),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def test_gradata_demo_exits_zero(tmp_path: Path) -> None:
    result = _run_demo(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Loading seeded SDR brain" in result.stdout


def test_gradata_demo_prints_before_and_after_sections(tmp_path: Path) -> None:
    result = _run_demo(tmp_path)

    assert "[Without brain]" in result.stdout
    assert "[With brain" in result.stdout


def test_gradata_demo_computes_token_reduction(tmp_path: Path) -> None:
    result = _run_demo(tmp_path)

    match = re.search(r"\[(\d+) tokens, (\d+)% reduction\]", result.stdout)
    assert match, result.stdout
    assert int(match.group(1)) > 0
    assert int(match.group(2)) == 92


def test_gradata_demo_rebuilds_missing_seeded_brain(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    env["NO_COLOR"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"  # ensure ✓ renders consistently across Windows cp1252
    env["GRADATA_DEMO_ASSETS"] = str(tmp_path / "missing-assets")
    env.pop("BRAIN_DIR", None)
    env.pop("GRADATA_BRAIN", None)

    result = subprocess.run(
        [sys.executable, "-m", "gradata.cli", "demo"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Loaded." in result.stdout
    assert (tmp_path / "missing-assets" / "sdr" / "lessons.md").exists()
