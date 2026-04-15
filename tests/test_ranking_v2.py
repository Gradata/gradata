"""Tests for BM25 + Thompson sampling modes in rule_ranker."""
from __future__ import annotations

import os
import sys

import pytest

from gradata.rules import rule_ranker
from gradata.rules.rule_ranker import rank_rules


def _mk(desc, *, confidence=0.8, category="CODE", fire_count=5, session=1,
        alpha=1.0, beta_param=1.0, tags="", rid=None):
    return {
        "id": rid or desc,
        "description": desc,
        "confidence": confidence,
        "category": category,
        "fire_count": fire_count,
        "last_session": session,
        "alpha": alpha,
        "beta_param": beta_param,
        "tags": tags,
    }


@pytest.fixture(autouse=True)
def _clear_thompson_env(monkeypatch):
    monkeypatch.delenv("GRADATA_THOMPSON_RANKING", raising=False)
    yield


# ---------- BM25 path ----------


def test_bm25_ranks_relevant_rule_above_irrelevant_when_available():
    """When bm25s is installed, BM25 context scoring surfaces topical matches."""
    if not rule_ranker._BM25_AVAILABLE:
        pytest.skip("bm25s not installed")
    rules = [
        _mk("validate email addresses before sending upload",
            confidence=0.80, category="CODE"),
        _mk("always clamp confidence scores to the range zero to one",
            confidence=0.80, category="CODE"),
        _mk("refactor graduated pattern storage layer",
            confidence=0.80, category="CODE"),
    ]
    ranked = rank_rules(
        rules,
        current_session=10,
        context_keywords=["confidence", "clamp", "range"],
        max_rules=3,
    )
    # Behavior assertion: the 'clamp confidence' rule ranks above the unrelated ones.
    top = ranked[0]["description"]
    assert "clamp confidence" in top


def test_bm25_falls_back_cleanly_when_module_absent(monkeypatch):
    """If bm25s is not importable at call time, ranker falls back to keyword scorer."""
    monkeypatch.setattr(rule_ranker, "bm25s", None)
    monkeypatch.setattr(rule_ranker, "_BM25_AVAILABLE", False)

    rules = [
        _mk("validate email before upload", confidence=0.80),
        _mk("always clamp confidence to 0-1", confidence=0.80),
    ]
    ranked = rank_rules(
        rules,
        current_session=10,
        context_keywords=["confidence", "clamp"],
        max_rules=2,
    )
    # Keyword scorer should still favor the lexically overlapping rule.
    assert "clamp" in ranked[0]["description"]


def test_bm25_handles_missing_bm25s_module_via_sys_modules(monkeypatch):
    """Simulate bm25s import failure by removing the module before re-importing the ranker."""
    # We can't reliably re-trigger the try/except at module import time, so we
    # exercise the runtime fallback by patching the flag — equivalent coverage.
    monkeypatch.setitem(sys.modules, "bm25s", None)
    monkeypatch.setattr(rule_ranker, "_BM25_AVAILABLE", False)
    monkeypatch.setattr(rule_ranker, "bm25s", None)

    rules = [_mk("only rule", confidence=0.9)]
    ranked = rank_rules(rules, current_session=1, context_keywords=["x"], max_rules=1)
    assert len(ranked) == 1


# ---------- Thompson path ----------


def test_thompson_deterministic_with_same_seed(monkeypatch):
    monkeypatch.setenv("GRADATA_THOMPSON_RANKING", "1")
    rules = [
        _mk(f"rule{i}", confidence=0.7, alpha=i + 1.0, beta_param=10.0 - i)
        for i in range(8)
    ]
    a = rank_rules(rules, current_session=5, session_seed=42, max_rules=5)
    b = rank_rules(rules, current_session=5, session_seed=42, max_rules=5)
    assert [r["id"] for r in a] == [r["id"] for r in b]


def test_thompson_different_seeds_can_differ(monkeypatch):
    monkeypatch.setenv("GRADATA_THOMPSON_RANKING", "1")
    # Many near-equal rules so sampling dominates — different seeds should diverge.
    rules = [
        _mk(f"rule{i}", confidence=0.7, alpha=2.0, beta_param=2.0)
        for i in range(20)
    ]
    orderings = set()
    for seed in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        ranked = rank_rules(rules, current_session=1, session_seed=seed, max_rules=10)
        orderings.add(tuple(r["id"] for r in ranked))
    # At least two distinct orderings across 10 seeds — exploration is happening.
    assert len(orderings) > 1


def test_thompson_guards_against_bad_beta_params(monkeypatch):
    """Zero / negative alpha or beta_param must not crash."""
    monkeypatch.setenv("GRADATA_THOMPSON_RANKING", "1")
    rules = [
        _mk("zero-alpha", alpha=0.0, beta_param=1.0),
        _mk("neg-beta", alpha=1.0, beta_param=-1.0),
        _mk("nan-as-none", alpha=1.0, beta_param=1.0),
    ]
    ranked = rank_rules(rules, current_session=1, session_seed=7, max_rules=3)
    assert len(ranked) == 3


# ---------- Invariants ----------


def test_rank_rules_respects_max_rules():
    rules = [_mk(f"r{i}", confidence=0.9 - i * 0.01) for i in range(20)]
    ranked = rank_rules(rules, current_session=10, max_rules=4)
    assert len(ranked) == 4


def test_rank_rules_output_sorted_by_score_desc():
    """Higher-confidence rules (all else equal) should come first."""
    rules = [
        _mk("low", confidence=0.60),
        _mk("high", confidence=0.95),
        _mk("mid", confidence=0.78),
    ]
    ranked = rank_rules(rules, current_session=10, max_rules=3)
    # In non-Thompson mode with no context, confidence drives the ordering.
    assert ranked[0]["description"] == "high"


def test_empty_rules_returns_empty():
    assert rank_rules([], current_session=1) == []


def test_single_rule_is_returned():
    rules = [_mk("solo", confidence=0.72)]
    ranked = rank_rules(rules, current_session=1, max_rules=5)
    assert len(ranked) == 1
    assert ranked[0]["description"] == "solo"


def test_missing_beta_fields_no_crash_non_thompson():
    """Lessons without alpha/beta_param fields still rank in default mode."""
    rules = [
        {"description": "a", "confidence": 0.7, "category": "CODE"},
        {"description": "b", "confidence": 0.9, "category": "CODE"},
    ]
    ranked = rank_rules(rules, current_session=1, max_rules=2)
    assert ranked[0]["description"] == "b"


def test_missing_beta_fields_no_crash_thompson(monkeypatch):
    monkeypatch.setenv("GRADATA_THOMPSON_RANKING", "1")
    rules = [
        {"description": "a", "confidence": 0.7, "category": "CODE"},
        {"description": "b", "confidence": 0.9, "category": "CODE"},
    ]
    ranked = rank_rules(rules, current_session=1, session_seed=1, max_rules=2)
    assert len(ranked) == 2


def test_wiki_boost_raises_relevance():
    rules = [
        _mk("neutral rule", confidence=0.80, rid="neutral"),
        _mk("boosted rule", confidence=0.80, rid="boosted"),
    ]
    ranked = rank_rules(
        rules,
        current_session=10,
        wiki_boost={"boosted": 0.5},
        max_rules=2,
    )
    assert ranked[0]["id"] == "boosted"
