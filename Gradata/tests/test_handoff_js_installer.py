"""Tests for the JS hook bundling/installer flow (issue #135)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from gradata.hooks._installer import (
    _JS_ASSETS_ROOT,
    generate_settings,
    install_js_hooks,
)


def test_js_assets_bundled_in_package():
    """The two JS hook files must ship as package data."""
    assert _JS_ASSETS_ROOT.is_dir(), f"Missing assets root: {_JS_ASSETS_ROOT}"
    watchdog = _JS_ASSETS_ROOT / "user-prompt" / "handoff-watchdog.js"
    inject = _JS_ASSETS_ROOT / "session-start" / "handoff-inject.js"
    assert watchdog.is_file(), "handoff-watchdog.js missing from assets"
    assert inject.is_file(), "handoff-inject.js missing from assets"
    # Sanity: both should reference the directives the SDK expects.
    assert "handoff-watchdog" in watchdog.read_text(encoding="utf-8")
    assert "handoff" in inject.read_text(encoding="utf-8").lower()


def test_install_js_hooks_copies_files(tmp_path: Path):
    """install_js_hooks must drop both files into the right subdirs."""
    project_dir = tmp_path / "myproj"
    project_dir.mkdir()

    target_root = install_js_hooks(project_dir)
    assert target_root == project_dir / ".claude" / "hooks"

    watchdog = target_root / "user-prompt" / "handoff-watchdog.js"
    inject = target_root / "session-start" / "handoff-inject.js"

    assert watchdog.is_file()
    assert inject.is_file()

    # Content matches the bundled source byte-for-byte
    src_watchdog = _JS_ASSETS_ROOT / "user-prompt" / "handoff-watchdog.js"
    assert watchdog.read_bytes() == src_watchdog.read_bytes()


def test_install_js_hooks_idempotent(tmp_path: Path):
    """Re-running install_js_hooks must not duplicate or clobber unchanged files."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    install_js_hooks(project_dir)
    watchdog = project_dir / ".claude" / "hooks" / "user-prompt" / "handoff-watchdog.js"
    mtime1 = watchdog.stat().st_mtime_ns
    original_bytes = watchdog.read_bytes()

    # Second invocation — same content already on disk, file should be left alone
    install_js_hooks(project_dir)
    assert watchdog.read_bytes() == original_bytes
    # mtime should not have changed (we didn't rewrite)
    assert watchdog.stat().st_mtime_ns == mtime1


def test_install_js_hooks_overwrites_drift(tmp_path: Path):
    """If a user-edited copy diverges from the canonical asset, the SDK rewrites it."""
    project_dir = tmp_path / "p"
    project_dir.mkdir()
    install_js_hooks(project_dir)
    watchdog = project_dir / ".claude" / "hooks" / "user-prompt" / "handoff-watchdog.js"

    watchdog.write_text("// stale", encoding="utf-8")
    install_js_hooks(project_dir)

    # Canonical content restored
    assert "handoff-watchdog" in watchdog.read_text(encoding="utf-8")


def test_generate_settings_registers_js_hooks_with_project_dir(tmp_path: Path):
    """generate_settings(project_dir=...) must include JS hook entries at STANDARD."""
    settings = generate_settings("standard", project_dir=tmp_path)
    hooks = settings["hooks"]

    # JS watchdog lands on UserPromptSubmit
    descs = [g.get("description", "") for g in hooks.get("UserPromptSubmit", [])]
    assert any("handoff watchdog" in d for d in descs)

    descs_ss = [g.get("description", "") for g in hooks.get("SessionStart", [])]
    assert any("handoff inject" in d for d in descs_ss)

    # And the command points to a node invocation under project_dir
    for group in hooks.get("UserPromptSubmit", []):
        if "handoff watchdog" in group.get("description", ""):
            cmd = group["hooks"][0]["command"]
            assert cmd.startswith("node ")
            assert "handoff-watchdog.js" in cmd
            assert str(tmp_path) in cmd


def test_generate_settings_omits_js_hooks_without_project_dir():
    """Without project_dir, JS hooks are not registered (no real on-disk path)."""
    settings = generate_settings("standard", project_dir=None)
    for groups in settings["hooks"].values():
        for g in groups:
            assert "handoff watchdog" not in g.get("description", "")
            assert "handoff inject" not in g.get("description", "")


# ---------------------------------------------------------------------------
# Integration: simulate Claude Code invoking the watchdog with a bridge file
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_handoff_watchdog_emits_directive_when_pressure_high(tmp_path: Path):
    """End-to-end: copy hook into a fresh .claude/, fake the bridge file, run the JS."""
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    install_js_hooks(project_dir)
    watchdog = project_dir / ".claude" / "hooks" / "user-prompt" / "handoff-watchdog.js"
    assert watchdog.is_file()

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    # Fake the statusline bridge file to look like high context pressure.
    session_id = "test-session-135"
    tmpdir = tempfile.gettempdir()
    bridge_path = Path(tmpdir) / f"claude-ctx-{session_id}.json"
    bridge_path.write_text(json.dumps({"used_pct": 85}), encoding="utf-8")

    # Clean up any existing handoff/sentinel for this session
    for name in (f"gradata-handoff-fired-{session_id}.flag",):
        p = Path(tmpdir) / name
        if p.exists():
            p.unlink()

    env = os.environ.copy()
    env["BRAIN_DIR"] = str(brain_dir)
    env["GRADATA_HANDOFF_THRESHOLD"] = "0.5"

    try:
        proc = subprocess.run(
            ["node", str(watchdog)],
            input=json.dumps({"session_id": session_id}),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    finally:
        # cleanup
        if bridge_path.exists():
            bridge_path.unlink()
        sentinel = Path(tmpdir) / f"gradata-handoff-fired-{session_id}.flag"
        if sentinel.exists():
            sentinel.unlink()

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), "watchdog should emit a directive at 85% used"

    payload = json.loads(proc.stdout)
    assert "result" in payload
    assert "<handoff-watchdog" in payload["result"]
    assert "handoff" in payload["result"].lower()
