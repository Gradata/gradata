"""Package import integrity tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gradata import Brain


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not existing else f"{src}{os.pathsep}{existing}"
    return env


def test_public_imports_work_in_subprocess() -> None:
    result = subprocess.run(
        [
            "python3",
            "-c",
            "import gradata; from gradata import Brain; from gradata import Lesson, LessonState",
        ],
        capture_output=True,
        text=True,
        env=_subprocess_env(),
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_brain_init_smoke_in_tmp_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        brain_dir = Path(tmp) / "brain"
        brain = Brain.init(brain_dir, name="Import Integrity", domain="test", interactive=False)
        assert brain.dir == brain_dir.resolve()
        assert (brain_dir / "system.db").exists()
