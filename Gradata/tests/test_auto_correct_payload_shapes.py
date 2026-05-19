"""Regression tests for auto_correct hook handling both Claude Code and Hermes payload shapes.

History: pre-2026-05-19, ``_extract_correction`` only matched the Claude
Code stdin shape (``tool_name`` in ``Edit``/``Write`` + args under
``"input"``). Hermes Agent sends ``{"hook_event_name": "post_tool_call",
"tool_name": "patch", "tool_input": {...}}`` instead, so every Hermes
post_tool_call hook fired but captured zero corrections. The user's
events.jsonl went idle for 43h+ while the fleet ran thousands of edits.

This test pins both shapes so the regression cannot recur silently.
"""

from __future__ import annotations

import json

from gradata.hooks.auto_correct import _extract_correction, process_hook_input

# ---- Pure unit tests for _extract_correction -------------------------------


class TestExtractCorrectionClaudeCode:
    """Pin the original Claude Code stdin shape."""

    def test_edit_with_old_and_new_string(self) -> None:
        payload = {
            "tool_name": "Edit",
            "input": {"old_string": "Dear Sir", "new_string": "Hey there"},
        }
        assert _extract_correction(payload) == ("Dear Sir", "Hey there")

    def test_edit_unchanged_returns_none(self) -> None:
        payload = {"tool_name": "Edit", "input": {"old_string": "same", "new_string": "same"}}
        assert _extract_correction(payload) is None

    def test_write_needs_tool_output_old_content(self) -> None:
        payload = {"tool_name": "Write", "input": {"content": "new file body"}}
        tool_output = {"old_content": "previous file body"}
        result = _extract_correction(payload, tool_output)
        assert result == ("previous file body", "new file body")


class TestExtractCorrectionHermes:
    """The regression these tests pin: Hermes-shape payloads must capture."""

    def test_hermes_patch_tool_extracts_correction(self) -> None:
        payload = {
            "hook_event_name": "post_tool_call",
            "tool_name": "patch",
            "tool_input": {
                "path": "/tmp/foo.txt",
                "old_string": "Dear Sir",
                "new_string": "Hey there",
            },
            "session_id": "test",
            "cwd": "/tmp",
            "extra": {},
        }
        assert _extract_correction(payload) == ("Dear Sir", "Hey there")

    def test_hermes_mcp_patch_tool_extracts_correction(self) -> None:
        """Tools dispatched via MCP get an mcp_ prefix; strip it for matching."""
        payload = {
            "hook_event_name": "post_tool_call",
            "tool_name": "mcp_Patch",
            "tool_input": {"old_string": "foo", "new_string": "bar"},
        }
        assert _extract_correction(payload) == ("foo", "bar")

    def test_hermes_write_file_tool_needs_old_content(self) -> None:
        payload = {
            "hook_event_name": "post_tool_call",
            "tool_name": "write_file",
            "tool_input": {"path": "/tmp/foo.txt", "content": "new body"},
        }
        tool_output = {"old_content": "previous body"}
        assert _extract_correction(payload, tool_output) == ("previous body", "new body")

    def test_hermes_terminal_tool_returns_none(self) -> None:
        """Non-edit tools must not produce false corrections."""
        payload = {
            "hook_event_name": "post_tool_call",
            "tool_name": "terminal",
            "tool_input": {"command": "ls /tmp"},
        }
        assert _extract_correction(payload) is None

    def test_hermes_unchanged_strings_returns_none(self) -> None:
        payload = {
            "tool_name": "patch",
            "tool_input": {"old_string": "same", "new_string": "same"},
        }
        assert _extract_correction(payload) is None


class TestExtractCorrectionMalformedInput:
    def test_missing_args_returns_none(self) -> None:
        assert _extract_correction({"tool_name": "Edit"}) is None

    def test_args_not_a_dict_returns_none(self) -> None:
        assert _extract_correction({"tool_name": "Edit", "input": "not a dict"}) is None

    def test_empty_payload_returns_none(self) -> None:
        assert _extract_correction({}) is None


# ---- Integration test: process_hook_input end-to-end ----------------------


class TestProcessHookInputHermes:
    """Exercise the full stdin → response flow with a real Brain.

    These hit the brain at $BRAIN_DIR (set by conftest tmp_path fixture).
    The point is: a Hermes-shape stdin must result in ``captured: true``.
    """

    def test_hermes_patch_produces_captured_true(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BRAIN_DIR", str(tmp_path / "brain"))
        stdin = json.dumps(
            {
                "hook_event_name": "post_tool_call",
                "tool_name": "patch",
                "tool_input": {
                    "old_string": "Dear Sir or Madam",
                    "new_string": "Hey there",
                },
            }
        )
        result = process_hook_input(stdin)
        assert result.get("captured") is True, f"expected capture, got {result}"
        # Severity values vary by edit distance + content; the important
        # assertion is captured=True. severity exists for diagnostic only.
        assert "severity" in result
