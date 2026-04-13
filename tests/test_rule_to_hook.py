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
        # read_before_edit template remains unimplemented (stateful)
        from gradata.enhancements.rule_to_hook import classify_rule, render_hook
        candidate = classify_rule("Always read files before editing", 0.92)
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
        path = install_hook("em-dash", "console.log('hello');\n", template="regex_replace")
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
        # read_before_edit remains unimplemented (stateful)
        candidate = classify_rule("Always read files before editing", 0.92)
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


class TestGeneratedRunner:
    @staticmethod
    def _runner_env(gen_dir):
        import os
        env = os.environ.copy()
        src_dir = str(Path(__file__).resolve().parent.parent / "src")
        env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["GRADATA_HOOK_ROOT"] = str(gen_dir)
        return env

    def test_runner_invokes_matching_generated_hook(self, tmp_path, monkeypatch):
        """The generated_runner scans GRADATA_HOOK_ROOT and runs each .js hook,
        relaying block decisions back to Claude Code."""
        import json as _j
        import subprocess as _sp
        import sys as _sys
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate

        gen_dir = tmp_path / "generated"
        gen_dir.mkdir(parents=True)
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(gen_dir))

        # Install an em-dash hook
        candidate = classify_rule("Never use em dashes", 0.95)
        assert try_generate(candidate).installed

        # Run the runner with violating payload — should block
        payload = {"tool_name": "Write",
                   "tool_input": {"content": "this \u2014 violates"}}
        proc = _sp.run(
            [_sys.executable, "-m", "gradata.hooks.generated_runner"],
            input=_j.dumps(payload),
            capture_output=True, text=True, env=self._runner_env(gen_dir),
            timeout=10,
        )
        assert proc.returncode == 2, f"expected block (2), got {proc.returncode}; stdout={proc.stdout!r}; stderr={proc.stderr!r}"

    def test_runner_passes_clean_input(self, tmp_path, monkeypatch):
        import json as _j, subprocess as _sp, sys as _sys
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate

        gen_dir = tmp_path / "generated"
        gen_dir.mkdir(parents=True)
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(gen_dir))
        try_generate(classify_rule("Never use em dashes", 0.95))

        payload = {"tool_name": "Write", "tool_input": {"content": "plain ascii"}}
        proc = _sp.run(
            [_sys.executable, "-m", "gradata.hooks.generated_runner"],
            input=_j.dumps(payload),
            capture_output=True, text=True,
            env=self._runner_env(gen_dir),
            timeout=10,
        )
        assert proc.returncode == 0, f"stderr={proc.stderr!r}"

    def test_runner_exits_zero_when_no_hooks_installed(self, tmp_path, monkeypatch):
        """No hooks → exit 0 silently. Never break Claude Code."""
        import json as _j, subprocess as _sp, sys as _sys
        gen_dir = tmp_path / "generated"
        gen_dir.mkdir(parents=True)

        payload = {"tool_name": "Write", "tool_input": {"content": "anything"}}
        proc = _sp.run(
            [_sys.executable, "-m", "gradata.hooks.generated_runner"],
            input=_j.dumps(payload),
            capture_output=True, text=True,
            env=self._runner_env(gen_dir),
            timeout=10,
        )
        assert proc.returncode == 0, f"stderr={proc.stderr!r}"


class TestInstallerRegistry:
    def test_generated_runner_in_hook_registry(self):
        """The installer must register the generated runner so fresh
        `gradata hooks install` picks it up automatically."""
        from gradata.hooks._installer import HOOK_REGISTRY
        modules = [entry[0] for entry in HOOK_REGISTRY]
        assert "generated_runner" in modules


