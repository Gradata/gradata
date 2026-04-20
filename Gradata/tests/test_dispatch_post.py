"""Tests for the consolidated PostToolUse dispatcher."""
from __future__ import annotations

from unittest.mock import patch

from gradata.hooks import dispatch_post


def test_unknown_tool_returns_none():
    assert dispatch_post.main({"tool_name": "Glob"}) is None


def test_no_tool_returns_none():
    assert dispatch_post.main({}) is None


def test_edit_routes_to_correct_handlers():
    """An Edit tool call must invoke auto_correct and tool_finding_capture,
    but NOT tool_failure_emit (which only handles Bash)."""
    called: list[str] = []

    def fake_invoke(name: str, data: dict) -> dict | None:
        called.append(name)
        return None

    with patch.object(dispatch_post, "_invoke", side_effect=fake_invoke):
        dispatch_post.main({"tool_name": "Edit", "file_path": "/x"})

    assert "auto_correct" in called
    assert "tool_finding_capture" in called
    assert "tool_failure_emit" not in called


def test_bash_routes_to_correct_handlers():
    called: list[str] = []

    def fake_invoke(name: str, data: dict) -> dict | None:
        called.append(name)
        return None

    with patch.object(dispatch_post, "_invoke", side_effect=fake_invoke):
        dispatch_post.main({"tool_name": "Bash", "command": "ls"})

    assert "tool_failure_emit" in called
    assert "tool_finding_capture" in called
    assert "auto_correct" not in called


def test_results_merged_with_concatenated_strings():
    """When multiple handlers return results, ``result`` strings concatenate
    (newline-joined) and other fields are merged."""
    def fake_invoke(name: str, data: dict) -> dict | None:
        if name == "auto_correct":
            return {"result": "captured", "severity": "minor"}
        if name == "tool_finding_capture":
            return {"result": "linted", "extra": 42}
        return None

    with patch.object(dispatch_post, "_invoke", side_effect=fake_invoke):
        out = dispatch_post.main({"tool_name": "Edit"})

    assert out is not None
    assert "captured" in out["result"]
    assert "linted" in out["result"]
    assert out["severity"] == "minor"
    assert out["extra"] == 42


def test_handler_exception_does_not_block_others():
    """A failing handler must not prevent later handlers from running."""
    def fake_invoke(name: str, data: dict) -> dict | None:
        if name == "auto_correct":
            raise RuntimeError("boom")  # _invoke catches this internally
        return {"result": f"ran-{name}"}

    # _invoke wraps the import+call in try/except, so we patch lower:
    # simulate the post-suppression behavior directly.
    def safe_invoke(name: str, data: dict) -> dict | None:
        try:
            return fake_invoke(name, data)
        except Exception:
            return None

    with patch.object(dispatch_post, "_invoke", side_effect=safe_invoke):
        out = dispatch_post.main({"tool_name": "Edit"})

    assert out is not None
    assert "ran-tool_finding_capture" in out["result"]


def test_all_handlers_return_none_yields_none():
    with patch.object(dispatch_post, "_invoke", return_value=None):
        assert dispatch_post.main({"tool_name": "Edit"}) is None


def test_tool_field_fallback():
    """Some hook payloads use 'tool' instead of 'tool_name'."""
    called: list[str] = []

    def fake_invoke(name: str, data: dict) -> dict | None:
        called.append(name)
        return None

    with patch.object(dispatch_post, "_invoke", side_effect=fake_invoke):
        dispatch_post.main({"tool": "Bash", "command": "ls"})

    assert "tool_failure_emit" in called
