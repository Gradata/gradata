"""Profile gating tests for ``generated_runner`` + ``generated_runner_post``.

Every other Gradata hook in ``_installer.HOOK_REGISTRY`` routes through
``run_hook`` which respects ``GRADATA_HOOK_PROFILE``. The generated-hook
runners bypass ``run_hook`` (they use ``sys.exit(main())`` not
``run_hook(main, meta)``) so they MUST do their own profile check.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_blocking_hook(dst: Path, stem: str = "always-block") -> Path:
    """Write a tiny Node.js hook that always blocks (exit 2)."""
    hook = dst / f"{stem}.js"
    hook.write_text(
        "process.stdin.resume();\n"
        "process.stdout.write(JSON.stringify({decision:'block',reason:'test'}));\n"
        "process.exit(2);\n",
        encoding="utf-8",
    )
    return hook


# ---------------------------------------------------------------------------
# Profile gating
# ---------------------------------------------------------------------------


class TestMinimalProfileSkips:
    def test_pre_runner_noops_under_minimal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``GRADATA_HOOK_PROFILE=minimal`` must skip the pre-tool runner."""
        hook_root = tmp_path / "gen"
        hook_root.mkdir()
        _make_blocking_hook(hook_root)

        monkeypatch.setenv("GRADATA_HOOK_PROFILE", "minimal")
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_root))
        monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_name":"Edit"}'))

        from gradata.hooks._generated_runner_core import run_generated_hooks

        rc = run_generated_hooks(
            env_var="GRADATA_HOOK_ROOT",
            default_dir=".claude/hooks/pre-tool/generated",
            per_hook_timeout=5,
        )
        assert rc == 0  # no block propagated — hook never ran
        captured = capsys.readouterr()
        # No block payload should have been written to stdout
        assert "block" not in captured.out.lower()

    def test_post_runner_noops_under_minimal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hook_root = tmp_path / "post_gen"
        hook_root.mkdir()
        _make_blocking_hook(hook_root, stem="post-block")

        monkeypatch.setenv("GRADATA_HOOK_PROFILE", "minimal")
        monkeypatch.setenv("GRADATA_HOOK_ROOT_POST", str(hook_root))
        monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_name":"Write"}'))

        from gradata.hooks._generated_runner_core import run_generated_hooks

        rc = run_generated_hooks(
            env_var="GRADATA_HOOK_ROOT_POST",
            default_dir=".claude/hooks/post-tool/generated",
            per_hook_timeout=30,
        )
        assert rc == 0


class TestStandardProfileRuns:
    def test_standard_profile_executes_generated_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Under ``standard`` (default), generated hooks must execute."""
        hook_root = tmp_path / "gen"
        hook_root.mkdir()
        _make_blocking_hook(hook_root)

        monkeypatch.setenv("GRADATA_HOOK_PROFILE", "standard")
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_root))
        monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_name":"Edit"}'))

        # Skip if node isn't available (CI sanity — we only care about gating)
        import shutil
        if shutil.which("node") is None:
            pytest.skip("node not installed")

        from gradata.hooks._generated_runner_core import run_generated_hooks

        rc = run_generated_hooks(
            env_var="GRADATA_HOOK_ROOT",
            default_dir=".claude/hooks/pre-tool/generated",
            per_hook_timeout=5,
        )
        # The blocking hook exits 2 — runner should propagate that
        assert rc == 2
        assert "block" in capsys.readouterr().out.lower()

    def test_unset_profile_defaults_to_standard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no env var set, treat as standard (runner executes)."""
        hook_root = tmp_path / "gen"
        hook_root.mkdir()
        # No .js files — runner should return 0, but NOT because of profile
        monkeypatch.delenv("GRADATA_HOOK_PROFILE", raising=False)
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_root))
        monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_name":"Edit"}'))

        from gradata.hooks._generated_runner_core import run_generated_hooks

        rc = run_generated_hooks(
            env_var="GRADATA_HOOK_ROOT",
            default_dir=".claude/hooks/pre-tool/generated",
            per_hook_timeout=5,
        )
        assert rc == 0  # no hooks present, not profile-skipped


class TestStrictProfileRuns:
    def test_strict_profile_executes_generated_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        hook_root = tmp_path / "gen"
        hook_root.mkdir()
        _make_blocking_hook(hook_root)

        monkeypatch.setenv("GRADATA_HOOK_PROFILE", "strict")
        monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_root))
        monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_name":"Edit"}'))

        import shutil
        if shutil.which("node") is None:
            pytest.skip("node not installed")

        from gradata.hooks._generated_runner_core import run_generated_hooks

        rc = run_generated_hooks(
            env_var="GRADATA_HOOK_ROOT",
            default_dir=".claude/hooks/pre-tool/generated",
            per_hook_timeout=5,
        )
        assert rc == 2
