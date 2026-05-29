from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_offline_quickstart_smoke_script_runs_without_credentials(tmp_path):
    script = Path(__file__).resolve().parents[1] / "examples" / "offline_quickstart_smoke.py"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["HOME"] = str(tmp_path / "home")
    env["GRADATA_TELEMETRY"] = "0"
    env.pop("GRADATA_API_KEY", None)
    env.pop("GRADATA_CLOUD_API_BASE", None)

    proc = subprocess.run(
        [sys.executable, str(script)],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["cli_manifest_domain"] == "Sales"
    assert payload["events"] == {"OUTPUT": 1, "CORRECTION": 1}
    assert payload["sdk_version"]
