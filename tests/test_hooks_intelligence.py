"""Tests for intelligence + completeness hooks (Phase 4-5)."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── agent_precontext ──

from gradata.hooks.agent_precontext import main as precontext_main


def test_agent_precontext_injects_rules(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text(
        "2026-04-01 [RULE:0.92] PROCESS: Always plan first\n"
        "2026-04-01 [PATTERN:0.65] CODE: Use type hints\n"
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = precontext_main({
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "general", "prompt": "do stuff"},
        })
    assert result is not None
    assert "agent-rules" in result["result"]
    assert "Always plan first" in result["result"]


def test_agent_precontext_no_brain():
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "/nonexistent/path/xyz"}):
        result = precontext_main({
            "tool_name": "Agent",
            "tool_input": {"subagent_type": "general"},
        })
    assert result is None


def test_agent_precontext_scope_matching(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text(
        "2026-04-01 [RULE:0.92] SALES: Always check pipeline first\n"
        "2026-04-01 [RULE:0.91] CODE: Write tests before code\n"
    )
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = precontext_main({
            "tool_name": "Agent",
            "tool_input": {"description": "research the sales pipeline"},
        })
    assert result is not None
    # Sales rule should rank higher for sales-related agent
    lines = result["result"].split("\n")
    assert any("SALES" in l for l in lines)


# ── agent_graduation ──

from gradata.hooks.agent_graduation import main as graduation_main


def test_agent_graduation_emits_event(tmp_path):
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        with patch("gradata._events.emit") as mock_emit:
            result = graduation_main({
                "tool_name": "Agent",
                "tool_input": {"subagent_type": "code"},
                "tool_output": "Here is the result of the agent work",
            })
    assert result is None  # fire-and-forget
    mock_emit.assert_called_once()
    call_kwargs = mock_emit.call_args
    assert call_kwargs[0][0] == "AGENT_OUTCOME"


def test_agent_graduation_no_brain():
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "/nonexistent/xyz"}):
        result = graduation_main({
            "tool_name": "Agent",
            "tool_input": {},
            "tool_output": "done",
        })
    assert result is None


# ── tool_failure_emit ──

from gradata.hooks.tool_failure_emit import main as failure_main


def test_tool_failure_detects_error(tmp_path):
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        with patch("gradata._events.emit") as mock_emit:
            result = failure_main({
                "tool_name": "Bash",
                "tool_input": {"command": "npm install"},
                "tool_output": "npm ERR! ECONNREFUSED connection refused",
            })
    assert result is None  # fire-and-forget
    mock_emit.assert_called_once()
    assert mock_emit.call_args[0][0] == "TOOL_FAILURE"


def test_tool_failure_ignores_clean_output():
    result = failure_main({
        "tool_name": "Bash",
        "tool_input": {"command": "echo hello"},
        "tool_output": "hello\nAll tests passed.",
    })
    assert result is None


def test_tool_failure_filters_false_positive():
    result = failure_main({
        "tool_name": "Bash",
        "tool_input": {"command": "grep errors"},
        "tool_output": "no errors found in the output",
    })
    assert result is None


# ── tool_finding_capture ──

from gradata.hooks.tool_finding_capture import main as finding_main, FINDINGS_FILE


def test_finding_capture_stores_test_failure():
    # Clean up any prior findings
    if FINDINGS_FILE.exists():
        FINDINGS_FILE.unlink()

    result = finding_main({
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/"},
        "tool_output": "FAILED tests/test_foo.py::test_bar - AssertionError\nshort test summary",
    })
    assert result is None  # storing only, no output
    assert FINDINGS_FILE.exists()
    findings = json.loads(FINDINGS_FILE.read_text())
    assert len(findings) >= 1
    assert "test_foo.py" in findings[0]["files"][0]

    # Clean up
    FINDINGS_FILE.unlink(missing_ok=True)


def test_finding_capture_detects_acted_on():
    # Pre-populate a finding
    FINDINGS_FILE.write_text(json.dumps([{
        "files": ["tests/test_foo.py"],
        "preview": "FAILED",
        "command": "pytest",
    }]))

    result = finding_main({
        "tool_name": "Edit",
        "tool_input": {"file_path": "tests/test_foo.py", "old_string": "x", "new_string": "y"},
    })
    assert result is not None
    assert "Correction captured" in result["result"]

    # Clean up
    FINDINGS_FILE.unlink(missing_ok=True)


def test_finding_capture_noop_no_failure():
    result = finding_main({
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "tool_output": "file1.py  file2.py",
    })
    assert result is None


# ── context_inject ──

from gradata.hooks.context_inject import main as context_main


def test_context_inject_returns_context(tmp_path):
    mock_brain = MagicMock()
    mock_brain.search.return_value = [{"text": "Relevant brain knowledge here"}]

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        with patch("gradata.brain.Brain", return_value=mock_brain):
            result = context_main({"message": "How do I set up the pipeline for new prospects?"})

    assert result is not None
    assert "brain context:" in result["result"]
    assert "Relevant brain knowledge" in result["result"]


def test_context_inject_skips_short_message():
    result = context_main({"message": "ok"})
    assert result is None


def test_context_inject_skips_slash_command():
    result = context_main({"message": "/commit all changes"})
    assert result is None


# ── config_validate ──

from gradata.hooks.config_validate import main as validate_main


def test_config_validate_clean(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {}}))

    with patch("gradata.hooks.config_validate._find_settings", return_value=settings):
        result = validate_main({})
    assert result is None  # No warnings


def test_config_validate_invalid_json(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{invalid json")

    with patch("gradata.hooks.config_validate._find_settings", return_value=settings):
        result = validate_main({})
    assert result is not None
    assert "Invalid JSON" in result["result"]


def test_config_validate_no_settings():
    with patch("gradata.hooks.config_validate._find_settings", return_value=None):
        result = validate_main({})
    assert result is None


# ── pre_compact ──

from gradata.hooks.pre_compact import main as compact_main


def test_pre_compact_saves_snapshot(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text("2026-04-01 [RULE:0.92] PROCESS: Plan first\n# header\n")
    loop_state = tmp_path / "loop-state.md"
    loop_state.write_text("## Session 42\n")

    snapshot_path = Path(tempfile.gettempdir()) / "gradata-compact-snapshot.json"
    snapshot_path.unlink(missing_ok=True)

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        result = compact_main({"type": "auto"})

    assert result is not None
    assert "State saved" in result["result"]
    assert snapshot_path.exists()
    data = json.loads(snapshot_path.read_text())
    assert data["session"] == 42
    snapshot_path.unlink(missing_ok=True)


def test_pre_compact_no_brain():
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "/nonexistent/xyz"}):
        result = compact_main({})
    assert result is None


# ── duplicate_guard ──

from gradata.hooks.duplicate_guard import main as guard_main, _similarity, _normalize


def test_duplicate_guard_blocks_similar(tmp_path):
    # Create a watched dir with existing file
    hooks_dir = tmp_path / "src" / "gradata" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "auto_correct.py").write_text("# existing")
    (hooks_dir / "__init__.py").write_text("")

    with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
        result = guard_main({
            "tool_input": {
                "file_path": str(tmp_path / "src" / "gradata" / "hooks" / "auto_corrector.py"),
            },
        })
    assert result is not None
    assert result["decision"] == "block"
    assert "auto_correct.py" in result["reason"]


def test_duplicate_guard_allows_unique(tmp_path):
    hooks_dir = tmp_path / "src" / "gradata" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "auto_correct.py").write_text("# existing")

    with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
        result = guard_main({
            "tool_input": {
                "file_path": str(tmp_path / "src" / "gradata" / "hooks" / "brand_new_thing.py"),
            },
        })
    assert result is None


def test_duplicate_guard_allows_existing_file(tmp_path):
    hooks_dir = tmp_path / "src" / "gradata" / "hooks"
    hooks_dir.mkdir(parents=True)
    target = hooks_dir / "auto_correct.py"
    target.write_text("# existing")

    with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
        result = guard_main({
            "tool_input": {"file_path": str(target)},
        })
    assert result is None  # Overwriting existing file is fine


def test_similarity_function():
    assert _similarity("autocorrect", "autocorrector") > 0.8
    assert _similarity("abc", "xyz") < 0.3


def test_normalize_function():
    assert _normalize("my_hook_v2.py") == "myhookv"
    assert _normalize("AutoCorrect.py") == "autocorrect"


# ── brain_maintain ──

from gradata.hooks.brain_maintain import main as maintain_main


def test_brain_maintain_runs_silently(tmp_path):
    lessons = tmp_path / "lessons.md"
    lessons.write_text("2026-04-01 [RULE:0.92] PROCESS: Plan first\n")

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        with patch("gradata._query.fts_index") as mock_fts:
            with patch("gradata._brain_manifest.generate_manifest", return_value={}):
                with patch("gradata._brain_manifest.write_manifest"):
                    result = maintain_main({})
    assert result is None  # Silent maintenance
    mock_fts.assert_called()


def test_brain_maintain_no_brain():
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "/nonexistent/xyz"}):
        result = maintain_main({})
    assert result is None


# ── session_persist ──

from gradata.hooks.session_persist import main as persist_main


def test_session_persist_writes_handoff(tmp_path):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    loop_state = brain_dir / "loop-state.md"
    loop_state.write_text("## Session 99\n")

    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(brain_dir)}):
        with patch("gradata.hooks.session_persist._get_modified_files", return_value=["src/foo.py"]):
            result = persist_main({})

    assert result is None  # Silent
    persist_dir = brain_dir / "sessions" / "persist"
    assert persist_dir.exists()
    files = list(persist_dir.glob("session-*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["session"] == 99
    assert "src/foo.py" in data["modified_files"]


def test_session_persist_no_brain():
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": "/nonexistent/xyz"}):
        result = persist_main({})
    assert result is None


# ── implicit_feedback ──

from gradata.hooks.implicit_feedback import main as feedback_main


def test_implicit_feedback_detects_negation():
    result = feedback_main({"message": "No, that's wrong. Do it differently."})
    assert result is not None
    assert "IMPLICIT FEEDBACK" in result["result"]
    assert "negation" in result["result"]


def test_implicit_feedback_detects_reminder():
    result = feedback_main({"message": "I told you to always plan first before building."})
    assert result is not None
    assert "reminder" in result["result"]


def test_implicit_feedback_detects_challenge():
    result = feedback_main({"message": "Are you sure that's correct? It doesn't look right."})
    assert result is not None
    assert "challenge" in result["result"]


def test_implicit_feedback_ignores_neutral():
    result = feedback_main({"message": "Please build a new feature for the dashboard."})
    assert result is None


def test_implicit_feedback_emits_event(tmp_path):
    with patch.dict(os.environ, {"GRADATA_BRAIN_DIR": str(tmp_path)}):
        with patch("gradata._events.emit") as mock_emit:
            result = feedback_main({"message": "I told you not to do that, are you sure?"})
    assert result is not None
    mock_emit.assert_called_once()
    assert mock_emit.call_args[0][0] == "IMPLICIT_FEEDBACK"


def test_implicit_feedback_empty_message():
    result = feedback_main({"message": ""})
    assert result is None
