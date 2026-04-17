"""Tests for rule_enforcement scope-prefilter (LLM-agnostic)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata.hooks import rule_enforcement


@pytest.fixture(autouse=True)
def _enable_rule_enforcement(monkeypatch):
    """Rule enforcement hook is default-off; opt scope tests in."""
    monkeypatch.setenv("GRADATA_RULE_ENFORCEMENT", "1")


def _write_lesson(lessons_path: Path, *, category: str, desc: str, scope: dict | None) -> None:
    """Append one RULE-tier lesson to a lessons.md file."""
    line = f"[2026-04-09] [RULE:0.92] {category}: {desc}\n"
    line += "  Fire count: 1 | Sessions since fire: 0 | Misfires: 0\n"
    if scope is not None:
        line += f"  Scope: {json.dumps(scope)}\n"
    line += "\n"
    with lessons_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _setup_brain(tmp_path: Path, lessons: list[tuple[str, str, dict | None]]) -> Path:
    brain = tmp_path / "brain"
    brain.mkdir()
    lessons_path = brain / "lessons.md"
    lessons_path.touch()
    for cat, desc, scope in lessons:
        _write_lesson(lessons_path, category=cat, desc=desc, scope=scope)
    return brain


def test_file_domain_classifier():
    assert rule_enforcement._file_domain("foo.py") == "code"
    assert rule_enforcement._file_domain("README.md") == "prose"
    assert rule_enforcement._file_domain("data.json") == "data"
    assert rule_enforcement._file_domain("unknown.xyz") == ""
    assert rule_enforcement._file_domain("") == ""


def test_no_scope_always_applies(tmp_path):
    brain = _setup_brain(tmp_path, [("LEADS", "no scope rule", None)])
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "foo.py"}})
    assert out is not None
    assert "no scope rule" in out["result"]


def test_explicit_domain_mismatch_skips(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [("DRAFTING", "prose-only rule", {"domain": "prose"})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "foo.py"}})
    # Only rule was prose-scoped; editing .py drops it -> empty -> None
    assert out is None


def test_explicit_domain_match_includes(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [("BUG", "code-only rule", {"domain": "code"})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "src/foo.py"}})
    assert out is not None
    assert "code-only rule" in out["result"]


def test_unknown_file_domain_does_not_filter(tmp_path):
    """When file_domain is unknown, declared-domain rules still pass (safe default)."""
    brain = _setup_brain(
        tmp_path,
        [("BUG", "scoped rule", {"domain": "code"})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "Dockerfile"}})
    assert out is not None
    assert "scoped rule" in out["result"]


def test_file_glob_match(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [("API", "ts only", {"file_glob": "*.ts"})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "src/foo.ts"}})
    assert out is not None
    assert "ts only" in out["result"]


def test_file_glob_no_match(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [("API", "ts only", {"file_glob": "*.ts"})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "src/foo.py"}})
    assert out is None


def test_file_glob_list_any_match(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [("API", "ts/tsx", {"file_glob": ["*.ts", "*.tsx"]})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "src/foo.tsx"}})
    assert out is not None


def test_applies_to_prefix_mismatch_skips(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [("LEADS", "comms only", {"applies_to": "prose:"})],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "src/foo.py"}})
    assert out is None


def test_malformed_scope_json_falls_back_to_apply(tmp_path):
    """Unparseable scope must NOT silently drop the rule."""
    brain = tmp_path / "brain"
    brain.mkdir()
    lp = brain / "lessons.md"
    lp.write_text(
        "[2026-04-09] [RULE:0.92] LEADS: rule with bad scope\n"
        "  Fire count: 1 | Sessions since fire: 0 | Misfires: 0\n"
        "  Scope: {not valid json\n\n",
        encoding="utf-8",
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "foo.py"}})
    assert out is not None
    assert "rule with bad scope" in out["result"]


def test_no_file_path_includes_unscoped_only(tmp_path):
    """Without a file_path, glob/domain filters can't compute -> include unscoped, may filter scoped."""
    brain = _setup_brain(
        tmp_path,
        [
            ("LEADS", "unscoped", None),
            ("BUG", "code-scoped", {"domain": "code"}),
        ],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {}})
    assert out is not None
    # Unscoped always passes; code-scoped passes too because file_domain is "" (safe default).
    assert "unscoped" in out["result"]


def test_mixed_rules_only_applicable_returned(tmp_path):
    brain = _setup_brain(
        tmp_path,
        [
            ("LEADS", "prose only", {"domain": "prose"}),
            ("BUG", "code only", {"domain": "code"}),
            ("META", "everywhere", None),
        ],
    )
    with patch.object(rule_enforcement, "resolve_brain_dir", return_value=str(brain)):
        out = rule_enforcement.main({"tool_input": {"file_path": "src/foo.py"}})
    assert out is not None
    assert "code only" in out["result"]
    assert "everywhere" in out["result"]
    assert "prose only" not in out["result"]
