"""Tests for ``gradata.enhancements.rule_export.export_rules``.

Covers the cross-platform export targets — cursor, agents, aider (existing)
plus codex, cline, continue (new).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gradata.enhancements.rule_export import _FORMATTERS, DEFAULT_PATHS, export_rules

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_lessons(brain_root: Path, lessons_text: str) -> None:
    brain_root.mkdir(parents=True, exist_ok=True)
    (brain_root / "lessons.md").write_text(lessons_text, encoding="utf-8")


SAMPLE_LESSONS = """\
[2026-04-13] [RULE:0.95] DRAFTING: Use colons not em-dashes
[2026-04-13] [RULE:0.91] PROCESS: Run tests after code changes
[2026-04-13] [PATTERN:0.70] DRAFTING: Keep emails under 100 words
[2026-04-13] [RULE:0.92] DRAFTING: Lead with the answer
[2026-04-13] [RULE:0.96] SAFETY: Never hardcode secrets
"""


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_new_targets_registered(self) -> None:
        for t in ("codex", "cline", "continue"):
            assert t in _FORMATTERS
            assert t in DEFAULT_PATHS

    def test_default_paths_are_distinct(self) -> None:
        # Each target has a distinct default output path (no collisions)
        paths = list(DEFAULT_PATHS.values())
        assert len(paths) == len(set(paths))

    def test_unknown_target_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unknown target"):
            export_rules(tmp_path, target="bogus")


# ---------------------------------------------------------------------------
# Codex
# ---------------------------------------------------------------------------


class TestCodex:
    def test_default_path_is_codex_agents(self) -> None:
        assert DEFAULT_PATHS["codex"] == ".codex/AGENTS.md"

    def test_empty_brain_produces_placeholder(self, tmp_path: Path) -> None:
        text = export_rules(tmp_path, target="codex")
        assert "# Codex AGENTS.md" in text
        assert "No graduated rules yet" in text

    def test_rules_grouped_by_category(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_rules(tmp_path, target="codex")
        # Header
        assert "# Codex AGENTS.md" in text
        # Categories present as markdown sub-headings
        assert "## DRAFTING" in text
        assert "## PROCESS" in text
        assert "## SAFETY" in text
        # Only RULE-tier rules — the PATTERN lesson should NOT appear
        assert "Keep emails under 100 words" not in text
        # Rule content present
        assert "- Use colons not em-dashes" in text
        assert "- Run tests after code changes" in text
        assert "- Lead with the answer" in text


# ---------------------------------------------------------------------------
# Cline
# ---------------------------------------------------------------------------


class TestCline:
    def test_default_path_is_clinerules(self) -> None:
        assert DEFAULT_PATHS["cline"] == ".clinerules"

    def test_empty_brain_produces_placeholder(self, tmp_path: Path) -> None:
        text = export_rules(tmp_path, target="cline")
        assert "# Cline Rules" in text
        assert "No graduated rules yet" in text

    def test_rules_grouped_by_category(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_rules(tmp_path, target="cline")
        assert "# Cline Rules" in text
        assert "## DRAFTING" in text
        assert "- Never hardcode secrets" in text
        # PATTERN-tier excluded
        assert "Keep emails under 100 words" not in text


# ---------------------------------------------------------------------------
# Continue.dev
# ---------------------------------------------------------------------------


class TestContinue:
    def test_default_path_is_continue_rules_md(self) -> None:
        assert DEFAULT_PATHS["continue"] == ".continue/rules/gradata-rules.md"

    def test_empty_brain_produces_placeholder(self, tmp_path: Path) -> None:
        text = export_rules(tmp_path, target="continue")
        assert "# Continue.dev Rules" in text
        assert "No graduated rules yet" in text

    def test_rules_grouped_by_category(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_rules(tmp_path, target="continue")
        assert "# Continue.dev Rules" in text
        assert "## DRAFTING" in text
        assert "## PROCESS" in text
        assert "- Lead with the answer" in text
        # PATTERN-tier excluded
        assert "Keep emails under 100 words" not in text


# ---------------------------------------------------------------------------
# Shared semantics: [hooked] marker stripping, RULE-only filter
# ---------------------------------------------------------------------------


class TestSharedSemantics:
    @pytest.mark.parametrize("target", ["codex", "cline", "continue"])
    def test_hooked_marker_stripped(self, tmp_path: Path, target: str) -> None:
        _write_lessons(
            tmp_path,
            "[2026-04-13] [RULE:0.95] [hooked] DRAFTING: Use colons not em-dashes\n",
        )
        text = export_rules(tmp_path, target=target)
        # The internal [hooked] marker should NOT leak into exports
        assert "[hooked]" not in text
        assert "- Use colons not em-dashes" in text

    @pytest.mark.parametrize("target", ["codex", "cline", "continue"])
    def test_non_rule_states_excluded(self, tmp_path: Path, target: str) -> None:
        _write_lessons(
            tmp_path,
            "[2026-04-13] [INSTINCT:0.3] CAT: Instinct rule should not export\n"
            "[2026-04-13] [PATTERN:0.7] CAT: Pattern rule should not export\n"
            "[2026-04-13] [RULE:0.95] CAT: Only this one exports\n",
        )
        text = export_rules(tmp_path, target=target)
        assert "Only this one exports" in text
        assert "Instinct rule" not in text
        assert "Pattern rule should not export" not in text


# ---------------------------------------------------------------------------
# Regression: existing targets still work
# ---------------------------------------------------------------------------


class TestExistingTargetsRegression:
    @pytest.mark.parametrize("target", ["cursor", "agents", "aider"])
    def test_existing_targets_still_work(self, tmp_path: Path, target: str) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_rules(tmp_path, target=target)
        assert len(text) > 0
        # All existing targets include a rule
        assert "Lead with the answer" in text or "lead with the answer" in text
