"""Tests for rule-to-hook graduation."""
from pathlib import Path

import pytest

from gradata.brain import Brain
from gradata.enhancements.rule_to_hook import (
    DeterminismCheck,
    EnforcementType,
    classify_rule,
    find_hook_candidates,
)


def test_correction_event_captures_draft_text(tmp_path: Path) -> None:
    """CORRECTION events must carry the raw violating assistant draft under
    ``data['draft_text']`` so later tasks can use it as ground truth when
    self-testing generated hooks."""
    brain = Brain.init(
        tmp_path / "brain",
        name="RuleToHookTest",
        domain="Testing",
        embedding="local",
        interactive=False,
    )

    brain.record_correction(
        text="no don't use em dashes",
        assistant_draft="Subject: Let me — help you out",
        category="FORMATTING",
    )

    events = brain.query_events(event_type="CORRECTION", last_n_sessions=1)
    assert len(events) == 1
    assert events[0]["data"]["draft_text"] == "Subject: Let me — help you out"
    assert events[0]["data"]["category"] == "FORMATTING"


class TestClassifyRule:
    def test_em_dash_rule_is_deterministic(self):
        result = classify_rule("Never use em dashes in prose", 0.95)
        assert result.determinism == DeterminismCheck.REGEX_PATTERN
        assert result.enforcement == EnforcementType.HOOK

    def test_file_size_rule_is_deterministic(self):
        result = classify_rule("Keep files under 500 lines", 0.92)
        assert result.determinism == DeterminismCheck.FILE_CHECK

    def test_secret_rule_is_deterministic(self):
        result = classify_rule("Never commit secrets or API keys", 0.98)
        assert result.determinism == DeterminismCheck.COMMAND_BLOCK

    def test_test_rule_is_deterministic(self):
        result = classify_rule("Run tests after code changes", 0.91)
        assert result.determinism == DeterminismCheck.TEST_TRIGGER

    def test_read_before_edit_is_deterministic(self):
        result = classify_rule("Always read a file before editing it", 0.93)
        assert result.determinism == DeterminismCheck.FILE_CHECK

    def test_destructive_command_is_deterministic(self):
        result = classify_rule("Never force push to main", 0.96)
        assert result.determinism == DeterminismCheck.COMMAND_BLOCK

    def test_tone_rule_is_not_deterministic(self):
        result = classify_rule("Be concise and direct", 0.91)
        assert result.determinism == DeterminismCheck.NOT_DETERMINISTIC
        assert result.enforcement == EnforcementType.PROMPT_INJECTION

    def test_judgment_rule_is_not_deterministic(self):
        result = classify_rule("Lead with the answer, not the reasoning", 0.90)
        assert result.determinism == DeterminismCheck.NOT_DETERMINISTIC

    def test_audience_rule_is_not_deterministic(self):
        result = classify_rule("Match formality to the audience", 0.92)
        assert result.determinism == DeterminismCheck.NOT_DETERMINISTIC


class TestFindHookCandidates:
    def test_filters_by_confidence(self):
        lessons = [
            {"status": "RULE", "confidence": 0.95, "description": "Never use em dashes"},
            {"status": "PATTERN", "confidence": 0.80, "description": "Never use em dashes"},
        ]
        candidates = find_hook_candidates(lessons, min_confidence=0.90)
        assert len(candidates) == 1

    def test_filters_by_status(self):
        lessons = [
            {"status": "RULE", "confidence": 0.95, "description": "Never use em dashes"},
            {"status": "INSTINCT", "confidence": 0.95, "description": "Never use em dashes"},
        ]
        candidates = find_hook_candidates(lessons)
        assert len(candidates) == 1

    def test_returns_only_deterministic(self):
        lessons = [
            {"status": "RULE", "confidence": 0.95, "description": "Never use em dashes"},
            {"status": "RULE", "confidence": 0.95, "description": "Be concise and direct"},
        ]
        candidates = find_hook_candidates(lessons)
        assert len(candidates) == 1
        assert candidates[0].determinism == DeterminismCheck.REGEX_PATTERN

    def test_empty_lessons(self):
        assert find_hook_candidates([]) == []

    def test_meta_rule_included(self):
        lessons = [
            {"status": "META_RULE", "confidence": 0.98, "description": "Run tests after code changes"},
        ]
        candidates = find_hook_candidates(lessons)
        assert len(candidates) == 1


import subprocess
import json as _json


class TestRenderHook:
    def test_render_substitutes_placeholders(self):
        from gradata.enhancements.rule_to_hook import classify_rule, render_hook
        candidate = classify_rule("Never use em dashes", 0.95)
        rendered = render_hook(candidate)
        assert rendered is not None
        assert "{{RULE_TEXT}}" not in rendered
        assert "{{SOURCE_HASH}}" not in rendered
        assert "{{PATTERN_LITERAL}}" not in rendered
        assert "Never use em dashes" in rendered
        assert "GRADATA_BYPASS" in rendered

    def test_render_returns_none_for_nondeterministic(self):
        from gradata.enhancements.rule_to_hook import classify_rule, render_hook
        candidate = classify_rule("Be concise and direct", 0.91)
        rendered = render_hook(candidate)
        assert rendered is None

    def test_render_returns_none_for_unimplemented_template(self):
        # file_size_check template doesn't exist yet (v1 = regex_replace only)
        from gradata.enhancements.rule_to_hook import classify_rule, render_hook
        candidate = classify_rule("Keep files under 500 lines", 0.92)
        rendered = render_hook(candidate)
        assert rendered is None  # gracefully skip unimplemented templates


