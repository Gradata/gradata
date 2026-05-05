"""Tests for ``gradata.enhancements.skill_export``.

Covers ``_slugify``, ``_auto_description``, ``_filter_rules``,
``export_skill`` (string output), and ``write_skill`` (folder I/O).
"""

from __future__ import annotations

from pathlib import Path

from gradata.enhancements.skill_export import (
    _DESC_MAX_LEN,
    _auto_description,
    _filter_rules,
    _slugify,
    export_skill,
    write_skill,
)

SAMPLE_LESSONS = """\
[2026-04-13] [RULE:0.95] DRAFTING: Use colons not em-dashes
[2026-04-13] [RULE:0.91] PROCESS: Run tests after code changes
[2026-04-13] [PATTERN:0.70] DRAFTING: Keep emails under 100 words
[2026-04-13] [RULE:0.92] DRAFTING: Lead with the answer
[2026-04-13] [RULE:0.96] SAFETY: Never hardcode secrets
"""


def _write_lessons(brain_root: Path, lessons_text: str) -> None:
    brain_root.mkdir(parents=True, exist_ok=True)
    (brain_root / "lessons.md").write_text(lessons_text, encoding="utf-8")


class TestSlugify:
    def test_lowercases_and_hyphenates_spaces(self) -> None:
        assert _slugify("Sales Follow Ups") == "sales-follow-ups"

    def test_strips_special_chars(self) -> None:
        assert _slugify("Sales Follow-Ups!") == "sales-follow-ups"

    def test_collapses_repeated_separators(self) -> None:
        assert _slugify("  --weird---name--  ") == "weird-name"

    def test_empty_input_falls_back(self) -> None:
        assert _slugify("") == "gradata-skill"
        assert _slugify("!!!") == "gradata-skill"

    def test_preserves_digits(self) -> None:
        assert _slugify("v2 sales kit") == "v2-sales-kit"


class TestAutoDescription:
    def test_empty_rules_describes_skill_as_empty(self) -> None:
        desc = _auto_description([], "demo")
        assert "no graduated rules" in desc.lower()

    def test_lists_unique_categories(self) -> None:
        desc = _auto_description([("email", "a"), ("email", "b"), ("discovery", "c")], "demo")
        assert "email" in desc
        assert "discovery" in desc
        # Total rule count appears
        assert "3 rules" in desc

    def test_caps_to_six_categories(self) -> None:
        rules = [(f"cat{i}", f"rule{i}") for i in range(10)]
        desc = _auto_description(rules, "demo")
        assert "+4 more" in desc

    def test_clips_at_max_length(self) -> None:
        long_cat = "x" * 2000
        rules = [(long_cat, "rule")]
        desc = _auto_description(rules, "demo")
        assert len(desc) <= _DESC_MAX_LEN


class TestFilterRules:
    def test_no_filter_returns_all(self) -> None:
        rules = [("a", "x"), ("b", "y")]
        assert _filter_rules(rules, None) == rules

    def test_filter_is_case_insensitive(self) -> None:
        rules = [("EMAIL", "x"), ("draft", "y")]
        assert _filter_rules(rules, "email") == [("EMAIL", "x")]

    def test_no_match_returns_empty(self) -> None:
        rules = [("a", "x")]
        assert _filter_rules(rules, "missing") == []


