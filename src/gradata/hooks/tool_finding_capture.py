"""PostToolUse hook: capture test findings and detect when user acts on them."""
from __future__ import annotations

import hashlib as _fp_hashlib
import json
import os
import tempfile
from pathlib import Path

from ._base import run_hook
from ._base import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Bash|Edit|Write",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

# Per-user, per-project findings file (Windows-safe tempdir with fallback).
if hasattr(os, "getuid"):
    _fp_uid: str | int = os.getuid()
else:
    try:
        _fp_uid = os.getlogin()
    except OSError:
        _fp_uid = f"pid{os.getpid()}"
_fp_tmp = Path(tempfile.gettempdir()) / f"gradata-{_fp_uid}"
try:
    _fp_tmp.mkdir(parents=True, exist_ok=True)
except OSError:
    _fp_tmp = Path(tempfile.gettempdir())
_fp_proj = os.environ.get("CLAUDE_PROJECT_DIR", "")
FINDINGS_FILE = (
    _fp_tmp / f"findings-{_fp_hashlib.md5(_fp_proj.encode()).hexdigest()[:8]}.json"
    if _fp_proj else _fp_tmp / "findings.json"
)

# Refined patterns that indicate actual test failures
TEST_FAILURE_INDICATORS = [
    "FAILED tests/",
    "FAILED src/",
    "AssertionError",
    "AssertError",
    "assert ",
    "E       ",
    "ERRORS",
    "short test summary",
]


def _load_findings() -> list[dict]:
    try:
        if FINDINGS_FILE.exists():
            return json.loads(FINDINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_findings(findings: list[dict]) -> None:
    """Atomically write findings via temp file + rename to avoid corruption
    from concurrent hook processes writing simultaneously."""
    try:
        content = json.dumps(findings[-20:], indent=2)
        tmp = FINDINGS_FILE.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(FINDINGS_FILE)  # atomic on POSIX, near-atomic on Windows
    except Exception:
        pass


def _has_test_failure(output: str) -> bool:
    return any(indicator in output for indicator in TEST_FAILURE_INDICATORS)


def main(data: dict) -> dict | None:
    try:
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        output = data.get("tool_output", "") or ""
        if isinstance(output, dict):
            output = str(output)

        if tool_name == "Bash" and _has_test_failure(output):
            failed_files: list[str] = []
            for _eff_l in output.splitlines():
                _eff_l = _eff_l.strip()
                if "FAILED" in _eff_l and "::" in _eff_l:
                    _eff_p = _eff_l.split("FAILED")[-1].strip().split("::")[0].strip()
                    if _eff_p:
                        failed_files.append(_eff_p)
                elif _eff_l.startswith("E") and "File" in _eff_l and ".py" in _eff_l:
                    _eff_s = _eff_l.find('"')
                    _eff_e = _eff_l.find('"', _eff_s + 1)
                    if _eff_s != -1 and _eff_e != -1:
                        failed_files.append(_eff_l[_eff_s + 1:_eff_e])
            if failed_files:
                findings = _load_findings()
                findings.append({
                    "files": failed_files,
                    "preview": output[:500],
                    "command": tool_input.get("command", "")[:200],
                })
                _save_findings(findings)
            return None

        if tool_name in ("Edit", "Write"):
            file_path = tool_input.get("file_path", "")
            if not file_path:
                return None

            findings = _load_findings()
            if not findings:
                return None

            file_basename = Path(file_path).name
            for finding in findings:
                for f in finding.get("files", []):
                    if Path(f).name == file_basename:
                        # User is editing a file related to a test finding
                        _save_findings([])  # Clear acted-on findings
                        return {"result": "Correction captured from test finding"}

        return None
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
