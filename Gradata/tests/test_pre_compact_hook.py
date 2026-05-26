from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_pre_compact_hook_writes_snapshot_from_stdin(tmp_path: Path) -> None:
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    (brain_dir / "lessons.md").write_text("# Lessons\n\n- Prefer focused tests.\n", encoding="utf-8")

    payload = {
        "hook_event_name": "PreCompact",
        "session_id": "session/abc",
        "trigger": "manual",
        "transcript_path": "/tmp/claude-transcript.jsonl",
    }
    env = os.environ.copy()
    env["BRAIN_DIR"] = str(brain_dir)
    env["GRADATA_TELEMETRY"] = "off"
    env["PYTHONPATH"] = str(Path.cwd() / "src")

    result = subprocess.run(
        [sys.executable, "-m", "gradata.hooks.pre_compact"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        cwd=Path.cwd(),
        env=env,
    )

    assert result.returncode == 0, result.stderr
    snapshot_path = brain_dir / ".precompact-snapshots" / "session-abc.json"
    assert snapshot_path.is_file()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["hook_event_name"] == "PreCompact"
    assert snapshot["session_id"] == "session-abc"
    assert snapshot["payload"] == payload
    assert snapshot["context"]["files"]["lessons.md"]["content"].startswith("# Lessons")
    assert "PreCompact snapshot" in result.stdout
