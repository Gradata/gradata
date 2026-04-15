"""Phase 5 rule-to-hook auto-promotion tests.

Covers the end-to-end loop:
  - classify_rule finds a deterministic template for a high-confidence rule
  - promote() installs a hook file on disk
  - the injection hooks (inject_brain_rules, jit_inject) skip hook-enforced
    rules so context isn't wasted once the hook is live
  - demote() removes the file; the round-trip restores text injection

Shells out to Node for hook self-test, so skip when Node is absent.
"""
from __future__ import annotations

import shutil

import pytest

from gradata._types import Lesson, LessonState, RuleMetadata
from gradata.enhancements.rule_to_hook import (
    GenerationResult,
    classify_rule,
    demote,
    promote,
)
from gradata.enhancements.self_improvement import (
    format_lessons,
    is_hook_enforced,
    parse_lessons,
)

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not installed — rule-to-hook promotion tests shell out to Node",
)


# ---------------------------------------------------------------------------
# Classification + promote()
# ---------------------------------------------------------------------------


def test_promote_installs_hook_for_deterministic_rule(tmp_path, monkeypatch):
    """A deterministic RULE at conf>=0.99 installs a .js file."""
    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    result = promote("Never use em dashes in prose", 0.99)

    assert isinstance(result, GenerationResult)
    assert result.installed, result.reason
    assert result.hook_path is not None
    assert result.hook_path.exists()
    assert result.hook_path.parent == hook_dir


def test_promote_skips_non_deterministic_rule(tmp_path, monkeypatch):
    """Rules requiring LLM judgment must NOT install a hook."""
    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    result = promote("Always write empathetic replies", 0.99)

    assert not result.installed
    assert "llm" in result.reason.lower() or "judgment" in result.reason.lower()
    assert not hook_dir.exists() or not list(hook_dir.glob("*.js"))


def test_classify_rule_handles_confidence_boundaries():
    """classify_rule rejects out-of-range confidence."""
    with pytest.raises(ValueError):
        classify_rule("Never use em dashes", 1.5)
    with pytest.raises(ValueError):
        classify_rule("Never use em dashes", -0.1)


# ---------------------------------------------------------------------------
# demote() inverse
# ---------------------------------------------------------------------------


def test_demote_removes_installed_hook(tmp_path, monkeypatch):
    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    promoted = promote("Never use em dashes in prose", 0.99)
    assert promoted.installed
    slug = promoted.hook_path.stem

    result = demote(slug)

    assert result.installed  # in GenerationResult, installed==True means "removed"
    assert not (hook_dir / f"{slug}.js").exists()


def test_demote_missing_slug_returns_not_found(tmp_path, monkeypatch):
    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    result = demote("no-such-slug")

    assert not result.installed
    assert "no hook file" in result.reason.lower()


# ---------------------------------------------------------------------------
# Lesson metadata round-trip (is_hook_enforced)
# ---------------------------------------------------------------------------


def _make_hooked_lesson(description: str) -> Lesson:
    md = RuleMetadata(how_enforced="hooked")
    return Lesson(
        date="2026-04-14",
        state=LessonState.RULE,
        confidence=0.99,
        category="FORMATTING",
        description=description,
        fire_count=5,
        metadata=md,
    )


def _make_plain_lesson(description: str) -> Lesson:
    return Lesson(
        date="2026-04-14",
        state=LessonState.RULE,
        confidence=0.95,
        category="FORMATTING",
        description=description,
        fire_count=5,
    )


def test_is_hook_enforced_reads_structured_metadata():
    lesson = _make_hooked_lesson("Never use em dashes")
    assert is_hook_enforced(lesson)


def test_is_hook_enforced_legacy_prefix_fallback():
    """Old lessons.md files use a '[hooked]' description prefix."""
    lesson = _make_plain_lesson("[hooked] Never use em dashes")
    assert is_hook_enforced(lesson)


def test_is_hook_enforced_false_for_plain_rule():
    lesson = _make_plain_lesson("Never use em dashes")
    assert not is_hook_enforced(lesson)


def test_metadata_round_trips_through_format_parse():
    """Round-trip: a lesson flagged as hooked survives format_lessons -> parse_lessons."""
    original = _make_hooked_lesson("Never use em dashes in prose")
    text = format_lessons([original])
    parsed = parse_lessons(text)
    assert len(parsed) == 1
    assert is_hook_enforced(parsed[0])


# ---------------------------------------------------------------------------
# Injection pipelines skip hook-enforced rules
# ---------------------------------------------------------------------------


def test_inject_brain_rules_skips_hook_enforced(tmp_path, monkeypatch):
    """SessionStart hook must not re-inject rules an installed hook already enforces."""
    from gradata.hooks import inject_brain_rules as ibr

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    lessons_path = brain_dir / "lessons.md"

    hooked = _make_hooked_lesson("Never use em dashes in prose")
    plain = _make_plain_lesson("Always hyperlink the booking CTA")
    lessons_path.write_text(format_lessons([hooked, plain]), encoding="utf-8")

    monkeypatch.setattr(ibr, "resolve_brain_dir", lambda: brain_dir)

    out = ibr.main({"session_type": "general"})

    assert out is not None
    # The hooked rule is excluded; the plain rule is present.
    assert "em dashes" not in out["result"]
    assert "hyperlink" in out["result"]


