"""Tests for brain.scope(), detect_cross_domain_candidates(), and suggest_scope_narrowing."""
from __future__ import annotations
import json
import pytest


# Feature 1: brain.scope()

def test_brain_scope_returns_str(tmp_path):
    from gradata.brain import Brain
    brain = Brain.init(str(tmp_path))
    result = brain.scope(domain="sales")
    assert isinstance(result, str)


def test_brain_scope_no_args_returns_str(tmp_path):
    from gradata.brain import Brain
    brain = Brain.init(str(tmp_path))
    result = brain.scope()
    assert isinstance(result, str)


def test_brain_scope_with_task_type(tmp_path):
    from gradata.brain import Brain
    brain = Brain.init(str(tmp_path))
    result = brain.scope(domain="sales", task_type="email_draft")
    assert isinstance(result, str)


def test_brain_scope_with_agent_type(tmp_path):
    from gradata.brain import Brain
    brain = Brain.init(str(tmp_path))
    result = brain.scope(domain="engineering", agent_type="reviewer")
    assert isinstance(result, str)


# Feature 2: detect_cross_domain_candidates()

def _make_lesson(description, domain, confidence=0.9):
    from gradata._types import Lesson, LessonState
    return Lesson(
        date="2024-01-01",
        state=LessonState.RULE,
        confidence=confidence,
        category="STYLE",
        description=description,
        scope_json=json.dumps({"domain": domain}),
    )


def test_detect_cross_domain_candidates_returns_candidates():
    from gradata.enhancements.meta_rules import detect_cross_domain_candidates
    desc = "Always be concise"
    lessons = [
        _make_lesson(desc, "sales"),
        _make_lesson(desc, "engineering"),
        _make_lesson(desc, "marketing"),
    ]
    candidates = detect_cross_domain_candidates(lessons, min_domains=3)
    assert len(candidates) == 1
    c = candidates[0]
    assert c["description"] == desc
    assert set(c["domains"]) == {"sales", "engineering", "marketing"}
    assert c["count"] == 3
    assert isinstance(c["avg_confidence"], float)


def test_detect_cross_domain_candidates_below_threshold():
    from gradata.enhancements.meta_rules import detect_cross_domain_candidates
    desc = "Be specific"
    lessons = [_make_lesson(desc, "sales"), _make_lesson(desc, "engineering")]
    candidates = detect_cross_domain_candidates(lessons, min_domains=3)
    assert len(candidates) == 0


def test_detect_cross_domain_candidates_skips_no_domain():
    from gradata.enhancements.meta_rules import detect_cross_domain_candidates
    from gradata._types import Lesson, LessonState
    desc = "Be precise"
    lessons = [
        _make_lesson(desc, "sales"),
        _make_lesson(desc, "engineering"),
        _make_lesson(desc, "marketing"),
        Lesson(date="2024-01-01", state=LessonState.RULE, confidence=0.9,
               category="STYLE", description=desc, scope_json=""),
    ]
    candidates = detect_cross_domain_candidates(lessons, min_domains=3)
    assert len(candidates) == 1
    assert candidates[0]["count"] == 3


def test_detect_cross_domain_avg_confidence():
    from gradata.enhancements.meta_rules import detect_cross_domain_candidates
    desc = "Validate input"
    lessons = [
        _make_lesson(desc, "sales", confidence=0.9),
        _make_lesson(desc, "engineering", confidence=0.8),
        _make_lesson(desc, "marketing", confidence=0.7),
    ]
    candidates = detect_cross_domain_candidates(lessons, min_domains=3)
    assert len(candidates) == 1
    expected = round((0.9 + 0.8 + 0.7) / 3, 4)
    assert candidates[0]["avg_confidence"] == pytest.approx(expected, abs=1e-4)


def test_detect_cross_domain_same_domain_not_counted_twice():
    from gradata.enhancements.meta_rules import detect_cross_domain_candidates
    desc = "Same rule"
    lessons = [
        _make_lesson(desc, "sales"),
        _make_lesson(desc, "sales"),
        _make_lesson(desc, "engineering"),
    ]
    candidates = detect_cross_domain_candidates(lessons, min_domains=3)
    assert len(candidates) == 0


# Feature 3: suggest_scope_narrowing()

def test_suggest_scope_narrowing_wildcard_gets_narrowed():
    from gradata._scope import RuleScope
    from gradata.enhancements.self_healing import suggest_scope_narrowing
    rule_scope = RuleScope(domain="", task_type="", stakes="normal")
    misfire_context = {"domain": "engineering"}
    result = suggest_scope_narrowing(rule_scope, misfire_context)
    assert result is not None
    assert isinstance(result, RuleScope)
    assert result.domain == "engineering"


def test_suggest_scope_narrowing_specific_scope_returns_none():
    from gradata._scope import RuleScope
    from gradata.enhancements.self_healing import suggest_scope_narrowing
    rule_scope = RuleScope(domain="sales", task_type="email_draft")
    misfire_context = {"domain": "sales", "task_type": "email_draft"}
    result = suggest_scope_narrowing(rule_scope, misfire_context)
    assert result is None


def test_suggest_scope_narrowing_empty_context_returns_none():
    from gradata._scope import RuleScope
    from gradata.enhancements.self_healing import suggest_scope_narrowing
    rule_scope = RuleScope(domain="", task_type="")
    result = suggest_scope_narrowing(rule_scope, {})
    assert result is None


def test_suggest_scope_narrowing_partial_narrowing():
    from gradata._scope import RuleScope
    from gradata.enhancements.self_healing import suggest_scope_narrowing
    rule_scope = RuleScope(domain="sales", task_type="")
    misfire_context = {"domain": "engineering", "task_type": "code_review"}
    result = suggest_scope_narrowing(rule_scope, misfire_context)
    assert result is not None
    assert result.domain == "sales"
    assert result.task_type == "code_review"


def test_suggest_scope_narrowing_imports_rulescope_from_gradata_scope():
    import inspect
    from gradata.enhancements import self_healing
    source = inspect.getsource(self_healing.suggest_scope_narrowing)
    assert "from gradata._scope import RuleScope" in source
