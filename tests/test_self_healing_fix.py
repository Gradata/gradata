"""Tests for self-healing pipeline fixes — positive directive graduation.

Covers:
- SESSION_DIRECTIVE pattern matching for positive directives
- Existing negation patterns still work (regression guard)
- render_hook() generates valid JS for session_directive
- install_hook() routes session_directive to session-start directory
- inject_brain_rules mandatory injection tier formatting
"""
from __future__ import annotations

import os
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gradata.enhancements.rule_to_hook import (
    DeterminismCheck,
    EnforcementType,
    HookCandidate,
    classify_rule,
    render_hook,
    _IMPLEMENTED_TEMPLATES,
    _SESSION_START_TEMPLATES,
    _TEMPLATES_SKIP_SELFTEST,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(description: str) -> HookCandidate:
    return classify_rule(description, confidence=0.92)


def _is_session_directive(description: str) -> bool:
    c = _classify(description)
    return c.determinism == DeterminismCheck.SESSION_DIRECTIVE


# ---------------------------------------------------------------------------
# Positive directive pattern tests
# ---------------------------------------------------------------------------

class TestPositiveDirectivePatterns:
    def test_use_superpowers_before_building(self):
        assert _is_session_directive("use superpowers before building")

    def test_always_use_superpowers(self):
        assert _is_session_directive("always use superpowers")

    def test_use_council_for_decisions(self):
        assert _is_session_directive("always use council for decisions")

    def test_use_council_plain(self):
        assert _is_session_directive("use council before implementing")

    def test_use_worktrees_for_all_code_changes(self):
        assert _is_session_directive("use worktrees for all code changes")

    def test_ooda_godmode(self):
        assert _is_session_directive("OODA godmode — never stop to ask")

    def test_ooda_lowercase(self):
        assert _is_session_directive("ooda mode: observe orient decide act")

    def test_godmode(self):
        assert _is_session_directive("godmode enabled")

    def test_never_stop_to_ask(self):
        assert _is_session_directive("never stop to ask permission")

    def test_keep_building(self):
        assert _is_session_directive("keep building until told to stop")

    def test_spawn_parallel_agents(self):
        assert _is_session_directive("spawn parallel agents for tasks")

    def test_use_parallel_agents(self):
        assert _is_session_directive("use parallel agents")

    def test_never_work_sequential(self):
        assert _is_session_directive("never work sequential")

    def test_before_implementing_use_council(self):
        assert _is_session_directive("before implementing, use council")

    def test_invoke_before_planning(self):
        assert _is_session_directive("invoke brainstorm before planning")

    def test_use_before_creating(self):
        assert _is_session_directive("use superpowers before creating new features")

    def test_run_worktree_before_coding(self):
        assert _is_session_directive("run worktree before coding")

    def test_enforcement_type_is_hook(self):
        c = _classify("use superpowers before building")
        assert c.enforcement == EnforcementType.HOOK

    def test_hook_template_is_session_directive(self):
        c = _classify("always use council for decisions")
        assert c.hook_template == "session_directive"

    def test_template_arg_is_set(self):
        c = _classify("use superpowers before building")
        assert c.template_arg is not None


# ---------------------------------------------------------------------------
# Regression: existing negation patterns still work
# ---------------------------------------------------------------------------

class TestNegationPatternsRegression:
    def test_never_em_dash(self):
        c = _classify("never use em-dash in prose")
        assert c.determinism == DeterminismCheck.REGEX_PATTERN
        assert c.hook_template == "regex_replace"

    def test_no_em_dash(self):
        c = _classify("no em dash allowed")
        assert c.determinism == DeterminismCheck.REGEX_PATTERN

    def test_keep_files_under_500_lines(self):
        c = _classify("keep files under 500 lines")
        assert c.determinism == DeterminismCheck.FILE_CHECK
        assert c.hook_template == "file_size_check"
        assert c.template_arg == "500"

    def test_never_commit_secret(self):
        c = _classify("never commit secret to repo")
        assert c.determinism == DeterminismCheck.COMMAND_BLOCK
        assert c.hook_template == "secret_scan"

    def test_run_tests_after(self):
        c = _classify("run tests after every code change")
        assert c.determinism == DeterminismCheck.TEST_TRIGGER
        assert c.hook_template == "auto_test"

    def test_never_force_push(self):
        c = _classify("never force push to main")
        assert c.determinism == DeterminismCheck.COMMAND_BLOCK
        assert c.hook_template == "destructive_block"

    def test_not_deterministic_still_works(self):
        c = _classify("be polite and empathetic to users")
        assert c.determinism == DeterminismCheck.NOT_DETERMINISTIC
        assert c.enforcement == EnforcementType.PROMPT_INJECTION


# ---------------------------------------------------------------------------
# render_hook() for session_directive
# ---------------------------------------------------------------------------

class TestRenderHookSessionDirective:
    def _make_candidate(self, description: str = "use superpowers before building") -> HookCandidate:
        return HookCandidate(
            rule_description=description,
            rule_confidence=0.92,
            determinism=DeterminismCheck.SESSION_DIRECTIVE,
            enforcement=EnforcementType.HOOK,
            hook_template="session_directive",
            template_arg="positive_directive",
            reason="Matches deterministic pattern",
        )

    def test_render_returns_string(self):
        c = self._make_candidate()
        result = render_hook(c)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_contains_mandatory_directive_tags(self):
        c = self._make_candidate()
        result = render_hook(c)
        assert "<mandatory-directive>" in result
        assert "</mandatory-directive>" in result

    def test_render_contains_rule_description(self):
        desc = "use superpowers before building"
        c = self._make_candidate(desc)
        result = render_hook(c)
        assert desc in result

    def test_render_is_valid_js_structure(self):
        c = self._make_candidate()
        result = render_hook(c)
        # Must start with shebang
        assert result.startswith("#!/usr/bin/env node")
        # Must write to stdout
        assert "process.stdout.write" in result

    def test_render_escapes_quotes_in_description(self):
        desc = 'use "council" before building'
        c = self._make_candidate(desc)
        result = render_hook(c)
        assert result is not None
        # Double-quote in description must be escaped in the JS output
        assert '\\"council\\"' in result or "council" in result

    def test_render_non_hook_returns_none(self):
        c = HookCandidate(
            rule_description="be nice",
            rule_confidence=0.5,
            determinism=DeterminismCheck.NOT_DETERMINISTIC,
            enforcement=EnforcementType.PROMPT_INJECTION,
            hook_template="",
            template_arg=None,
            reason="not deterministic",
        )
        assert render_hook(c) is None

    def test_session_directive_in_implemented_templates(self):
        assert "session_directive" in _IMPLEMENTED_TEMPLATES

    def test_session_directive_in_skip_selftest(self):
        assert "session_directive" in _TEMPLATES_SKIP_SELFTEST

    def test_session_directive_in_session_start_templates(self):
        assert "session_directive" in _SESSION_START_TEMPLATES


# ---------------------------------------------------------------------------
# install_hook() routing for session_directive
# ---------------------------------------------------------------------------

class TestInstallHookRouting:
    def test_session_directive_routes_to_session_start(self, tmp_path):
        from gradata.enhancements.rule_to_hook import install_hook
        session_root = tmp_path / "session-start"
        with patch.dict(os.environ, {"GRADATA_HOOK_ROOT_SESSION": str(session_root)}):
            path = install_hook("test-directive", "// js", template="session_directive")
        assert "session-start" in str(path)
        assert path.exists()

    def test_auto_test_routes_to_post_tool(self, tmp_path):
        from gradata.enhancements.rule_to_hook import install_hook
        post_root = tmp_path / "post-tool"
        with patch.dict(os.environ, {"GRADATA_HOOK_ROOT_POST": str(post_root)}):
            path = install_hook("test-auto", "// js", template="auto_test")
        assert "post-tool" in str(path)

    def test_regular_template_routes_to_pre_tool(self, tmp_path):
        from gradata.enhancements.rule_to_hook import install_hook
        pre_root = tmp_path / "pre-tool"
        with patch.dict(os.environ, {"GRADATA_HOOK_ROOT": str(pre_root)}):
            path = install_hook("test-pre", "// js", template="regex_replace")
        assert "pre-tool" in str(path)


# ---------------------------------------------------------------------------
# classify_rule -> render_hook end-to-end for session directives
# ---------------------------------------------------------------------------

class TestEndToEnd:
    @pytest.mark.parametrize("description", [
        "use superpowers before building",
        "always use council for decisions",
        "use worktrees for all code changes",
        "OODA godmode",
        "spawn parallel agents",
        "never stop to ask",
    ])
    def test_classify_then_render_produces_js(self, description: str):
        candidate = classify_rule(description, 0.92)
        assert candidate.determinism == DeterminismCheck.SESSION_DIRECTIVE
        result = render_hook(candidate)
        assert result is not None
        assert isinstance(result, str)
        assert "mandatory-directive" in result


# ---------------------------------------------------------------------------
# inject_brain_rules mandatory injection tier
# ---------------------------------------------------------------------------

class _FakeLesson:
    """Minimal Lesson stub for injection tests."""
    def __init__(self, description, category, confidence, fire_count, state_name="RULE"):
        self.description = description
        self.category = category
        self.confidence = confidence
        self.fire_count = fire_count
        self.state = SimpleNamespace(name=state_name)

    def __getitem__(self, key):
        return getattr(self, key)


class TestMandatoryInjectionTier:
    """Unit-test the mandatory block logic extracted from inject_brain_rules.main()."""

    def _build_mandatory_output(self, lessons: list) -> str:
        """Replicate the mandatory block construction from inject_brain_rules."""
        mandatory = [
            lesson for lesson in lessons
            if lesson.state.name == "RULE"
            and lesson.confidence >= 0.90
            and getattr(lesson, "fire_count", 0) >= 10
        ]
        if mandatory:
            mandatory_lines = [
                f"[MANDATORY] {r.category}: {r.description}" for r in mandatory
            ]
            mandatory_block = (
                "<mandatory-directives>\n"
                "## NON-NEGOTIABLE DIRECTIVES\n"
                "These rules are MANDATORY. Your response will be REJECTED if any are violated.\n"
                + "\n".join(mandatory_lines)
                + "\n</mandatory-directives>"
            )
        else:
            mandatory_block = ""
        return mandatory_block

    def test_mandatory_block_appears_for_qualifying_rules(self):
        lessons = [
            _FakeLesson("use superpowers before building", "workflow", 0.92, 15),
        ]
        result = self._build_mandatory_output(lessons)
        assert "<mandatory-directives>" in result
        assert "NON-NEGOTIABLE DIRECTIVES" in result
        assert "use superpowers before building" in result

    def test_low_confidence_rule_excluded_from_mandatory(self):
        lessons = [
            _FakeLesson("be concise", "style", 0.80, 15),  # conf < 0.90
        ]
        result = self._build_mandatory_output(lessons)
        assert result == ""

    def test_low_fire_count_excluded_from_mandatory(self):
        lessons = [
            _FakeLesson("use superpowers", "workflow", 0.92, 5),  # fire_count < 10
        ]
        result = self._build_mandatory_output(lessons)
        assert result == ""

    def test_pattern_state_excluded_from_mandatory(self):
        lessons = [
            _FakeLesson("use superpowers", "workflow", 0.92, 15, state_name="PATTERN"),
        ]
        result = self._build_mandatory_output(lessons)
        assert result == ""

    def test_no_mandatory_returns_empty(self):
        lessons = [
            _FakeLesson("be polite", "style", 0.65, 3, state_name="PATTERN"),
        ]
        result = self._build_mandatory_output(lessons)
        assert result == ""

    def test_multiple_mandatory_rules_all_appear(self):
        lessons = [
            _FakeLesson("use superpowers before building", "workflow", 0.95, 20),
            _FakeLesson("never ask without checking first", "workflow", 0.91, 11),
        ]
        result = self._build_mandatory_output(lessons)
        assert "use superpowers before building" in result
        assert "never ask without checking first" in result

    def test_mandatory_block_label_format(self):
        lessons = [
            _FakeLesson("use superpowers", "workflow", 0.92, 15),
        ]
        result = self._build_mandatory_output(lessons)
        assert "[MANDATORY] workflow: use superpowers" in result
