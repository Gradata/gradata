"""Tests for context_inject hook — dedup against .last_injection.json rules."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gradata.hooks.context_inject import (
    _is_duplicate,
    _jaccard,
    _load_injected_descriptions,
    main,
)

# ---------------------------------------------------------------------------
# Unit: _jaccard
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_strings_return_one(self) -> None:
        assert _jaccard("foo bar baz", "foo bar baz") == 1.0

    def test_disjoint_strings_return_zero(self) -> None:
        assert _jaccard("alpha beta", "gamma delta") == 0.0

    def test_empty_string_returns_zero(self) -> None:
        assert _jaccard("", "foo bar") == 0.0
        assert _jaccard("foo bar", "") == 0.0

    def test_partial_overlap(self) -> None:
        # {"foo", "bar"} ∩ {"foo", "baz"} = {"foo"}, union = 3 → 1/3
        score = _jaccard("foo bar", "foo baz")
        assert abs(score - 1 / 3) < 1e-9

    def test_case_insensitive(self) -> None:
        assert _jaccard("Foo BAR", "foo bar") == 1.0


# ---------------------------------------------------------------------------
# Unit: _load_injected_descriptions
# ---------------------------------------------------------------------------


class TestLoadInjectedDescriptions:
    def test_returns_descriptions_from_manifest(self, tmp_path: Path) -> None:
        manifest = {
            "anchors": {
                "ab12": {
                    "full_id": "ab12cd34ef56",
                    "category": "PATHS",
                    "description": "Always use absolute paths when referencing files",
                    "state": "RULE",
                    "cluster_category": None,
                },
                "cd34": {
                    "full_id": "cd34ab12ef56",
                    "category": "PROSE",
                    "description": "Avoid em dashes in marketing copy",
                    "state": "RULE",
                    "cluster_category": None,
                },
            }
        }
        (tmp_path / ".last_injection.json").write_text(json.dumps(manifest), encoding="utf-8")
        descs = _load_injected_descriptions(str(tmp_path))
        assert len(descs) == 2
        assert "Always use absolute paths when referencing files" in descs
        assert "Avoid em dashes in marketing copy" in descs

    def test_missing_manifest_returns_empty(self, tmp_path: Path) -> None:
        assert _load_injected_descriptions(str(tmp_path)) == []

    def test_malformed_json_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / ".last_injection.json").write_text("not-json", encoding="utf-8")
        assert _load_injected_descriptions(str(tmp_path)) == []

    def test_entry_without_description_skipped(self, tmp_path: Path) -> None:
        manifest = {"anchors": {"ab12": {"full_id": "ab12cd34ef56", "category": "X"}}}
        (tmp_path / ".last_injection.json").write_text(json.dumps(manifest), encoding="utf-8")
        assert _load_injected_descriptions(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# Unit: _is_duplicate
# ---------------------------------------------------------------------------


class TestIsDuplicate:
    def test_high_overlap_is_duplicate(self) -> None:
        desc = "always use absolute paths when referencing files in the project"
        snippet = "always use absolute paths when referencing files in your project"
        # High Jaccard → duplicate
        assert _is_duplicate(snippet, [desc], threshold=0.70) is True

    def test_low_overlap_is_not_duplicate(self) -> None:
        desc = "always use absolute paths when referencing files"
        snippet = "deploy kubernetes cluster to production environment today"
        assert _is_duplicate(snippet, [desc], threshold=0.70) is False

    def test_empty_descriptions_list_never_duplicate(self) -> None:
        assert _is_duplicate("any snippet text here", [], threshold=0.70) is False

    def test_threshold_boundary(self) -> None:
        # Exactly at threshold: treated as duplicate (>=)
        a = "alpha beta gamma delta"
        b = "alpha beta gamma delta"
        assert _is_duplicate(a, [b], threshold=1.0) is True

    def test_just_below_threshold_not_duplicate(self) -> None:
        # 3/4 = 0.75 overlap — below 0.80 threshold
        a = "alpha beta gamma delta"
        b = "alpha beta gamma epsilon"
        score = _jaccard(
            a, b
        )  # {"alpha","beta","gamma"} / {"alpha","beta","gamma","delta","epsilon"} = 3/5 = 0.6
        assert _is_duplicate(a, [b], threshold=0.80) is (score >= 0.80)


# ---------------------------------------------------------------------------
# Integration: main() dedup against .last_injection.json
# ---------------------------------------------------------------------------


class TestMainDedup:
    """Verify that snippets duplicating already-injected rules are dropped."""

    # A message longer than the default MIN_MESSAGE_LEN=100. MIN_MESSAGE_LEN is
    # baked as a module-level constant at import time, so we cannot override it
    # via monkeypatch.setenv after the module has been imported. Use a message
    # that satisfies the default threshold instead.
    _LONG_MSG = (
        "How should I correctly reference files when working inside this project? "
        "I want to make sure I use the right conventions for file paths every time."
    )

    @pytest.fixture
    def brain_dir(self, tmp_path: Path, monkeypatch) -> Path:
        monkeypatch.setenv("GRADATA_CONTEXT_INJECT", "1")
        monkeypatch.setenv("GRADATA_CONTEXT_DEDUP", "1")
        monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
        return tmp_path

    def _make_manifest(self, brain_dir: Path, descriptions: list[str]) -> None:
        anchors = {}
        for i, desc in enumerate(descriptions):
            anchor = f"{i:04x}"
            anchors[anchor] = {
                "full_id": f"{anchor}{'0' * 8}",
                "category": "TEST",
                "description": desc,
                "state": "RULE",
                "cluster_category": None,
            }
        (brain_dir / ".last_injection.json").write_text(
            json.dumps({"anchors": anchors}), encoding="utf-8"
        )

    def test_duplicate_snippet_is_filtered(self, brain_dir: Path) -> None:
        """A snippet with >70% overlap against an injected rule must be dropped."""
        rule_desc = "always use absolute paths when referencing files in the project"
        duplicate_snippet = "always use absolute paths when referencing files in your project"
        unique_snippet = "deploy kubernetes cluster to production environment today with helm"

        self._make_manifest(brain_dir, [rule_desc])

        # Brain is imported lazily inside main(); patch at its source module.
        with patch("gradata.brain.Brain") as MockBrain:
            inst = MagicMock()
            inst.search.return_value = [{"text": duplicate_snippet}, {"text": unique_snippet}]
            MockBrain.return_value = inst
            result = main({"message": self._LONG_MSG})

        assert result is not None, "Expected non-None result (unique snippet should pass)"
        assert duplicate_snippet not in result["result"], "Duplicate snippet must be filtered"
        assert unique_snippet in result["result"], "Unique snippet must survive dedup"

    def test_all_snippets_duplicate_returns_none(self, brain_dir: Path) -> None:
        """If every snippet is a duplicate, main() returns None."""
        rule_desc = "always use absolute paths when referencing files in the project"
        duplicate = "always use absolute paths when referencing files in your project"

        self._make_manifest(brain_dir, [rule_desc])

        with patch("gradata.brain.Brain") as MockBrain:
            inst = MagicMock()
            inst.search.return_value = [{"text": duplicate}]
            MockBrain.return_value = inst
            result = main({"message": self._LONG_MSG})

        assert result is None

    def test_dedup_disabled_passes_duplicates_through(self, brain_dir: Path, monkeypatch) -> None:
        """GRADATA_CONTEXT_DEDUP=0 must let duplicate snippets pass through."""
        monkeypatch.setenv("GRADATA_CONTEXT_DEDUP", "0")
        rule_desc = "always use absolute paths when referencing files in the project"
        duplicate = "always use absolute paths when referencing files in your project"

        self._make_manifest(brain_dir, [rule_desc])

        with patch("gradata.brain.Brain") as MockBrain:
            inst = MagicMock()
            inst.search.return_value = [{"text": duplicate}]
            MockBrain.return_value = inst
            result = main({"message": self._LONG_MSG})

        assert result is not None, "Dedup disabled — duplicate must pass through"
        assert duplicate in result["result"]

    def test_no_manifest_passes_all_snippets(self, brain_dir: Path) -> None:
        """When .last_injection.json is absent, no dedup occurs."""
        snippet = "always use absolute paths when referencing files in your project"

        with patch("gradata.brain.Brain") as MockBrain:
            inst = MagicMock()
            inst.search.return_value = [{"text": snippet}]
            MockBrain.return_value = inst
            result = main({"message": self._LONG_MSG})

        assert result is not None
        assert snippet in result["result"]

    def test_kill_switch_returns_none(self, brain_dir: Path, monkeypatch) -> None:
        """GRADATA_CONTEXT_INJECT=0 must short-circuit before any search."""
        monkeypatch.setenv("GRADATA_CONTEXT_INJECT", "0")
        # Brain is never reached, no patch needed — just verify early return.
        result = main({"message": self._LONG_MSG})
        assert result is None

    def test_short_message_skipped(self, brain_dir: Path) -> None:
        """Messages shorter than MIN_MESSAGE_LEN must be skipped."""
        # Brain is never reached for short messages — verify early return.
        result = main({"message": "hi"})
        assert result is None
