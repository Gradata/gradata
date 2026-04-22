"""Tests for just-in-time (JIT) rule injection hook."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradata._types import Lesson, LessonState
from gradata.hooks import jit_inject
from gradata.hooks.jit_inject import (
    _jaccard,
    _tokenize,
    main,
    rank_rules_for_draft,
)


def _lesson(
    category: str,
    description: str,
    *,
    confidence: float = 0.92,
    state: LessonState = LessonState.RULE,
) -> Lesson:
    return Lesson(
        date="2026-04-14",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
    )


class TestTokenize:
    def test_drops_stopwords(self) -> None:
        toks = _tokenize("The cat sat on the mat")
        assert "the" not in toks
        assert "on" not in toks
        assert "cat" in toks
        assert "mat" in toks

    def test_drops_short_tokens(self) -> None:
        assert _tokenize("a b cd xyz") == {"xyz"}

    def test_lowercases(self) -> None:
        assert _tokenize("Pipedrive DEAL") == {"pipedrive", "deal"}


class TestJaccard:
    def test_identical_sets_score_one(self) -> None:
        a = {"foo", "bar"}
        assert _jaccard(a, a) == 1.0

    def test_disjoint_sets_score_zero(self) -> None:
        assert _jaccard({"foo"}, {"bar"}) == 0.0

    def test_empty_sets_score_zero(self) -> None:
        assert _jaccard(set(), {"foo"}) == 0.0
        assert _jaccard({"foo"}, set()) == 0.0


class TestRankRulesForDraft:
    def test_high_similarity_rule_is_selected(self) -> None:
        lessons = [
            _lesson("PIPEDRIVE", "Never auto-tag CEOs on pipedrive deals"),
            _lesson("PROSE", "Avoid em dashes in marketing prose"),
        ]
        draft = "Please update the pipedrive deal and tag the CEO"
        ranked = rank_rules_for_draft(lessons, draft, k=5, min_similarity=0.05)
        assert len(ranked) == 1
        assert ranked[0][0].category == "PIPEDRIVE"

    def test_low_similarity_rule_is_filtered(self) -> None:
        lessons = [_lesson("UNRELATED", "spec grammar nouns verbs clauses")]
        draft = "Deploy the kubernetes cluster to production"
        ranked = rank_rules_for_draft(lessons, draft, min_similarity=0.05)
        assert ranked == []

    def test_k_cap_is_respected(self) -> None:
        lessons = [
            _lesson("ONE", "deploy kubernetes cluster production"),
            _lesson("TWO", "kubernetes cluster deployment production"),
            _lesson("THREE", "production cluster kubernetes deploy"),
            _lesson("FOUR", "cluster deploy production kubernetes"),
        ]
        draft = "deploy the kubernetes production cluster today"
        ranked = rank_rules_for_draft(lessons, draft, k=2, min_similarity=0.01)
        assert len(ranked) == 2

    def test_confidence_floor_excludes_instincts(self) -> None:
        lessons = [
            _lesson(
                "LOWCONF",
                "kubernetes deploy production",
                confidence=0.40,
                state=LessonState.INSTINCT,
            ),
            _lesson("HIGHCONF", "kubernetes deploy production", confidence=0.95),
        ]
        draft = "deploy kubernetes to production"
        ranked = rank_rules_for_draft(lessons, draft, min_similarity=0.01)
        assert len(ranked) == 1
        assert ranked[0][0].category == "HIGHCONF"

    def test_killed_and_archived_excluded(self) -> None:
        lessons = [
            _lesson("ARCHIVED", "kubernetes deploy", state=LessonState.ARCHIVED),
            _lesson("KILLED", "kubernetes deploy", state=LessonState.KILLED),
            _lesson("RULE", "kubernetes deploy"),
        ]
        ranked = rank_rules_for_draft(
            lessons,
            "kubernetes deploy tomorrow",
            min_similarity=0.01,
        )
        assert len(ranked) == 1
        assert ranked[0][0].category == "RULE"

    def test_empty_draft_returns_empty(self) -> None:
        lessons = [_lesson("X", "anything")]
        assert rank_rules_for_draft(lessons, "") == []

    def test_k_zero_returns_empty(self) -> None:
        lessons = [_lesson("X", "kubernetes deploy")]
        assert rank_rules_for_draft(lessons, "kubernetes deploy", k=0) == []

    def test_ranked_by_similarity_desc(self) -> None:
        lessons = [
            _lesson("LOW", "kubernetes spec grammar nouns verbs clauses"),
            _lesson("HIGH", "kubernetes deploy production today"),
        ]
        ranked = rank_rules_for_draft(
            lessons,
            "deploy kubernetes to production today",
            k=5,
            min_similarity=0.01,
        )
        assert ranked[0][0].category == "HIGH"
        assert ranked[0][1] > ranked[1][1]

    def test_bm25_path_ranks_rare_terms_higher(self, monkeypatch) -> None:
        pytest.importorskip("bm25s")
        monkeypatch.setattr(jit_inject, "_BM25_AVAILABLE", True)
        lessons = [
            _lesson("COMMON", "deploy production today kubernetes"),
            _lesson("RARE", "rollback postgres replica lag alerts"),
        ]
        ranked = rank_rules_for_draft(
            lessons,
            "postgres replica lag during rollback",
            k=5,
            min_similarity=0.0,
        )
        assert ranked[0][0].category == "RARE"

    def test_falls_back_to_jaccard_when_bm25_unavailable(self, monkeypatch) -> None:
        monkeypatch.setattr(jit_inject, "_BM25_AVAILABLE", False)
        monkeypatch.setattr(jit_inject, "bm25s", None)
        lessons = [_lesson("X", "kubernetes deploy production today")]
        ranked = rank_rules_for_draft(
            lessons,
            "deploy kubernetes production today",
            k=5,
            min_similarity=0.05,
        )
        assert len(ranked) == 1
        assert ranked[0][0].category == "X"


class TestMainHookFlagOff:
    def test_flag_off_returns_none(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.delenv("GRADATA_JIT_ENABLED", raising=False)
        result = main({"prompt": "deploy the kubernetes cluster"})
        assert result is None

    def test_flag_explicit_false_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("GRADATA_JIT_ENABLED", "false")
        result = main({"prompt": "deploy the kubernetes cluster"})
        assert result is None


class TestMainHookFlagOn:
    @pytest.fixture
    def brain(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("GRADATA_JIT_ENABLED", "1")
        monkeypatch.setenv("GRADATA_HOOK_PROFILE", "standard")
        monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
        lessons_md = tmp_path / "lessons.md"
        lessons_md.write_text(
            "[2026-04-14] [RULE:0.92] PIPEDRIVE: Never auto-tag CEOs on pipedrive deals\n"
            "[2026-04-14] [RULE:0.91] PROSE: Avoid em dashes in marketing prose\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_short_prompt_skipped(self, brain: Path) -> None:
        assert main({"prompt": "hi"}) is None

    def test_slash_command_skipped(self, brain: Path) -> None:
        assert main({"prompt": "/foo bar baz pipedrive deal"}) is None

    def test_relevant_prompt_injects(self, brain: Path) -> None:
        result = main({"prompt": "Update the pipedrive deal for the CEO today"})
        assert result is not None
        # Autoresearch token-compression dropped the <brain-rules-jit> wrapper
        # AND the CATEGORY: prefix - output is now bare description text.
        assert "pipedrive" in result["result"].lower()
        # PROSE rule description mentions em dashes - unrelated; must not appear.
        assert "em dashes" not in result["result"].lower()

    def test_irrelevant_prompt_returns_none(self, brain: Path) -> None:
        result = main({"prompt": "Deploy the kubernetes cluster to aws"})
        assert result is None

    def test_zero_match_emits_nothing(self, brain: Path) -> None:
        """Zero-match prompts must NOT write to events.jsonl (hot-path I/O fix)."""
        main({"prompt": "Deploy the kubernetes cluster to aws"})
        events_path = brain / "events.jsonl"
        assert not events_path.exists(), "events.jsonl should not be created on zero-match"

    def test_event_emitted_on_hit(self, brain: Path) -> None:
        main({"prompt": "Update the pipedrive deal for the CEO today"})
        events_path = brain / "events.jsonl"
        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        payload = json.loads(lines[0])
        assert payload["injected"] == 1

    def test_k_override_via_env(self, brain: Path, monkeypatch) -> None:
        # Add more matching rules, cap k=1 via env
        (brain / "lessons.md").write_text(
            "[2026-04-14] [RULE:0.95] ONE: pipedrive deal ceo tagging rule\n"
            "[2026-04-14] [RULE:0.94] TWO: pipedrive deal ceo naming rule\n"
            "[2026-04-14] [RULE:0.93] THREE: pipedrive deal ceo update rule\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("GRADATA_JIT_MAX_RULES", "1")
        result = main({"prompt": "Update the pipedrive deal for the CEO today"})
        assert result is not None
        # Exactly one rule line in the bare rules block (wrapper + [..] prefix
        # dropped by autoresearch token-compression).
        body = result["result"]
        rule_lines = [ln for ln in body.splitlines() if ln.strip()]
        assert len(rule_lines) == 1


class TestJitEnvParsing:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("1", True),
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("on", True),
            ("0", False),
            ("false", False),
            ("", False),
            ("no", False),
        ],
    )
    def test_flag_parsing(self, monkeypatch, value: str, expected: bool) -> None:
        monkeypatch.setenv("GRADATA_JIT_ENABLED", value)
        assert jit_inject._jit_enabled() is expected