class TestSelfTest:
    def test_self_test_passes_when_hook_blocks_positive(self):
        from gradata.enhancements.rule_to_hook import classify_rule, render_hook, self_test
        candidate = classify_rule("Never use em dashes", 0.95)
        rendered = render_hook(candidate)
        ok = self_test(rendered, positive="hello \u2014 world", tool_name="Write")
        assert ok is True

    def test_self_test_fails_when_hook_does_not_block(self):
        from gradata.enhancements.rule_to_hook import classify_rule, render_hook, self_test
        candidate = classify_rule("Never use em dashes", 0.95)
        rendered = render_hook(candidate)
        # Plain ASCII content shouldn't match em-dash pattern
        ok = self_test(rendered, positive="hello - world (plain hyphen)", tool_name="Write")
        assert ok is False


class TestInstallHook:
    def test_install_writes_file_and_sets_executable(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import install_hook
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        path = install_hook("em-dash", "console.log('hello');\n")
        assert path.exists()
        assert path.parent == tmp_path
        assert path.suffix == ".js"
        assert "hello" in path.read_text(encoding="utf-8")


class TestTryGenerate:
    def test_try_generate_installs_for_em_dash(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import try_generate, classify_rule
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate, positive_example="this \u2014 fails")
        assert result.installed is True
        assert result.hook_path is not None
        assert result.hook_path.exists()
        assert "never-use-em-dashes" in result.hook_path.name.lower() or "em-dash" in result.hook_path.name.lower()

    def test_try_generate_skips_nondeterministic(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import try_generate, classify_rule
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Be concise and direct", 0.91)
        result = try_generate(candidate)
        assert result.installed is False
        assert "not deterministic" in result.reason.lower() or "not a hook" in result.reason.lower() or "advisory" in result.reason.lower()

    def test_try_generate_skips_unimplemented_template(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import try_generate, classify_rule
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Keep files under 500 lines", 0.92)
        result = try_generate(candidate)
        assert result.installed is False

    def test_try_generate_fails_self_test_if_positive_does_not_match(self, tmp_path, monkeypatch):
        # If caller passes a positive_example that the generated regex doesn't match,
        # self-test will fail and hook should NOT be installed.
        from gradata.enhancements.rule_to_hook import try_generate, classify_rule
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate, positive_example="plain ascii no dashes here")
        assert result.installed is False
        assert "self-test" in result.reason.lower() or "did not block" in result.reason.lower()


import subprocess
import sys


class TestCliRuleAdd:
    def test_rule_add_installs_hook_for_em_dash(self, tmp_path, monkeypatch):
        # Set up an isolated brain + hook root
        brain_dir = tmp_path / "brain"
        hook_root = tmp_path / "generated"
        hook_root.mkdir(parents=True)
        monkeypatch.setenv("GRADATA_BRAIN", str(brain_dir))
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_root))

        # Run the CLI
        import os
        env = os.environ.copy()
        src_dir = str(Path(__file__).resolve().parent.parent / "src")
        env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["GRADATA_BRAIN"] = str(brain_dir)
        env["GRADATA_HOOK_ROOT"] = str(hook_root)
        result = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "add", "never use em dashes"],
            capture_output=True, text=True,
            cwd=str(tmp_path),
            env=env,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        # Should report installation
        assert "installed" in result.stdout.lower() or "graduated" in result.stdout.lower()
        # Hook file should exist
        js_files = list(hook_root.glob("*.js"))
        assert len(js_files) == 1, f"found: {[f.name for f in hook_root.iterdir()]}"
        # Lessons file should contain the [hooked] marker
        lessons = brain_dir / "lessons.md"
        assert lessons.exists()
        content = lessons.read_text(encoding="utf-8")
        assert "[hooked]" in content
        assert "never use em dashes" in content

    def test_rule_add_falls_back_to_soft_for_advisory(self, tmp_path, monkeypatch):
        brain_dir = tmp_path / "brain"
        hook_root = tmp_path / "generated"
        hook_root.mkdir(parents=True)
        monkeypatch.setenv("GRADATA_BRAIN", str(brain_dir))
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_root))

        import os
        env = os.environ.copy()
        src_dir = str(Path(__file__).resolve().parent.parent / "src")
        env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["GRADATA_BRAIN"] = str(brain_dir)
        env["GRADATA_HOOK_ROOT"] = str(hook_root)
        result = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "add", "lead with the answer"],
            capture_output=True, text=True,
            cwd=str(tmp_path),
            env=env,
        )
        assert result.returncode == 0
        # No hook installed (advisory / non-deterministic)
        js_files = list(hook_root.glob("*.js"))
        assert len(js_files) == 0
        # Lessons file has the rule but WITHOUT [hooked] marker
        lessons = brain_dir / "lessons.md"
        assert lessons.exists()
        content = lessons.read_text(encoding="utf-8")
        assert "lead with the answer" in content
        assert "[hooked]" not in content


