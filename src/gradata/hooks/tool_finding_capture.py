"""PostToolUse hook: capture test findings and detect when user acts on them."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Bash|Edit|Write",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

def _findings_path() -> Path:
    uid = os.getuid() if hasattr(os, "getuid") else "win"
    user_tmp = Path(tempfile.gettempdir()) / f"gradata-{uid}"
    user_tmp.mkdir(parents=True, exist_ok=True)
    return user_tmp / "findings.json"


FINDINGS_FILE = _findings_path()

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


def _extract_failed_files(output: str) -> list[str]:
    """Extract file paths from test failure output."""
    files = []
    for line in output.splitlines():
        line = line.strip()
        if "FAILED" in line and "::" in line:
            # pytest format: FAILED tests/test_foo.py::test_bar
            parts = line.split("FAILED")[-1].strip()
            file_part = parts.split("::")[0].strip()
            if file_part:
                files.append(file_part)
        elif line.startswith("E") and "File" in line and ".py" in line:
            # Traceback format: E   File "foo.py", line 10
            start = line.find('"')
            end = line.find('"', start + 1)
            if start != -1 and end != -1:
                files.append(line[start + 1:end])
    return files


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
            failed_files = _extract_failed_files(output)
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