class TestDestructiveBlockTemplate:
    def test_rm_rf_rule_graduates(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never rm -rf anything", 0.95)
        assert candidate.hook_template == "destructive_block"
        assert try_generate(candidate).installed

    def test_force_push_rule_graduates(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never force push", 0.95)
        assert candidate.hook_template == "destructive_block"
        assert try_generate(candidate).installed

    def test_destructive_hook_blocks_rm_rf(self, tmp_path, monkeypatch):
        import subprocess, json as _j
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never rm -rf anything", 0.95)
        result = try_generate(candidate)
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Bash",
                            "tool_input": {"command": "rm -rf /tmp/foo"}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 2
        # Safe command passes
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Bash",
                            "tool_input": {"command": "ls -la"}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 0


class TestSecretScanTemplate:
    def test_secret_rule_graduates(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never commit secrets", 0.95)
        assert candidate.hook_template == "secret_scan"
        assert try_generate(candidate).installed

    def test_secret_hook_blocks_openai_key(self, tmp_path, monkeypatch):
        import subprocess, json as _j
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never commit secrets", 0.95)
        result = try_generate(candidate)
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"content": "OPENAI_KEY = 'sk-abc123def456ghi789jklmno'"}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 2
        # Clean content passes
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"content": "OPENAI_KEY = os.environ['OPENAI_API_KEY']"}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 0


class TestFileSizeCheckTemplate:
    def test_file_size_rule_graduates_with_limit(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Keep files under 500 lines", 0.95)
        assert candidate.hook_template == "file_size_check"
        assert candidate.template_arg == "500"
        assert try_generate(candidate).installed

    def test_file_size_hook_blocks_oversized_content(self, tmp_path, monkeypatch):
        import subprocess, json as _j
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Keep files under 100 lines", 0.95)
        result = try_generate(candidate)
        big = "line\n" * 150
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"content": big}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 2
        small = "line\n" * 50
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps({"tool_name": "Write",
                            "tool_input": {"content": small}}),
            capture_output=True, text=True, timeout=5,
        )
        assert proc.returncode == 0


class TestPhrasingCoverage:
    def test_em_dash_paraphrasing(self):
        from gradata.enhancements.rule_to_hook import classify_rule, EnforcementType
        c1 = classify_rule("Avoid em dashes in prose", 0.95)
        c2 = classify_rule("Em dashes are banned", 0.95)
        assert c1.enforcement == EnforcementType.HOOK
        assert c2.enforcement == EnforcementType.HOOK
        assert c1.hook_template == "regex_replace"
        assert c2.hook_template == "regex_replace"