class TestGraduateIntegration:
    """Task 7: graduate() should auto-attempt hook install on PATTERN->RULE promotion."""

    def test_graduate_promotes_and_installs_hook_for_em_dash(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        from gradata.enhancements.self_improvement import graduate
        from gradata._types import Lesson, LessonState

        # Build a lesson at PATTERN tier with high confidence + enough fires
        # to promote to RULE. The description matches rule_to_hook's em-dash
        # deterministic pattern, so a hook should render, self-test, and install.
        lesson = Lesson(
            date="2026-04-12",
            state=LessonState.PATTERN,
            confidence=0.95,
            category="FORMATTING",
            description="Never use em dashes",
            fire_count=10,  # past MIN_APPLICATIONS_FOR_RULE=5 threshold
        )
        active, graduated = graduate([lesson], maturity="MATURE")

        # Assertion 1: lesson reached RULE state
        ended_at_rule = any(
            getattr(l, "state", None) == LessonState.RULE for l in (active + graduated)
        )
        assert ended_at_rule, f"lesson didn't reach RULE: state={lesson.state}"

        # Assertion 2: a hook file got installed under GRADATA_HOOK_ROOT
        js_files = list(tmp_path.glob("*.js"))
        assert len(js_files) == 1, (
            f"expected 1 hook file, found: {[f.name for f in tmp_path.iterdir()]}"
        )

        # Assertion 3: lesson description now carries [hooked] marker so
        # rule_enforcement dedup skips it.
        assert lesson.description.lstrip().startswith("[hooked]"), (
            f"lesson should be marked hooked, got: {lesson.description!r}"
        )

    def test_graduate_non_deterministic_rule_not_hooked(self, tmp_path, monkeypatch):
        """A graduated rule whose description is non-deterministic should
        reach RULE but NOT install a hook and NOT get the [hooked] marker."""
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        from gradata.enhancements.self_improvement import graduate
        from gradata._types import Lesson, LessonState

        lesson = Lesson(
            date="2026-04-12",
            state=LessonState.PATTERN,
            confidence=0.95,
            category="VOICE",
            description="Be concise and direct",
            fire_count=10,
        )
        graduate([lesson], maturity="MATURE")

        # No hook file should exist
        js_files = list(tmp_path.glob("*.js"))
        assert len(js_files) == 0, (
            f"advisory rule should not install a hook, got: {[f.name for f in js_files]}"
        )
        # Description should NOT be marked [hooked]
        assert not lesson.description.lstrip().startswith("[hooked]")


class TestBypassEnv:
    def test_bypass_env_disables_generated_hook(self, tmp_path, monkeypatch):
        """Generated hooks must honor GRADATA_BYPASS=1 as a runtime escape hatch."""
        import json as _j
        import os as _os
        import subprocess as _sp
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate

        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate)
        assert result.installed and result.hook_path is not None

        # Invoke the installed hook with GRADATA_BYPASS=1 and violating input
        env = {**_os.environ, "GRADATA_BYPASS": "1"}
        proc = _sp.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"content": "this \u2014 should pass"}}),
            capture_output=True, text=True, env=env, timeout=5,
        )
        assert proc.returncode == 0, (
            f"bypass failed: rc={proc.returncode} stdout={proc.stdout!r}"
        )


class TestFstringBlockTemplate:
    def test_fstring_rule_graduates_to_bash_hook(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule(
            "Never use python -c to format an f-string", 0.95
        )
        assert candidate.hook_template == "fstring_block"
        result = try_generate(candidate)
        assert result.installed is True, result.reason

    def test_fstring_hook_blocks_violating_bash_command(self, tmp_path, monkeypatch):
        import subprocess, json as _j
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never use python -c to format an f-string", 0.95)
        result = try_generate(candidate)
        assert result.installed

        # Violating bash command
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Bash",
                            "tool_input": {"command": "python -c \"f'{x}'\""}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 2

        # Clean command — no f-string
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Bash",
                            "tool_input": {"command": "python -c \"print(1)\""}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 0


class TestRootFileSaveTemplate:
    def test_root_file_rule_graduates(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never save files to the root folder", 0.95)
        assert candidate.hook_template == "root_file_save"
        result = try_generate(candidate)
        assert result.installed is True, result.reason

    def test_root_file_hook_blocks_root_path_but_allows_nested(self, tmp_path, monkeypatch):
        import subprocess, json as _j
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never save files to the root folder", 0.95)
        result = try_generate(candidate)
        assert result.installed

        # Root-level write → blocked
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"file_path": "foo.py"}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 2

        # Nested write → allowed
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"file_path": "sdk/foo.py"}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 0