class TestExportSkill:
    def test_empty_brain_produces_valid_skill_md(self, tmp_path: Path) -> None:
        text = export_skill(tmp_path, name="demo")
        # Frontmatter
        assert text.startswith("---\n")
        assert "name: demo\n" in text
        assert "description:" in text
        # Body has the empty-state placeholder
        assert "No graduated rules yet" in text

    def test_includes_rule_only_lessons_grouped_by_category(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_skill(tmp_path, name="demo")
        # Frontmatter still well-formed
        assert text.startswith("---\n")
        # Categories appear as ### sub-headings under ## Gotchas
        assert "## Gotchas" in text
        assert "### DRAFTING" in text
        assert "### PROCESS" in text
        assert "### SAFETY" in text
        # RULE content
        assert "- Use colons not em-dashes" in text
        assert "- Lead with the answer" in text
        # PATTERN-tier excluded
        assert "Keep emails under 100 words" not in text

    def test_explicit_description_overrides_auto(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_skill(tmp_path, name="demo", description="My custom blurb")
        assert 'description: "My custom blurb"' in text

    def test_double_quotes_in_description_are_escaped(self, tmp_path: Path) -> None:
        text = export_skill(tmp_path, name="demo", description='He said "hi" loudly')
        # Ensure the quote is backslash-escaped so YAML stays valid
        assert r'description: "He said \"hi\" loudly"' in text

    def test_backslash_in_description_is_escaped(self, tmp_path: Path) -> None:
        # Windows path with literal backslashes must produce an escaped YAML string.
        text = export_skill(tmp_path, name="demo", description=r"C:\Users\foo")
        assert r'description: "C:\\Users\\foo"' in text

    def test_backslash_and_quote_combined(self, tmp_path: Path) -> None:
        # Backslashes must be escaped BEFORE quotes so we don't accidentally
        # produce \\" sequences that break YAML.
        text = export_skill(tmp_path, name="demo", description=r'path C:\a "b"')
        assert r'description: "path C:\\a \"b\""' in text

    def test_multiline_literal_newline_in_description(self, tmp_path: Path) -> None:
        # A literal `\n` (two chars: backslash + n) must round-trip as `\\n`.
        text = export_skill(tmp_path, name="demo", description=r"line1\nline2")
        assert r'description: "line1\\nline2"' in text

    def test_whitespace_only_description_falls_back_to_auto(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_skill(tmp_path, name="demo", description="   \t\n  ")
        # Auto description must not be empty and must not be just whitespace.
        import re

        m = re.search(r'^description: "(.*)"$', text, flags=re.MULTILINE)
        assert m is not None, "description line missing"
        assert m.group(1).strip() != "", "whitespace-only desc should fall back to auto"

    def test_category_filter_narrows_output(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        text = export_skill(tmp_path, name="demo", category="DRAFTING")
        assert "### DRAFTING" in text
        # Other categories filtered out
        assert "### PROCESS" not in text
        assert "### SAFETY" not in text

    def test_name_is_slugified(self, tmp_path: Path) -> None:
        text = export_skill(tmp_path, name="My Sales Skill!")
        assert "name: my-sales-skill\n" in text

    def test_no_meta_skips_principles_section(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        # No system.db so meta loader returns [] anyway, but with --no-meta the
        # section header must also be absent regardless of DB state.
        text = export_skill(tmp_path, name="demo", include_meta=False)
        assert "## Meta-principles" not in text

    def test_hooked_marker_stripped(self, tmp_path: Path) -> None:
        _write_lessons(
            tmp_path,
            "[2026-04-13] [RULE:0.95] [hooked] DRAFTING: Use colons not em-dashes\n",
        )
        text = export_skill(tmp_path, name="demo")
        assert "[hooked]" not in text
        assert "- Use colons not em-dashes" in text

    def test_lessons_path_override(self, tmp_path: Path) -> None:
        # Brain root has no lessons.md, but we point at a custom location.
        custom = tmp_path / "elsewhere" / "my-lessons.md"
        custom.parent.mkdir(parents=True)
        custom.write_text(
            "[2026-04-13] [RULE:0.99] CUSTOM: Override path works\n",
            encoding="utf-8",
        )
        text = export_skill(tmp_path, name="demo", lessons_path=custom)
        assert "Override path works" in text


class TestWriteSkill:
    def test_creates_folder_and_writes_skill_md(self, tmp_path: Path) -> None:
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        out = tmp_path / "out"
        skill_md = write_skill(tmp_path, name="demo", output_dir=out)
        # Returned path points to the SKILL.md inside <output_dir>/<slug>/
        assert skill_md == out / "demo" / "SKILL.md"
        assert skill_md.exists()
        # File content matches export_skill output
        body = skill_md.read_text(encoding="utf-8")
        assert "name: demo\n" in body
        assert "### DRAFTING" in body

    def test_slugified_name_drives_folder_name(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        skill_md = write_skill(tmp_path, name="My Sales Skill!", output_dir=out)
        assert skill_md.parent.name == "my-sales-skill"

    def test_overwrites_existing_skill_md(self, tmp_path: Path) -> None:
        out = tmp_path / "out"
        # First write — no rules
        first = write_skill(tmp_path, name="demo", output_dir=out)
        assert "No graduated rules yet" in first.read_text(encoding="utf-8")
        # Add rules and rewrite — should be overwritten, not duplicated
        _write_lessons(tmp_path, SAMPLE_LESSONS)
        second = write_skill(tmp_path, name="demo", output_dir=out)
        assert second == first
        body = second.read_text(encoding="utf-8")
        assert "No graduated rules yet" not in body
        assert "### DRAFTING" in body