class TestAutoTestTemplate:
    def test_auto_test_rule_classifies(self):
        from gradata.enhancements.rule_to_hook import classify_rule, EnforcementType
        candidate = classify_rule("Run tests after code changes", 0.95)
        assert candidate.enforcement == EnforcementType.HOOK
        assert candidate.hook_template == "auto_test"

    def test_auto_test_installs_to_post_tool_dir(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        post_dir = tmp_path / "post-tool-generated"
        post_dir.mkdir()
        monkeypatch.setenv("GRADATA_HOOK_ROOT_POST", str(post_dir))
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path / "pre-tool"))

        candidate = classify_rule("Always run tests after editing", 0.95)
        result = try_generate(candidate)
        assert result.installed is True, result.reason
        # Hook lands in POST dir, not PRE dir
        assert result.hook_path is not None
        assert str(post_dir) in str(result.hook_path)

    def test_auto_test_hook_runs_pytest_and_exits_zero_if_no_test_file(self, tmp_path, monkeypatch):
        """If no matching test file exists, hook silently exits 0 — don't noise up every edit."""
        import subprocess, json as _j
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        post_dir = tmp_path / "post-tool-generated"
        post_dir.mkdir()
        monkeypatch.setenv("GRADATA_HOOK_ROOT_POST", str(post_dir))
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path / "pre-tool"))

        candidate = classify_rule("Run tests after code changes", 0.95)
        result = try_generate(candidate)
        assert result.installed

        # Fake Write to a file with no matching test
        target = tmp_path / "orphan.py"
        target.write_text("def f(): pass\n", encoding="utf-8")
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(target)}}
        proc = subprocess.run(
            ["node", str(result.hook_path)],
            input=_j.dumps(payload),
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0


class TestGeneratedRunnerPost:
    def test_post_runner_registered_in_installer(self):
        from gradata.hooks._installer import HOOK_REGISTRY
        modules = [entry[0] for entry in HOOK_REGISTRY]
        assert "generated_runner_post" in modules

    def test_post_runner_iterates_post_tool_dir(self, tmp_path, monkeypatch):
        import json as _j, subprocess as _sp, sys as _sys, os as _os
        post_dir = tmp_path / "post-tool-generated"
        post_dir.mkdir()
        # Install a no-op hook file directly
        noop = post_dir / "noop.js"
        noop.write_text(
            "process.stdin.on('data', ()=>{}); "
            "process.stdin.on('end', ()=>process.exit(0));\n",
            encoding="utf-8", newline="\n",
        )

        env = {**_os.environ,
               "GRADATA_HOOK_ROOT_POST": str(post_dir),
               "PYTHONPATH": "src"}
        proc = _sp.run(
            [_sys.executable, "-m", "gradata.hooks.generated_runner_post"],
            input=_j.dumps({"tool_name": "Write", "tool_input": {"file_path": "x.py"}}),
            capture_output=True, text=True, env=env, timeout=10,
        )
        assert proc.returncode == 0


class TestRuleExport:
    def _write_lessons(self, brain_dir, lines):
        brain_dir.mkdir(parents=True, exist_ok=True)
        (brain_dir / "lessons.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def test_export_cursor_format(self, tmp_path):
        from gradata.enhancements.rule_export import export_rules
        brain = tmp_path / "brain"
        self._write_lessons(brain, [
            "[2026-04-12] [RULE:1.00] [hooked] FORMATTING: never use em dashes",
            "[2026-04-12] [RULE:0.95] STRUCTURE: lead with the answer",
            "[2026-04-12] [PATTERN:0.70] TONE: be friendly",  # should skip non-RULE
        ])
        output = export_rules(brain, target="cursor")
        assert "never use em dashes" in output
        assert "lead with the answer" in output
        assert "be friendly" not in output  # PATTERN-tier excluded
        # Cursor format: each rule on its own line or bullet
        assert output.count("never use em dashes") == 1

    def test_export_agents_format(self, tmp_path):
        from gradata.enhancements.rule_export import export_rules
        brain = tmp_path / "brain"
        self._write_lessons(brain, [
            "[2026-04-12] [RULE:1.00] FORMATTING: never use em dashes",
            "[2026-04-12] [RULE:0.95] STRUCTURE: lead with the answer",
        ])
        output = export_rules(brain, target="agents")
        # AGENTS.md has a heading and bullet rules
        assert "# " in output or "## " in output
        assert "- " in output
        assert "never use em dashes" in output

    def test_export_aider_format(self, tmp_path):
        from gradata.enhancements.rule_export import export_rules
        brain = tmp_path / "brain"
        self._write_lessons(brain, [
            "[2026-04-12] [RULE:1.00] FORMATTING: never use em dashes",
        ])
        output = export_rules(brain, target="aider")
        # Aider format: YAML-safe. Should validate as YAML.
        try:
            import yaml
            parsed = yaml.safe_load(output)
            assert parsed is not None
        except ImportError:
            assert "message:" in output
            assert "  - " in output

    def test_export_strips_hooked_marker(self, tmp_path):
        """The [hooked] marker is internal — exported rules shouldn't include it."""
        from gradata.enhancements.rule_export import export_rules
        brain = tmp_path / "brain"
        self._write_lessons(brain, [
            "[2026-04-12] [RULE:1.00] [hooked] FORMATTING: never use em dashes",
        ])
        output = export_rules(brain, target="cursor")
        assert "[hooked]" not in output
        assert "never use em dashes" in output

    def test_export_empty_brain(self, tmp_path):
        from gradata.enhancements.rule_export import export_rules
        brain = tmp_path / "brain"
        brain.mkdir()
        (brain / "lessons.md").write_text("", encoding="utf-8")
        output = export_rules(brain, target="cursor")
        # Empty is fine, don't crash
        assert isinstance(output, str)


class TestCliExport:
    def test_cli_export_writes_cursorrules(self, tmp_path, monkeypatch):
        import subprocess, sys, os
        brain = tmp_path / "brain"
        brain.mkdir()
        (brain / "lessons.md").write_text(
            "[2026-04-12] [RULE:1.00] FORMATTING: never use em dashes\n",
            encoding="utf-8",
        )
        out_dir = tmp_path / "project"
        out_dir.mkdir()

        # Resolve src/ to absolute path so cwd=tmp_path doesn't break imports
        repo_src = str((__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
        existing_pp = os.environ.get("PYTHONPATH", "")
        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "PYTHONPATH": (repo_src + os.pathsep + existing_pp) if existing_pp else repo_src}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "export",
             "--target", "cursor",
             "--output", str(out_dir / ".cursorrules")],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
        written = out_dir / ".cursorrules"
        assert written.exists()
        assert "never use em dashes" in written.read_text(encoding="utf-8")

    def test_cli_export_writes_stdout_when_no_output_flag(self, tmp_path):
        import subprocess, sys, os
        brain = tmp_path / "brain"
        brain.mkdir()
        (brain / "lessons.md").write_text(
            "[2026-04-12] [RULE:1.00] FORMATTING: never use em dashes\n",
            encoding="utf-8",
        )
        # Resolve src/ to absolute path so cwd=tmp_path doesn't break imports
        repo_src = str((__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
        existing_pp = os.environ.get("PYTHONPATH", "")
        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "PYTHONPATH": (repo_src + os.pathsep + existing_pp) if existing_pp else repo_src}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "export", "--target", "agents"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert proc.returncode == 0
        assert "never use em dashes" in proc.stdout


class TestCliRuleList:
    def _write_lessons(self, brain_dir, lines):
        brain_dir.mkdir(parents=True, exist_ok=True)
        (brain_dir / "lessons.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_rule_list_shows_hooked_markers(self, tmp_path):
        import subprocess, sys, os
        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        post = tmp_path / "post"
        pre.mkdir(parents=True)
        post.mkdir(parents=True)

        self._write_lessons(brain, [
            "[2026-04-13] [RULE:1.00] FORMATTING: [hooked] never use em dashes",
            "[2026-04-13] [RULE:0.95] STRUCTURE: lead with the answer",
        ])
        # Install matching .js for the em-dash rule
        (pre / "never-use-em-dashes.js").write_text("// stub\n", encoding="utf-8")

        repo_src = str((__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
        existing_pp = os.environ.get("PYTHONPATH", "")
        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "GRADATA_HOOK_ROOT": str(pre),
               "GRADATA_HOOK_ROOT_POST": str(post),
               "PYTHONPATH": (repo_src + os.pathsep + existing_pp) if existing_pp else repo_src}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "list"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        out = proc.stdout
        assert "never use em dashes" in out
        assert "lead with the answer" in out
        assert "[hooked]" in out
        assert "1 hooked" in out or "1 / 2" in out or "1 hooked / 2" in out

    def test_rule_list_flags_stale_and_orphan(self, tmp_path):
        """[hooked] in lessons but no .js file = STALE. .js file without [hooked] = ORPHAN."""
        import subprocess, sys, os
        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        post = tmp_path / "post"
        pre.mkdir(parents=True)
        post.mkdir(parents=True)

        self._write_lessons(brain, [
            "[2026-04-13] [RULE:1.00] FORMATTING: [hooked] this rule is stale",
        ])
        # Orphan hook file — no matching lessons.md entry
        (pre / "orphan-hook.js").write_text("// orphan\n", encoding="utf-8")

        repo_src = str((__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
        existing_pp = os.environ.get("PYTHONPATH", "")
        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "GRADATA_HOOK_ROOT": str(pre),
               "GRADATA_HOOK_ROOT_POST": str(post),
               "PYTHONPATH": (repo_src + os.pathsep + existing_pp) if existing_pp else repo_src}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "list"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        assert "STALE" in proc.stdout
        assert "orphan-hook" in proc.stdout.lower() or "ORPHAN" in proc.stdout

    def test_rule_list_empty_is_fine(self, tmp_path):
        import subprocess, sys, os
        brain = tmp_path / "brain"
        brain.mkdir()
        (brain / "lessons.md").write_text("", encoding="utf-8")
        repo_src = str((__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))
        existing_pp = os.environ.get("PYTHONPATH", "")
        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "PYTHONPATH": (repo_src + os.pathsep + existing_pp) if existing_pp else repo_src}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "list"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert proc.returncode == 0
        # Empty lessons → should still print header or "no rules"
        assert "rules" in proc.stdout.lower() or proc.stdout.strip() == ""


class TestCliRuleRemove:
    def _write_lessons(self, brain_dir, lines):
        brain_dir.mkdir(parents=True, exist_ok=True)
        (brain_dir / "lessons.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _env(self, tmp_path):
        import os
        from pathlib import Path as _P
        return {**os.environ,
                "GRADATA_BRAIN": str(tmp_path / "brain"),
                "GRADATA_HOOK_ROOT": str(tmp_path / "pre"),
                "GRADATA_HOOK_ROOT_POST": str(tmp_path / "post"),
                "PYTHONPATH": str(_P(__file__).resolve().parents[1] / "src")}

    def test_rule_remove_deletes_hook_and_unmarks_lesson(self, tmp_path):
        import subprocess, sys
        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        pre.mkdir(parents=True)
        (tmp_path / "post").mkdir()

        self._write_lessons(brain, [
            "[2026-04-13] [RULE:1.00] FORMATTING: [hooked] never use em dashes",
            "[2026-04-13] [RULE:0.95] STRUCTURE: lead with the answer",
        ])
        hook_file = pre / "never-use-em-dashes.js"
        hook_file.write_text("// stub\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "remove", "never-use-em-dashes"],
            capture_output=True, text=True, env=self._env(tmp_path), cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        assert not hook_file.exists(), "hook file should be deleted"
        # Lesson still exists but [hooked] marker removed
        lessons_text = (brain / "lessons.md").read_text(encoding="utf-8")
        assert "never use em dashes" in lessons_text
        assert "[hooked] never use em dashes" not in lessons_text
        # Other lesson untouched
        assert "lead with the answer" in lessons_text

    def test_rule_remove_purge_deletes_lesson(self, tmp_path):
        import subprocess, sys
        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        pre.mkdir(parents=True)
        (tmp_path / "post").mkdir()

        self._write_lessons(brain, [
            "[2026-04-13] [RULE:1.00] FORMATTING: [hooked] never use em dashes",
            "[2026-04-13] [RULE:0.95] STRUCTURE: lead with the answer",
        ])
        (pre / "never-use-em-dashes.js").write_text("// stub\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "remove", "never-use-em-dashes", "--purge"],
            capture_output=True, text=True, env=self._env(tmp_path), cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        lessons_text = (brain / "lessons.md").read_text(encoding="utf-8")
        assert "never use em dashes" not in lessons_text
        assert "lead with the answer" in lessons_text  # unchanged

    def test_rule_remove_idempotent(self, tmp_path):
        """Running remove on a non-existent slug is a no-op, exit 0."""
        import subprocess, sys
        brain = tmp_path / "brain"
        brain.mkdir()
        (brain / "lessons.md").write_text("", encoding="utf-8")
        (tmp_path / "pre").mkdir()
        (tmp_path / "post").mkdir()

        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "remove", "nonexistent-slug"],
            capture_output=True, text=True, env=self._env(tmp_path), cwd=str(tmp_path),
        )
        assert proc.returncode == 0
        assert "nothing to remove" in proc.stdout.lower() or "no" in proc.stdout.lower()

    def test_rule_remove_finds_hook_in_post_dir(self, tmp_path):
        """auto_test lives in post-tool dir; remove should find it there too."""
        import subprocess, sys
        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        post = tmp_path / "post"
        pre.mkdir(parents=True)
        post.mkdir(parents=True)

        self._write_lessons(brain, [
            "[2026-04-13] [RULE:1.00] TEST_TRIGGER: [hooked] always run tests after edit",
        ])
        post_hook = post / "always-run-tests-after-edit.js"
        post_hook.write_text("// stub\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "-m", "gradata.cli", "rule", "remove", "always-run-tests-after-edit"],
            capture_output=True, text=True, env=self._env(tmp_path), cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        assert not post_hook.exists()


class TestRuleToHookEvents:
    def _make_brain(self, tmp_path):
        from gradata.brain import Brain
        return Brain.init(
            tmp_path / "brain",
            name="EventsTest",
            domain="Testing",
            embedding="local",
            interactive=False,
        )

    def test_emits_installed_event_on_success(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        brain = self._make_brain(tmp_path)

        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate, brain=brain, source="user_declared")
        assert result.installed

        events = brain.query_events(event_type="RULE_TO_HOOK_INSTALLED", last_n_sessions=1)
        assert len(events) == 1
        data = events[0]["data"]
        assert data["slug"]
        assert data["template"] == "regex_replace"
        assert "never use em dashes" in data["rule_text"].lower()
        assert events[0]["source"] == "user_declared"

    def test_emits_failed_event_on_skip(self, tmp_path, monkeypatch):
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        brain = self._make_brain(tmp_path)

        candidate = classify_rule("Be concise and direct", 0.91)  # non-deterministic
        result = try_generate(candidate, brain=brain, source="graduate")
        assert not result.installed

        events = brain.query_events(event_type="RULE_TO_HOOK_FAILED", last_n_sessions=1)
        assert len(events) == 1
        assert events[0]["data"]["reason"]
        assert events[0]["source"] == "graduate"

    def test_no_brain_skips_logging_gracefully(self, tmp_path, monkeypatch):
        """try_generate without brain=... must still work (backward-compat)."""
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(tmp_path))
        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate)  # no brain kwarg
        assert result.installed  # still works


class TestStaleHookCheck:
    def test_detects_stale_hook_when_rule_text_changes(self, tmp_path, monkeypatch):
        """Install an em-dash hook, then modify the lesson text -> SessionStart check warns."""
        import subprocess, sys, os
        from pathlib import Path as _P

        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        post = tmp_path / "post"
        pre.mkdir(parents=True)
        post.mkdir(parents=True)
        brain.mkdir(parents=True)

        # Install a real hook
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(pre))
        monkeypatch.setenv("GRADATA_HOOK_ROOT_POST", str(post))
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate)
        assert result.installed

        # Write a lesson with MODIFIED text (different hash)
        (brain / "lessons.md").write_text(
            "[2026-04-13] [RULE:1.00] FORMATTING: [hooked] avoid em dashes everywhere\n",
            encoding="utf-8",
        )

        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "GRADATA_HOOK_ROOT": str(pre),
               "GRADATA_HOOK_ROOT_POST": str(post),
               "PYTHONPATH": str(_P(__file__).resolve().parents[1] / "src")}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.hooks.stale_hook_check"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=10,
        )
        assert proc.returncode == 0  # never block session
        assert "stale" in proc.stdout.lower()
        assert "never-use-em-dashes" in proc.stdout.lower() or "em" in proc.stdout.lower()

    def test_no_warning_when_hashes_match(self, tmp_path, monkeypatch):
        """Install + leave lesson text unchanged -> no stale warning."""
        import subprocess, sys, os
        from pathlib import Path as _P

        brain = tmp_path / "brain"
        pre = tmp_path / "pre"
        post = tmp_path / "post"
        pre.mkdir(parents=True)
        post.mkdir(parents=True)
        brain.mkdir(parents=True)

        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(pre))
        monkeypatch.setenv("GRADATA_HOOK_ROOT_POST", str(post))
        from gradata.enhancements.rule_to_hook import classify_rule, try_generate
        candidate = classify_rule("Never use em dashes", 0.95)
        result = try_generate(candidate)
        assert result.installed

        (brain / "lessons.md").write_text(
            "[2026-04-13] [RULE:1.00] FORMATTING: [hooked] Never use em dashes\n",
            encoding="utf-8",
        )

        env = {**os.environ,
               "GRADATA_BRAIN": str(brain),
               "GRADATA_HOOK_ROOT": str(pre),
               "GRADATA_HOOK_ROOT_POST": str(post),
               "PYTHONPATH": str(_P(__file__).resolve().parents[1] / "src")}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.hooks.stale_hook_check"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=10,
        )
        assert proc.returncode == 0
        assert "stale" not in proc.stdout.lower()

    def test_no_hooks_installed_exits_silently(self, tmp_path):
        """Fresh install, no generated hooks -> no output, exit 0."""
        import subprocess, sys, os
        from pathlib import Path as _P

        empty = tmp_path / "empty"
        empty.mkdir()
        env = {**os.environ,
               "GRADATA_HOOK_ROOT": str(empty),
               "GRADATA_HOOK_ROOT_POST": str(empty),
               "PYTHONPATH": str(_P(__file__).resolve().parents[1] / "src")}
        proc = subprocess.run(
            [sys.executable, "-m", "gradata.hooks.stale_hook_check"],
            capture_output=True, text=True, env=env, timeout=10,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_installer_registers_session_start_entry(self):
        from gradata.hooks._installer import HOOK_REGISTRY
        entries = [e for e in HOOK_REGISTRY if e[0] == "stale_hook_check"]
        assert len(entries) == 1
        assert entries[0][1] == "SessionStart"
