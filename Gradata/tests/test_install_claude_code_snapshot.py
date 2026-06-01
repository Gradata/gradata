"""Snapshot test: gradata install --agent claude-code produces CC settings
with the expected lifecycle hook coverage.

GRA-1211 / EPIC GRA-1198 / GH #206

This test pins the exact .claude/settings.json content produced by
``gradata install --agent claude-code`` so we don't regress hook coverage
as we fold slash commands and lifecycle hooks into the SDK.

Current state (GRA-1211): all Claude Code lifecycles used by Gradata are wired.
"""

from __future__ import annotations

import json
from pathlib import Path

from gradata.hooks.adapters._base import InstallResult, get_adapter


def _install_agent(agent: str, brain_dir: Path, config_path: Path) -> InstallResult:
    """Call the adapter's install() directly — same as ``gradata install --agent``."""
    adapter = get_adapter(agent)
    return adapter.install(brain_dir, config_path)


# ── Lifecycle → hook module + adapter wiring status ──────────────────────
ALL_HOOK_LIFECYCLES: dict[str, tuple[str, str]] = {
    "PreToolUse":       ("gradata.hooks.inject_brain_rules", "wired"),
    "PostToolUse":      ("gradata.hooks.auto_correct",        "wired"),
    "Stop":             ("gradata.hooks.session_close",       "wired"),
    "PreCompact":       ("gradata.hooks.pre_compact",         "wired"),
    "UserPromptSubmit": ("gradata.hooks.context_inject",      "wired"),
}


def _assert_wired_lifecycles(hooks: dict) -> None:
    """Assert every lifecycle that should currently be wired IS present."""
    for lifecycle, (_module, status) in ALL_HOOK_LIFECYCLES.items():
        if status == "wired":
            assert lifecycle in hooks, (
                f"{lifecycle} hook should be wired but is missing from settings.json.\n"
                f"Got hook event keys: {sorted(hooks.keys())}\n"
                "Check that the adapter install() method writes this lifecycle."
            )


def _assert_no_stray_keys(hooks: dict) -> None:
    """Assert no unexpected hook event keys exist in the output."""
    wired_keys = {k for k, (_, s) in ALL_HOOK_LIFECYCLES.items() if s == "wired"}
    actual_keys = set(hooks.keys())
    unexpected = actual_keys - wired_keys
    assert not unexpected, (
        f"Unexpected hook event keys in snapshot: {sorted(unexpected)}\n"
        f"Expected only: {sorted(wired_keys)}.\n"
        "If a new lifecycle was intentionally wired, update ALL_HOOK_LIFECYCLES above."
    )


def _assert_lifecycle_commands_reference_expected_modules(hooks: dict) -> None:
    """Verify every wired lifecycle command points at the expected hook module."""
    for lifecycle, (module, status) in ALL_HOOK_LIFECYCLES.items():
        if status != "wired":
            continue
        entries = hooks.get(lifecycle, [])
        assert isinstance(entries, list) and entries, (
            f"{lifecycle} should have at least 1 hook entry, got {entries}"
        )
        commands = [
            hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
        ]
        matching = [cmd for cmd in commands if module in cmd]
        assert matching, (
            f"{lifecycle} should contain {module} hook.\n"
            f"Entries: {json.dumps(entries, indent=2)}"
        )
        for cmd in matching:
            assert "BRAIN_DIR=" in cmd, f"BRAIN_DIR not set in hook command: {cmd}"


def _snapshot_path(test_file: str) -> Path:
    return Path(test_file).parent / "snapshots" / "install_claude_code_settings.json"


def _normalized_snapshot(settings: dict) -> str:
    """Return normalized settings.json snapshot text.

    Brain-directory paths are normalized to a stable ``__BRAIN_DIR__``
    placeholder so the snapshot file doesn't change on every test run
    (tmp_paths are random per pytest invocation).
    """
    import re

    serialized = json.dumps(settings, indent=2, sort_keys=True)
    # Normalize: BRAIN_DIR=/tmp/pytest-N/.../brain → BRAIN_DIR=__BRAIN_DIR__
    serialized = re.sub(r"BRAIN_DIR=/tmp/[^ ]+/brain", "BRAIN_DIR=__BRAIN_DIR__", serialized)
    # Normalize: hook signature ID
    serialized = re.sub(
        r'"gradata:claude-code:/tmp/[^"]+brain"',
        '"gradata:claude-code:__BRAIN_DIR__"',
        serialized,
    )
    return serialized + "\n"


