"""
TDD tests for:
  Feature 1: Brain.scope() method
  Feature 2: detect_cross_domain_candidates() in meta_rules
  Feature 3: suggest_scope_narrowing() in self_healing
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from gradata import Brain
from gradata._scope import RuleScope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_brain(tmp_path: Path) -> Brain:
    brain_dir = tmp_path / "brain"
    os.environ["BRAIN_DIR"] = str(brain_dir)
    brain = Brain.init(
        brain_dir,
        name="ScopedTestBrain",
        domain="Testing",
        embedding="local",
        interactive=False,
    )
    import gradata._paths as _p
    import gradata._events as _ev
    import gradata._brain_manifest as _bm
    _ev.BRAIN_DIR = _p.BRAIN_DIR
    _ev.EVENTS_JSONL = _p.EVENTS_JSONL
    _ev.DB_PATH = _p.DB_PATH
    return brain


# ---------------------------------------------------------------------------
# Feature 1: Brain.scope()
# ---------------------------------------------------------------------------

class TestBrainScope:
    def test_scope_returns_str(self, tmp_path):
        brain = _init_brain(tmp_path)
        result = brain.scope(domain="sales")
        assert isinstance(result, str)

    def test_scope_empty_args_returns_str(self, tmp_path):
        brain = _init_brain(tmp_path)
        result = brain.scope()
        assert isinstance(result, str)

    def test_scope_with_task_type(self, tmp_path):
        brain = _init_brain(tmp_path)
        result = brain.scope(domain="engineering", task_type="code_review")
        assert isinstance(result, str)

    def test_scope_with_agent_type(self, tmp_path):
        brain = _init_brain(tmp_path)
        result = brain.scope(domain="sales", agent_type="researcher")
        assert isinstance(result, str)

    def test_scope_with_max_rules(self, tmp_path):
        brain = _init_brain(tmp_path)
        result = brain.scope(domain="sales", max_rules=5)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Feature 2: detect_cross_domain_candidates()
# ---------------------------------------------------------------------------

class TestDetectCrossDomainCandidates:
    def _make_lesson(self, description: str, domain: str, confidence: float = 0.85):
        """Build a minimal lesson-like dict."""
        from gradata._types import Lesson, LessonState
        from datetime import date
        return Lesson(
            category="STYLE",
            description=description,
            state=LessonState.RULE,
            confidence=confidence,
            fire_count=5,
            date=date.today().isoformat(),
            scope_json=f'{{"domain": "{domain}"}}',
        )

    def test_returns_candidate_for_3_domains(self):
        from gradata.enhancements.meta_rules import detect_cross_domain_candidates

        shared_desc = "Always confirm before deleting"
        lessons = [
            self._make_lesson(shared_desc, "sales"),
            self._make_lesson(shared_desc, "engineering"),
            self._make_lesson(shared_desc, "marketing"),
        ]
        candidates = detect_cross_domain_candidates(lessons)
        assert len(candidates) == 1
        cand = candidates[0]
        assert cand["description"] == shared_desc
        assert set(cand["domains"]) == {"sales", "engineering", "marketing"}
        assert cand["count"] == 3
        assert "avg_confidence" in cand

    def test_no_candidate_for_2_domains(self):
        from gradata.enhancements.meta_rules import detect_cross_domain_candidates

        shared_desc = "Use concise language"
        lessons = [
            self._make_lesson(shared_desc, "sales"),
            self._make_lesson(shared_desc, "engineering"),
        ]
        candidates = detect_cross_domain_candidates(lessons)
        assert candidates == []

    def test_ignores_no_domain_lessons(self):
        from gradata.enhancements.meta_rules import detect_cross_domain_candidates
        from gradata._types import Lesson, LessonState
        from datetime import date

        shared_desc = "Be explicit about assumptions"
        # 2 with domain, 1 without
        lessons = [
            self._make_lesson(shared_desc, "sales"),
            self._make_lesson(shared_desc, "engineering"),
            Lesson(
                category="STYLE",
                description=shared_desc,
                state=LessonState.RULE,
                confidence=0.85,
                fire_count=3,
                date=date.today().isoformat(),
                scope_json="{}",  # no domain
            ),
        ]
        candidates = detect_cross_domain_candidates(lessons)
        # Only 2 distinct domains → not enough
        assert candidates == []

    def test_multiple_descriptions(self):
        from gradata.enhancements.meta_rules import detect_cross_domain_candidates

        universal_desc = "Validate inputs"
        other_desc = "Use short sentences"
        lessons = [
            self._make_lesson(universal_desc, "sales"),
            self._make_lesson(universal_desc, "engineering"),
            self._make_lesson(universal_desc, "support"),
            self._make_lesson(other_desc, "sales"),
            self._make_lesson(other_desc, "engineering"),  # only 2 domains
        ]
        candidates = detect_cross_domain_candidates(lessons)
        assert len(candidates) == 1
        assert candidates[0]["description"] == universal_desc

    def test_avg_confidence_correct(self):
        from gradata.enhancements.meta_rules import detect_cross_domain_candidates

        desc = "Check edge cases"
        lessons = [
            self._make_lesson(desc, "sales", confidence=0.90),
            self._make_lesson(desc, "engineering", confidence=0.80),
            self._make_lesson(desc, "marketing", confidence=0.70),
        ]
        candidates = detect_cross_domain_candidates(lessons)
        assert len(candidates) == 1
        assert abs(candidates[0]["avg_confidence"] - 0.80) < 0.01


# ---------------------------------------------------------------------------
# Feature 3: suggest_scope_narrowing()
# ---------------------------------------------------------------------------

class TestSuggestScopeNarrowing:
    def test_wildcard_domain_narrows_to_context(self):
        from gradata.enhancements.self_healing import suggest_scope_narrowing

        rule_scope = RuleScope()  # all wildcards
        misfire_context = {"domain": "engineering", "task_type": "code_review"}
        result = suggest_scope_narrowing(rule_scope, misfire_context)

        assert result is not None
        assert isinstance(result, RuleScope)
        # Should have narrowed domain to "engineering"
        assert result.domain == "engineering"

    def test_already_specific_returns_none(self):
        from gradata.enhancements.self_healing import suggest_scope_narrowing

        rule_scope = RuleScope(domain="engineering", task_type="code_review")
        misfire_context = {"domain": "engineering", "task_type": "code_review"}
        result = suggest_scope_narrowing(rule_scope, misfire_context)

        assert result is None

    def test_partial_wildcard_narrows_remaining(self):
        from gradata.enhancements.self_healing import suggest_scope_narrowing

        # domain set but task_type is wildcard
        rule_scope = RuleScope(domain="sales")
        misfire_context = {"domain": "sales", "task_type": "email_draft"}
        result = suggest_scope_narrowing(rule_scope, misfire_context)

        assert result is not None
        assert result.domain == "sales"
        assert result.task_type == "email_draft"

    def test_context_without_scope_fields_returns_none(self):
        from gradata.enhancements.self_healing import suggest_scope_narrowing

        rule_scope = RuleScope(domain="sales", task_type="email_draft")
        misfire_context = {"irrelevant_key": "value"}
        result = suggest_scope_narrowing(rule_scope, misfire_context)

        assert result is None

    def test_agent_type_narrowing(self):
        from gradata.enhancements.self_healing import suggest_scope_narrowing

        rule_scope = RuleScope()  # all wildcards
        misfire_context = {"agent_type": "reviewer"}
        result = suggest_scope_narrowing(rule_scope, misfire_context)

        assert result is not None
        assert result.agent_type == "reviewer"
