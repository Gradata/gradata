"""Tests for scripts/migrate_legacy_scopes.py.

Covers the council-mandated migration path for legacy lessons that relied
on the removed category-as-domain fallback.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "scripts" / "migrate_legacy_scopes.py"


def _load_migrate_module():
    """Dynamically load the script as a module (scripts/ isn't a package)."""
    spec = importlib.util.spec_from_file_location("_migrate_legacy_scopes_under_test", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def migrate_mod():
    return _load_migrate_module()


@pytest.fixture()
def brain_with_mixed_lessons(brain_dir):
    """Create a brain dir with 5 lessons: 2 migratable, 1 ambiguous,
    1 already-scoped, 1 with unknown category."""
    from gradata._types import Lesson, LessonState
    from gradata.enhancements.self_improvement import format_lessons

    lessons = [
        Lesson(
            date="2026-04-14",
            state=LessonState.RULE,
            confidence=0.95,
            category="CODE",
            description="Run tests first",
            scope_json="",
        ),
        Lesson(
            date="2026-04-14",
            state=LessonState.RULE,
            confidence=0.95,
            category="EMAIL",
            description="Hyperlink the Calendly",
            scope_json="",
        ),
        Lesson(
            date="2026-04-14",
            state=LessonState.RULE,
            confidence=0.92,
            category="GENERAL",
            description="Verify before shipping",
            scope_json="",
        ),
        Lesson(
            date="2026-04-14",
            state=LessonState.RULE,
            confidence=0.93,
            category="CODE",
            description="Already explicitly scoped",
            scope_json=json.dumps({"domain": "code"}),
        ),
        Lesson(
            date="2026-04-14",
            state=LessonState.RULE,
            confidence=0.91,
            category="RANDOM",  # not present in the domains list below
            description="Weird legacy lesson",
            scope_json="",
        ),
    ]

    (brain_dir / "lessons.md").write_text(format_lessons(lessons), encoding="utf-8")
    return brain_dir


def test_plan_migration_counts(migrate_mod, brain_with_mixed_lessons):
    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = brain_with_mixed_lessons / "lessons.md"
    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))

    # Explicit domain set (simulating a future domains.yaml)
    domains = {"code", "email"}
    _new_lessons, result = migrate_mod.plan_migration(lessons, domains)

    assert result.migrated == 2  # CODE + EMAIL -> scope_json.domain set
    assert result.skipped == 1  # the already-scoped CODE lesson
    assert result.flagged == 2  # GENERAL + RANDOM


def test_plan_migration_sets_scope_json(migrate_mod, brain_with_mixed_lessons):
    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = brain_with_mixed_lessons / "lessons.md"
    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    new_lessons, _ = migrate_mod.plan_migration(lessons, {"code", "email"})

    # The first two (CODE, EMAIL) should now carry domain
    first = json.loads(new_lessons[0].scope_json)
    second = json.loads(new_lessons[1].scope_json)
    assert first["domain"] == "code"
    assert second["domain"] == "email"

    # The already-scoped one is unchanged
    fourth = json.loads(new_lessons[3].scope_json)
    assert fourth["domain"] == "code"

    # The flagged ones keep empty scope_json
    assert new_lessons[2].scope_json in ("", None)
    assert new_lessons[4].scope_json in ("", None)


def test_cli_dry_run_does_not_write(migrate_mod, brain_with_mixed_lessons, caplog, monkeypatch):
    lessons_path = brain_with_mixed_lessons / "lessons.md"
    before = lessons_path.read_text(encoding="utf-8")

    rc = migrate_mod.run_cli(["--brain", str(brain_with_mixed_lessons)])
    assert rc == 0

    after = lessons_path.read_text(encoding="utf-8")
    assert after == before, "dry-run must not modify lessons.md"


def test_cli_apply_writes_scope_json(migrate_mod, brain_with_mixed_lessons):
    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = brain_with_mixed_lessons / "lessons.md"
    rc = migrate_mod.run_cli(["--brain", str(brain_with_mixed_lessons), "--apply"])
    assert rc == 0

    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    scoped_domains = {json.loads(l.scope_json).get("domain") for l in lessons if l.scope_json}
    assert "code" in scoped_domains
    assert "email" in scoped_domains


def test_ambiguous_category_is_flagged_not_migrated(migrate_mod):
    from dataclasses import replace

    from gradata._types import Lesson, LessonState

    lesson = Lesson(
        date="2026-04-14",
        state=LessonState.RULE,
        confidence=0.9,
        category="GENERAL",
        description="vague",
        scope_json="",
    )
    new, result = migrate_mod.plan_migration([lesson], {"code", "email", "general"})
    # "general" is an ambiguous sentinel even if present in domains list
    assert result.flagged == 1
    assert result.migrated == 0
    # unchanged
    assert new[0] == replace(lesson)