def test_inject_brain_rules_emits_none_when_all_rules_hooked(tmp_path, monkeypatch):
    """When every eligible rule is already enforced by a hook, no injection block fires."""
    from gradata.hooks import inject_brain_rules as ibr

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    lessons_path = brain_dir / "lessons.md"

    hooked_a = _make_hooked_lesson("Never use em dashes in prose")
    hooked_b = _make_hooked_lesson("Never force push to main")
    lessons_path.write_text(format_lessons([hooked_a, hooked_b]), encoding="utf-8")

    monkeypatch.setattr(ibr, "resolve_brain_dir", lambda: brain_dir)

    out = ibr.main({"session_type": "general"})

    # All rules hooked => nothing to inject
    assert out is None


def test_jit_inject_skips_hook_enforced(tmp_path, monkeypatch):
    """Per-tool JIT injection must also skip hook-enforced rules."""
    from gradata.hooks import jit_inject as jit

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    lessons_path = brain_dir / "lessons.md"

    hooked = _make_hooked_lesson("Never use em dashes in prose em dash dashes")
    plain = _make_plain_lesson("Always hyperlink the booking CTA prose em dash dashes")
    lessons_path.write_text(format_lessons([hooked, plain]), encoding="utf-8")

    monkeypatch.setenv("GRADATA_JIT_ENABLED", "1")
    monkeypatch.setattr(jit, "resolve_brain_dir", lambda: brain_dir)

    # Payload mirrors real UserPromptSubmit hook data.
    out = jit.main({
        "prompt": "Help me draft an email about em dashes and dashes in prose",
    })

    if out is None:
        # No rules ranked highly enough for JIT — still valid; the assertion
        # we care about (no em-dash rule injected) is trivially true.
        return
    assert "em dashes" not in out["result"]


# ---------------------------------------------------------------------------
# Graduation round-trip (promote at graduation time)
# ---------------------------------------------------------------------------


def test_graduation_auto_promotes_deterministic_rule(tmp_path, monkeypatch):
    """graduate() classifies a newly-promoted RULE and installs a hook."""
    from gradata.enhancements.self_improvement import graduate

    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    # A PATTERN that should graduate to RULE on this pass.
    l = Lesson(
        date="2026-04-14",
        state=LessonState.PATTERN,
        confidence=0.92,
        category="FORMATTING",
        description="Never use em dashes in prose",
        fire_count=5,
    )
    _active, graduated = graduate([l])

    # Post-graduation the lesson is in the graduated bucket as a RULE
    # and its metadata has how_enforced == "hooked".
    promoted = [x for x in graduated if x.state == LessonState.RULE]
    assert promoted, "expected the PATTERN to promote to RULE"
    assert is_hook_enforced(promoted[0])
    # And the .js hook file landed on disk.
    assert list(hook_dir.glob("*.js")), "expected a generated hook file"


def test_graduation_does_not_hook_non_deterministic_rule(tmp_path, monkeypatch):
    """A graduating RULE that isn't deterministic stays as soft injection only."""
    from gradata.enhancements.self_improvement import graduate

    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    l = Lesson(
        date="2026-04-14",
        state=LessonState.PATTERN,
        confidence=0.92,
        category="TONE",
        description="Write warm, empathetic replies to frustrated users",
        fire_count=5,
    )
    _active, graduated = graduate([l])

    promoted = [x for x in graduated if x.state == LessonState.RULE]
    if not promoted:
        # Non-deterministic rules may be blocked by adversarial gates; that's
        # fine for this test. We only care that *if* it promotes, it's not
        # marked as hooked.
        return
    assert not is_hook_enforced(promoted[0])
    assert not list(hook_dir.glob("*.js"))


# ---------------------------------------------------------------------------
# Full loop: promote -> inject-skips -> demote -> inject-resumes
# ---------------------------------------------------------------------------


def test_end_to_end_promote_inject_demote_roundtrip(tmp_path, monkeypatch):
    from gradata.hooks import inject_brain_rules as ibr

    hook_dir = tmp_path / "pre-tool" / "generated"
    monkeypatch.setenv("GRADATA_HOOK_ROOT", str(hook_dir))

    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    lessons_path = brain_dir / "lessons.md"
    monkeypatch.setattr(ibr, "resolve_brain_dir", lambda: brain_dir)

    # 1) Seed a plain RULE, verify it injects.
    rule = _make_plain_lesson("Never use em dashes in prose")
    lessons_path.write_text(format_lessons([rule]), encoding="utf-8")
    out_before = ibr.main({"session_type": "general"})
    assert out_before is not None
    assert "em dashes" in out_before["result"]

    # 2) Promote: install a hook and flip the metadata.
    promoted = promote(rule.description, 0.99)
    assert promoted.installed
    rule.metadata = RuleMetadata(how_enforced="hooked")
    lessons_path.write_text(format_lessons([rule]), encoding="utf-8")

    out_after = ibr.main({"session_type": "general"})
    # Only rule was hooked => no injection at all.
    assert out_after is None

    # 3) Demote: remove hook + flip metadata back.
    slug = promoted.hook_path.stem
    removed = demote(slug)
    assert removed.installed

    rule.metadata = RuleMetadata(how_enforced="injected")
    lessons_path.write_text(format_lessons([rule]), encoding="utf-8")

    out_restored = ibr.main({"session_type": "general"})
    assert out_restored is not None
    assert "em dashes" in out_restored["result"]
