"""Tests for Phase 2 — Scoped Brains.

Covers:
    - brain.scope(domain) returns a ScopedBrain
    - ScopedBrain.rules() filters parent rules by domain
    - ScopedBrain.lessons() filters parsed Lessons by domain
    - ScopedBrain.inject() emits only scoped rule text
    - Round-trip: correct(scope="domain", applies_to="code:X") then scope("code") surfaces the rule
    - Sub-agent scope inheritance via the agent_precontext hook
    - RuleContext.query(domain=...) filter
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_lessons(lessons_path: Path, entries: list[dict]) -> None:
    """Write a simple lessons.md with the given entries.

    Each entry: {category, description, state, confidence, scope_json?}
    """
    from gradata._types import Lesson, LessonState
    from gradata.enhancements.self_improvement import format_lessons

    lessons = []
    for e in entries:
        lessons.append(
            Lesson(
                date="2026-04-14",
                state=LessonState[e.get("state", "RULE")],
                confidence=float(e.get("confidence", 0.95)),
                category=e["category"],
                description=e["description"],
                scope_json=e.get("scope_json", ""),
            )
        )
    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def test_scope_returns_scoped_brain(tmp_path):
    from gradata._scoped_brain import ScopedBrain
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    scoped = brain.scope("code")
    assert isinstance(scoped, ScopedBrain)
    assert scoped.domain == "code"
    assert scoped.parent is brain


def test_scope_empty_domain_rejected(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    with pytest.raises(ValueError):
        brain.scope("")
    with pytest.raises(ValueError):
        brain.scope("   ")


def test_scope_is_public_export():
    import gradata

    assert hasattr(gradata, "ScopedBrain")


# ---------------------------------------------------------------------------
# Lesson / rule filtering
# ---------------------------------------------------------------------------


def test_lessons_filtered_by_scope_domain(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "STYLE",
                "description": "Use four-space indents",
                "scope_json": json.dumps({"domain": "code"}),
            },
            {
                "category": "TONE",
                "description": "Stay casual with prospects",
                "scope_json": json.dumps({"domain": "sales"}),
            },
            {
                "category": "GENERAL",
                "description": "Verify before shipping",
                "scope_json": "",
            },
        ],
    )

    code_brain = brain.scope("code")
    scoped = code_brain.lessons()
    descs = [l.description for l in scoped]
    assert "Use four-space indents" in descs
    assert "Stay casual with prospects" not in descs
    assert "Verify before shipping" not in descs


def test_lessons_filtered_by_applies_to_prefix(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "STYLE",
                "description": "Refactor into pure functions",
                "scope_json": json.dumps({"applies_to": "code:refactor"}),
            },
            {
                "category": "STYLE",
                "description": "Tighten the subject line",
                "scope_json": json.dumps({"applies_to": "email:cold"}),
            },
        ],
    )

    code_scoped = brain.scope("code").lessons()
    assert len(code_scoped) == 1
    assert "Refactor" in code_scoped[0].description


def test_legacy_category_only_lessons_excluded(tmp_path):
    """Council verdict 4/4 STRICT: category-as-domain fallback removed.

    Legacy lessons with no scope_json (category-only) MUST NOT surface
    under a scoped view. Users migrate them via
    ``scripts/migrate_legacy_scopes.py``.
    """
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {"category": "CODE", "description": "Run tests first", "scope_json": ""},
            {"category": "EMAIL", "description": "Hyperlink Calendly", "scope_json": ""},
        ],
    )

    code_scoped = brain.scope("code").lessons()
    assert code_scoped == []


def test_migrated_lesson_surfaces_after_scope_json_set(tmp_path):
    """Once scope_json.domain is populated (e.g. by migrate_legacy_scopes),
    the lesson surfaces under the scoped view."""
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "CODE",
                "description": "Run tests first",
                "scope_json": json.dumps({"domain": "code"}),
            },
            {"category": "EMAIL", "description": "Hyperlink Calendly", "scope_json": ""},
        ],
    )

    code_scoped = brain.scope("code").lessons()
    assert len(code_scoped) == 1
    assert code_scoped[0].description == "Run tests first"


def test_inject_returns_only_scoped_rules(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "STYLE",
                "description": "Use type hints",
                "scope_json": json.dumps({"domain": "code"}),
            },
            {
                "category": "TONE",
                "description": "Warm opening",
                "scope_json": json.dumps({"domain": "sales"}),
            },
        ],
    )

    text = brain.scope("code").inject("refactor parser")
    assert "Use type hints" in text
    assert "Warm opening" not in text


def test_inject_empty_when_no_matching_rules(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "TONE",
                "description": "Warm opening",
                "scope_json": json.dumps({"domain": "sales"}),
            },
        ],
    )

    text = brain.scope("code").inject("refactor parser")
    assert text == ""


# ---------------------------------------------------------------------------
# Round-trip with correct()
# ---------------------------------------------------------------------------


def test_correct_then_scope_round_trip(tmp_path):
    """Correcting through a ScopedBrain stamps applies_to=domain so subsequent
    scope() calls surface the lesson."""
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    code_brain = brain.scope("code")

    result = code_brain.correct(
        draft="def foo(x): return x+1",
        final="def foo(x: int) -> int:\n    return x + 1",
        category="STYLE",
    )

    # The parent brain records the event with applies_to="code" and scope="domain"
    assert isinstance(result, dict)

    # Pull CORRECTION events from the parent and verify applies_to propagated
    events = brain.query_events(event_type="CORRECTION") if hasattr(brain, "query_events") else []
    tagged = [e for e in events if (e.get("data") or {}).get("applies_to") == "code"]
    assert tagged, "expected at least one CORRECTION event tagged applies_to=code"


def test_scoped_correct_preserves_explicit_applies_to(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    code_brain = brain.scope("code")

    code_brain.correct(
        draft="x=1",
        final="x = 1",
        category="STYLE",
        applies_to="code:formatting",
    )

    events = brain.query_events(event_type="CORRECTION") if hasattr(brain, "query_events") else []
    targeted = [e for e in events if (e.get("data") or {}).get("applies_to") == "code:formatting"]
    assert targeted, "explicit applies_to must not be overwritten"


# ---------------------------------------------------------------------------
# Nested scoping and delegation
# ---------------------------------------------------------------------------


def test_nested_scope_is_flat_not_intersected(tmp_path):
    """Nested scoping rebinds to the top-level parent rather than intersecting."""
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    first = brain.scope("code")
    second = first.scope("sales")
    assert second.domain == "sales"
    assert second.parent is brain  # not first


def test_scoped_brain_delegates_attrs(tmp_path):
    from gradata.brain import Brain

    brain = Brain.init(str(tmp_path))
    scoped = brain.scope("code")
    # Arbitrary parent attribute should be reachable
    assert scoped.dir == brain.dir
    assert scoped.db_path == brain.db_path


# ---------------------------------------------------------------------------
# RuleContext domain filter
# ---------------------------------------------------------------------------


def test_rule_context_domain_filter():
    from gradata.rules.rule_context import GraduatedRule, RuleContext

    ctx = RuleContext()
    ctx.publish(
        GraduatedRule(
            rule_id="r1",
            category="STYLE",
            principle="type hints",
            confidence=0.95,
            scope={"domain": "code"},
        )
    )
    ctx.publish(
        GraduatedRule(
            rule_id="r2",
            category="TONE",
            principle="warm opener",
            confidence=0.95,
            scope={"domain": "sales"},
        )
    )
    ctx.publish(
        GraduatedRule(
            rule_id="r3",
            category="STYLE",
            principle="refactor pattern",
            confidence=0.92,
            scope={"applies_to": "code:refactor"},
        )
    )

    code_rules = ctx.query(domain="code", limit=10)
    ids = {r.rule_id for r in code_rules}
    assert ids == {"r1", "r3"}

    sales_rules = ctx.query(domain="sales", limit=10)
    assert {r.rule_id for r in sales_rules} == {"r2"}


def test_rule_context_category_only_excluded():
    """STRICT: category-only rules (no scope.domain) do NOT match a domain query."""
    from gradata.rules.rule_context import GraduatedRule, RuleContext

    ctx = RuleContext()
    ctx.publish(
        GraduatedRule(
            rule_id="r1",
            category="CODE",  # category matches but scope.domain is unset
            principle="unit-test coverage",
            confidence=0.9,
        )
    )
    result = ctx.query(domain="code", limit=10)
    assert result == []


def test_rule_context_domain_explicit_scope_required():
    """After migration, scope.domain='code' on the same rule makes it match."""
    from gradata.rules.rule_context import GraduatedRule, RuleContext

    ctx = RuleContext()
    ctx.publish(
        GraduatedRule(
            rule_id="r1",
            category="CODE",
            principle="unit-test coverage",
            confidence=0.9,
            scope={"domain": "code"},
        )
    )
    result = ctx.query(domain="code", limit=10)
    assert [r.rule_id for r in result] == ["r1"]


# ---------------------------------------------------------------------------
# Sub-agent inheritance (agent_precontext hook)
# ---------------------------------------------------------------------------


def test_agent_precontext_respects_scope_domain(tmp_path, monkeypatch):
    """The sub-agent precontext hook should filter to the scoped domain when
    ``tool_input.scope_domain`` is set."""
    from gradata.brain import Brain
    from gradata.hooks import agent_precontext

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "STYLE",
                "description": "CODE-RULE: type hints",
                "scope_json": json.dumps({"domain": "code"}),
                "confidence": 0.95,
            },
            {
                "category": "TONE",
                "description": "SALES-RULE: warm opener",
                "scope_json": json.dumps({"domain": "sales"}),
                "confidence": 0.95,
            },
        ],
    )

    # Point the hook at our brain dir
    monkeypatch.setenv("BRAIN_DIR", str(brain.dir))

    data = {
        "tool_input": {
            "subagent_type": "general",
            "description": "help with a task",
            "scope_domain": "code",
        }
    }

    result = agent_precontext.main(data)
    assert result is not None
    block = result.get("result", "")
    assert "CODE-RULE" in block
    assert "SALES-RULE" not in block


def test_agent_precontext_respects_env_domain(tmp_path, monkeypatch):
    from gradata.brain import Brain
    from gradata.hooks import agent_precontext

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "STYLE",
                "description": "CODE-RULE: type hints",
                "scope_json": json.dumps({"domain": "code"}),
                "confidence": 0.95,
            },
            {
                "category": "TONE",
                "description": "SALES-RULE: warm opener",
                "scope_json": json.dumps({"domain": "sales"}),
                "confidence": 0.95,
            },
        ],
    )

    monkeypatch.setenv("BRAIN_DIR", str(brain.dir))
    monkeypatch.setenv("GRADATA_SCOPE_DOMAIN", "sales")

    data = {"tool_input": {"subagent_type": "general", "description": "help with a task"}}
    result = agent_precontext.main(data)
    assert result is not None
    block = result.get("result", "")
    assert "SALES-RULE" in block
    assert "CODE-RULE" not in block


def test_agent_precontext_env_domain_overridden_by_tool_input(tmp_path, monkeypatch):
    """tool_input.scope_domain takes priority over GRADATA_SCOPE_DOMAIN env var.

    Regression: when both an env-var domain and an explicit tool_input domain
    are present, the tool_input value must win.  This also verifies that an
    ambient GRADATA_BRAIN_DIR in the shell does not shadow an explicit
    BRAIN_DIR set by the test fixture (the env-isolation regression from the
    original scope-domain bug).
    """
    from gradata.brain import Brain
    from gradata.hooks import agent_precontext

    brain = Brain.init(str(tmp_path))
    lessons_path = brain.dir / "lessons.md"
    _write_lessons(
        lessons_path,
        [
            {
                "category": "STYLE",
                "description": "CODE-RULE: type hints",
                "scope_json": json.dumps({"domain": "code"}),
                "confidence": 0.95,
            },
            {
                "category": "TONE",
                "description": "SALES-RULE: warm opener",
                "scope_json": json.dumps({"domain": "sales"}),
                "confidence": 0.95,
            },
        ],
    )

    monkeypatch.setenv("BRAIN_DIR", str(brain.dir))
    # Env var says "sales" but tool_input says "code" — tool_input must win.
    monkeypatch.setenv("GRADATA_SCOPE_DOMAIN", "sales")

    data = {
        "tool_input": {
            "subagent_type": "general",
            "description": "help with a task",
            "scope_domain": "code",  # explicit override
        }
    }
    result = agent_precontext.main(data)
    assert result is not None
    block = result.get("result", "")
    assert "CODE-RULE" in block, (
        "tool_input.scope_domain='code' must win over env GRADATA_SCOPE_DOMAIN='sales'"
    )
    assert "SALES-RULE" not in block
