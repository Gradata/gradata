"""Tests for the 3 TikTok-inspired hook templates.

auto_format:      PostToolUse — ruff/prettier after Edit/Write. Fail-open.
notify_waiting:   Stop — native OS notification. Fail-open, no-op in CI.
destructive_block: PreToolUse — curated baseline + rule pattern. Fail-closed
                   ONLY on match; fail-open on any runtime error.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from gradata.enhancements.rule_to_hook import (
    DeterminismCheck,
    EnforcementType,
    classify_rule,
    render_hook,
)

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not installed — TikTok hook tests shell out to Node",
)

TEMPLATE_DIR = Path(__file__).parent.parent / "src" / "gradata" / "hooks" / "templates"


def _write_and_run(js_source: str, payload: dict, *, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    """Render + execute a hook against a payload; return the completed proc."""
    import os
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8", newline="\n",
    ) as f:
        f.write(js_source)
        path = Path(f.name)
    try:
        # Inherit the real environment — Node on Windows crashes if core
        # env vars (SystemRoot, TEMP) are missing. Explicitly clear CI so
        # the notifier's auto-skip doesn't fire unless a test asks for it.
        env = os.environ.copy()
        env["CI"] = ""
        env["GRADATA_BYPASS"] = ""
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["node", str(path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    finally:
        try: path.unlink()
        except OSError: pass


# ---------------------------------------------------------------------------
# auto_format
# ---------------------------------------------------------------------------

class TestAutoFormat:
    def test_template_file_exists(self):
        assert (TEMPLATE_DIR / "auto_format.js.tmpl").is_file()

    def test_classify_runs_formatter_after_edit_rule(self):
        c = classify_rule("Auto-format python files after edit", 0.95)
        assert c.enforcement == EnforcementType.HOOK
        assert c.hook_template == "auto_format"

    def test_render_produces_runnable_js(self):
        c = classify_rule("Auto-format python files after edit", 0.95)
        js = render_hook(c)
        assert js is not None
        assert "#!/usr/bin/env node" in js
        # Sentinel: should NOT still contain unreplaced template markers.
        assert "{{RULE_TEXT}}" not in js
        assert "{{SOURCE_HASH}}" not in js

    def test_skips_non_formattable_extension(self):
        c = classify_rule("Always auto-format after edit", 0.95)
        js = render_hook(c)
        # Tool edited a .rs file — formatter config covers neither ruff nor prettier.
        payload = {"tool_name": "Edit", "tool_input": {"file_path": "main.rs"}}
        proc = _write_and_run(js, payload)
        assert proc.returncode == 0, proc.stderr

    def test_fail_open_when_formatter_missing(self, tmp_path):
        """If ruff isn't installed, hook must exit 0 (advisory-only)."""
        c = classify_rule("Always auto-format after edit", 0.95)
        js = render_hook(c)
        # Point at a nonexistent .py file — ruff (if installed) errors;
        # if ruff is missing, spawnSync errors. Either way hook MUST exit 0.
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "missing.py")}}
        proc = _write_and_run(js, payload)
        assert proc.returncode == 0


# ---------------------------------------------------------------------------
# notify_waiting
# ---------------------------------------------------------------------------

class TestNotifyWaiting:
    def test_template_file_exists(self):
        assert (TEMPLATE_DIR / "notify_waiting.js.tmpl").is_file()

    def test_classify_notify_when_finished_rule(self):
        c = classify_rule("Notify me when Claude finishes", 0.95)
        assert c.enforcement == EnforcementType.HOOK
        assert c.hook_template == "notify_waiting"

    def test_render_produces_runnable_js(self):
        c = classify_rule("Notify me when Claude finishes", 0.95)
        js = render_hook(c)
        assert js is not None
        assert "#!/usr/bin/env node" in js

    def test_noop_in_ci(self):
        """CI=true must short-circuit the notifier (no user to see it)."""
        c = classify_rule("Notify me when Claude finishes", 0.95)
        js = render_hook(c)
        payload = {"tool_name": "Stop", "assistant_message": "Done with task."}
        proc = _write_and_run(js, payload, env_extra={"CI": "true"})
        assert proc.returncode == 0
        # Must not have spawned anything visible — stdout empty.
        assert proc.stdout == ""

    def test_noop_with_bypass(self):
        c = classify_rule("Notify me when Claude finishes", 0.95)
        js = render_hook(c)
        payload = {"tool_name": "Stop", "assistant_message": "Hi"}
        proc = _write_and_run(js, payload, env_extra={"GRADATA_NO_NOTIFY": "1"})
        assert proc.returncode == 0


# ---------------------------------------------------------------------------
# destructive_block
# ---------------------------------------------------------------------------

class TestDestructiveBlock:
    def test_template_file_exists(self):
        assert (TEMPLATE_DIR / "destructive_block.js.tmpl").is_file()

    def test_classify_rm_rf_rule(self):
        c = classify_rule("Never rm -rf", 0.98)
        assert c.enforcement == EnforcementType.HOOK
        assert c.hook_template == "destructive_block"

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf ~",
        "DROP TABLE users",
        "DROP DATABASE prod",
        "git push --force origin main",
        "git reset --hard origin/main",
    ])
    def test_baseline_blocks_classic_killers(self, cmd):
        """Baseline patterns must block even without a rule-specific pattern."""
        c = classify_rule("Never rm -rf", 0.98)
        js = render_hook(c)
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        proc = _write_and_run(js, payload)
        assert proc.returncode == 2, f"Expected block for {cmd!r}, got {proc.returncode} / stdout={proc.stdout} / stderr={proc.stderr}"
        reason = json.loads(proc.stdout)
        assert reason["decision"] == "block"
        assert "BLOCKED" in reason["reason"]

    def test_allow_destructive_env_bypass(self):
        """GRADATA_ALLOW_DESTRUCTIVE=1 must let one command through."""
        c = classify_rule("Never rm -rf", 0.98)
        js = render_hook(c)
        payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}
        proc = _write_and_run(js, payload, env_extra={"GRADATA_ALLOW_DESTRUCTIVE": "1"})
        assert proc.returncode == 0

    def test_benign_command_passes(self):
        c = classify_rule("Never rm -rf", 0.98)
        js = render_hook(c)
        payload = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        proc = _write_and_run(js, payload)
        assert proc.returncode == 0

    def test_malformed_input_is_fail_open(self):
        """A garbage stdin payload must never crash/block the session."""
        c = classify_rule("Never rm -rf", 0.98)
        js = render_hook(c)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8", newline="\n",
        ) as f:
            f.write(js)
            path = Path(f.name)
        try:
            proc = subprocess.run(
                ["node", str(path)],
                input="NOT JSON",
                capture_output=True, text=True, timeout=5,
            )
            assert proc.returncode == 0
        finally:
            try: path.unlink()
            except OSError: pass


# ---------------------------------------------------------------------------
# Installer registry
# ---------------------------------------------------------------------------

def test_template_registry_lists_three_new_templates():
    from gradata.hooks._installer import TEMPLATE_REGISTRY

    names = {t[0] for t in TEMPLATE_REGISTRY}
    assert {"auto_format", "notify_waiting", "destructive_block"} <= names
