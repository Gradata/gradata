"""Tests for Gradata hook foundation modules."""
import json
import os
from unittest.mock import patch

from gradata.hooks._profiles import Profile
from gradata.hooks._base import (
    get_profile, should_run, read_input, output_result, output_block, run_hook,
)
from gradata.hooks._installer import generate_settings, HOOK_REGISTRY


# _profiles.py tests
def test_profile_ordering():
    assert Profile.MINIMAL < Profile.STANDARD < Profile.STRICT

def test_profile_values():
    assert Profile.MINIMAL == 0
    assert Profile.STANDARD == 1
    assert Profile.STRICT == 2


# _base.py tests
def test_get_profile_default():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("GRADATA_HOOK_PROFILE", None)
        assert get_profile() == Profile.STANDARD

def test_get_profile_from_env():
    with patch.dict(os.environ, {"GRADATA_HOOK_PROFILE": "strict"}):
        assert get_profile() == Profile.STRICT

def test_should_run_standard_allows_minimal():
    with patch.dict(os.environ, {"GRADATA_HOOK_PROFILE": "standard"}):
        assert should_run(Profile.MINIMAL) is True

def test_should_run_minimal_blocks_standard():
    with patch.dict(os.environ, {"GRADATA_HOOK_PROFILE": "minimal"}):
        assert should_run(Profile.STANDARD) is False

def test_read_input_valid_json():
    data = {"tool_name": "Write", "tool_input": {"file_path": "test.py"}}
    result = read_input(json.dumps(data))
    assert result == data

def test_read_input_empty():
    assert read_input("") is None

def test_read_input_invalid_json():
    assert read_input("not json {{{") is None

def test_output_result(capsys):
    output_result("some context")
    out = json.loads(capsys.readouterr().out)
    assert out == {"result": "some context"}

def test_output_block(capsys):
    output_block("dangerous operation")
    out = json.loads(capsys.readouterr().out)
    assert out == {"decision": "block", "reason": "dangerous operation"}

def test_run_hook_skips_wrong_profile(capsys):
    meta = {"profile": Profile.STRICT}
    called = []
    def handler(data):
        called.append(True)
        return {"result": "hello"}
    with patch.dict(os.environ, {"GRADATA_HOOK_PROFILE": "minimal"}):
        run_hook(handler, meta, raw_input='{"tool_name":"Write"}')
    assert called == []
    assert capsys.readouterr().out == ""

def test_run_hook_calls_handler(capsys):
    meta = {"profile": Profile.MINIMAL}
    def handler(data):
        return {"result": "injected"}
    run_hook(handler, meta, raw_input='{"tool_name":"Write"}')
    out = json.loads(capsys.readouterr().out)
    assert out == {"result": "injected"}

def test_run_hook_silent_on_exception(capsys):
    meta = {"profile": Profile.MINIMAL}
    def handler(data):
        raise RuntimeError("boom")
    run_hook(handler, meta, raw_input='{"tool_name":"Write"}')
    assert capsys.readouterr().out == ""


# _installer.py tests
def test_hook_registry_not_empty():
    assert len(HOOK_REGISTRY) >= 16

def test_generate_settings_minimal():
    settings = generate_settings(profile="minimal")
    all_commands = []
    for event_hooks in settings["hooks"].values():
        for group in event_hooks:
            for hook in group.get("hooks", []):
                all_commands.append(hook["command"])
    assert any("auto_correct" in c for c in all_commands)
    assert any("inject_brain_rules" in c for c in all_commands)
    assert not any("secret_scan" in c for c in all_commands)

def test_generate_settings_standard():
    settings = generate_settings(profile="standard")
    all_commands = []
    for event_hooks in settings["hooks"].values():
        for group in event_hooks:
            for hook in group.get("hooks", []):
                all_commands.append(hook["command"])
    assert any("secret_scan" in c for c in all_commands)
    assert any("inject_brain_rules" in c for c in all_commands)

def test_generate_settings_has_all_events():
    settings = generate_settings(profile="strict")
    events = set(settings["hooks"].keys())
    assert "PreToolUse" in events
    assert "PostToolUse" in events
    assert "SessionStart" in events
    assert "Stop" in events
    assert "UserPromptSubmit" in events