def _assert_matches_snapshot(settings: dict, test_file: str) -> None:
    snapshot_file = _snapshot_path(test_file)
    expected = snapshot_file.read_text(encoding="utf-8")
    actual = _normalized_snapshot(settings)
    assert actual == expected, (
        f"Claude Code settings snapshot mismatch: {snapshot_file}\n"
        "Regenerate the snapshot intentionally if adapter output changed."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


def test_install_claude_code_produces_correct_settings(tmp_path: Path) -> None:
    """Run install_agent and assert all expected lifecycles are present."""
    brain = tmp_path / "brain"
    brain.mkdir()

    config_path = tmp_path / ".claude" / "settings.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")

    # Install via adapter API (same as `gradata install --agent claude-code`)
    result = _install_agent("claude-code", brain, config_path)

    assert result.action in ("added", "already_present"), (
        f"Install failed: action={result.action}, message={result.message}"
    )
    assert config_path.exists(), "settings.json should exist after install"

    settings = json.loads(config_path.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})

    # ── Assertions ───────────────────────────────────────────────────────
    _assert_wired_lifecycles(hooks)
    _assert_lifecycle_commands_reference_expected_modules(hooks)
    _assert_no_stray_keys(hooks)
    _assert_matches_snapshot(settings, __file__)


def test_install_claude_code_is_idempotent(tmp_path: Path) -> None:
    """Re-running install must not create duplicate hook entries."""
    brain = tmp_path / "brain"
    brain.mkdir()

    config_path = tmp_path / ".claude" / "settings.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")

    # First install
    r1 = _install_agent("claude-code", brain, config_path)
    assert r1.action in ("added", "already_present"), r1.message
    s1 = json.loads(config_path.read_text(encoding="utf-8"))

    # Second install — must not add duplicates
    r2 = _install_agent("claude-code", brain, config_path)
    assert r2.action == "already_present", (
        f"Second install should report already_present, got {r2.action}: {r2.message}"
    )
    s2 = json.loads(config_path.read_text(encoding="utf-8"))

    assert s1 == s2, (
        f"Second install changed settings content.\n"
        f"Before: {json.dumps(s1, indent=2, sort_keys=True)}\n"
        f"After:  {json.dumps(s2, indent=2, sort_keys=True)}"
    )


def test_install_claude_code_respects_existing_settings(tmp_path: Path) -> None:
    """Install should not destroy user-owned hooks in settings.json."""
    brain = tmp_path / "brain"
    brain.mkdir()

    config_path = tmp_path / ".claude" / "settings.json"
    config_path.parent.mkdir(parents=True)

    # Pre-populate with user-owned hooks
    pre_existing = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo 'user hook'",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "echo 'user stop hook'",
                        }
                    ],
                }
            ],
        }
    }
    config_path.write_text(json.dumps(pre_existing, indent=2), encoding="utf-8")

    result = _install_agent("claude-code", brain, config_path)
    assert result.action in ("added", "already_present"), result.message

    settings = json.loads(config_path.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})

    # User's Stop hook preserved
    stop_entries = hooks.get("Stop", [])
    user_stop_found = any(
        "user stop hook" in hook.get("command", "")
        for entry in stop_entries
        for hook in entry.get("hooks", [])
    )
    assert user_stop_found, f"User's Stop hook was destroyed. Stop entries: {stop_entries}"

    # Gradata hook added alongside user hooks
    pre_tool = hooks.get("PreToolUse", [])
    gradata_found = any(
        "gradata.hooks.inject_brain_rules" in hook.get("command", "")
        for entry in pre_tool
        for hook in entry.get("hooks", [])
    )
    assert gradata_found, f"Gradata hook not installed. PreToolUse: {pre_tool}"

    user_hook_found = any(
        "user hook" in hook.get("command", "")
        for entry in pre_tool
        for hook in entry.get("hooks", [])
    )
    assert user_hook_found, f"User's PreToolUse hook was destroyed. PreToolUse: {pre_tool}"


def test_install_claude_code_all_lifecycles_documented(tmp_path: Path) -> None:
    """All lifecycles in the GRA-1211 acceptance criteria must be wired."""
    brain = tmp_path / "brain"
    brain.mkdir()

    config_path = tmp_path / ".claude" / "settings.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{}", encoding="utf-8")

    _install_agent("claude-code", brain, config_path)
    settings = json.loads(config_path.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})

    # Report which lifecycles are missing (informational, not assertion failure)
    missing = [
        lifecycle
        for lifecycle, (_module, status) in ALL_HOOK_LIFECYCLES.items()
        if status == "wired" and lifecycle not in hooks
    ]
    pending = [
        lifecycle
        for lifecycle, (_module, status) in ALL_HOOK_LIFECYCLES.items()
        if status == "pending"
    ]

    assert not missing, (
        f"Lifecycles wired but missing from output: {missing}\n"
        f"Check adapter install()."
    )

    assert not pending, f"All GRA-1211 lifecycles should be wired, still pending: {pending}"
