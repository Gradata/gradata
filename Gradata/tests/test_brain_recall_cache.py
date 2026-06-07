from __future__ import annotations

from collections.abc import Callable

from gradata import Brain
from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons


def _seed_rule(brain: Brain) -> None:
    lessons = [
        Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="PROCESS",
            description="Verify cache-sensitive tasks before responding",
        )
    ]
    (brain.dir / "lessons.md").write_text(format_lessons(lessons), encoding="utf-8")


def _count_rule_applications(monkeypatch) -> Callable[[], int]:
    calls = 0

    def fake_apply_rules_with_tree(*args, **kwargs):
        nonlocal calls
        calls += 1
        from gradata.rules.rule_engine import apply_rules

        return apply_rules(args[0], args[1], max_rules=kwargs["max_rules"], bus=None)

    monkeypatch.setattr(
        "gradata.rules.rule_engine.apply_rules_with_tree", fake_apply_rules_with_tree
    )
    return lambda: calls


def test_recall_cache_reuses_same_task_without_recomputing(
    fresh_brain: Brain, monkeypatch
) -> None:
    _seed_rule(fresh_brain)
    calls = _count_rule_applications(monkeypatch)

    first = fresh_brain.recall("write a launch checklist")
    second = fresh_brain.recall("write a launch checklist")

    assert first == second
    assert calls() == 1


def test_recall_cache_key_includes_task_hash(fresh_brain: Brain, monkeypatch) -> None:
    _seed_rule(fresh_brain)
    calls = _count_rule_applications(monkeypatch)

    fresh_brain.recall("write a launch checklist")
    fresh_brain.recall("write a sales email")

    assert calls() == 2


def test_recall_cache_key_includes_scope_and_options(
    fresh_brain: Brain, monkeypatch
) -> None:
    _seed_rule(fresh_brain)
    calls = _count_rule_applications(monkeypatch)

    fresh_brain.recall("write copy", context={"domain": "marketing"}, max_rules=1)
    fresh_brain.recall("write copy", context={"domain": "support"}, max_rules=1)
    fresh_brain.recall("write copy", context={"domain": "support"}, max_rules=2)
    fresh_brain.recall("write copy", context={"domain": "support"}, max_rules=2)

    assert calls() == 3


def test_invalidate_cache_forces_next_recall_miss(fresh_brain: Brain, monkeypatch) -> None:
    _seed_rule(fresh_brain)
    calls = _count_rule_applications(monkeypatch)

    fresh_brain.recall("write a launch checklist")
    fresh_brain.invalidate_cache()
    fresh_brain.recall("write a launch checklist")

    assert calls() == 2


def test_cache_ttl_zero_disables_recall_cache(fresh_brain: Brain, monkeypatch) -> None:
    brain = Brain(fresh_brain.dir, cache_ttl=0)
    _seed_rule(brain)
    calls = _count_rule_applications(monkeypatch)

    brain.recall("write a launch checklist")
    brain.recall("write a launch checklist")

    assert calls() == 2


def test_cache_expires_after_configured_ttl(fresh_brain: Brain, monkeypatch) -> None:
    brain = Brain(fresh_brain.dir, cache_ttl=5)
    _seed_rule(brain)
    calls = _count_rule_applications(monkeypatch)
    now = 100.0
    monkeypatch.setattr("gradata.brain.time.monotonic", lambda: now)

    brain.recall("write a launch checklist")
    brain.recall("write a launch checklist")
    now = 106.0
    brain.recall("write a launch checklist")

    assert calls() == 2


def test_recall_cache_evicts_least_recently_used_entry(
    fresh_brain: Brain, monkeypatch
) -> None:
    _seed_rule(fresh_brain)
    fresh_brain._recall_cache_size = 2
    calls = _count_rule_applications(monkeypatch)

    fresh_brain.recall("task one")
    fresh_brain.recall("task two")
    fresh_brain.recall("task one")
    fresh_brain.recall("task three")
    fresh_brain.recall("task two")

    assert calls() == 4
