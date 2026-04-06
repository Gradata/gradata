"""Tests for rule domain scoping — per-domain misfire tracking and auto-disable."""
from gradata._types import Lesson, LessonState


def test_lesson_has_domain_scores_field():
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
    )
    assert hasattr(lesson, "domain_scores")
    assert lesson.domain_scores == {}


def test_domain_scores_round_trip():
    from gradata.enhancements.self_improvement import parse_lessons, format_lessons
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        fire_count=10,
        domain_scores={"CODE": {"fires": 8, "misfires": 1}, "DRAFTING": {"fires": 2, "misfires": 0}},
    )
    text = format_lessons([lesson])
    parsed = parse_lessons(text)
    assert len(parsed) == 1
    assert parsed[0].domain_scores == {"CODE": {"fires": 8, "misfires": 1}, "DRAFTING": {"fires": 2, "misfires": 0}}


from gradata.rules.rule_engine import is_rule_disabled_for_domain


def test_rule_disabled_high_misfire_rate():
    """Rule disabled when misfire rate >30% in a domain with 3+ fires."""
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 10, "misfires": 4}},
    )
    assert is_rule_disabled_for_domain(lesson, "CODE") is True


def test_rule_not_disabled_low_misfire_rate():
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 10, "misfires": 2}},
    )
    assert is_rule_disabled_for_domain(lesson, "CODE") is False


def test_rule_not_disabled_insufficient_data():
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 2, "misfires": 2}},
    )
    assert is_rule_disabled_for_domain(lesson, "CODE") is False


def test_rule_disabled_one_domain_active_another():
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={
            "CODE": {"fires": 10, "misfires": 5},
            "DRAFTING": {"fires": 20, "misfires": 1},
        },
    )
    assert is_rule_disabled_for_domain(lesson, "CODE") is True
    assert is_rule_disabled_for_domain(lesson, "DRAFTING") is False


def test_rule_not_disabled_unknown_domain():
    lesson = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 10, "misfires": 5}},
    )
    assert is_rule_disabled_for_domain(lesson, "EMAIL") is False


from gradata.rules.rule_engine import apply_rules
from gradata._scope import RuleScope


def test_apply_rules_filters_domain_disabled():
    """apply_rules excludes rules disabled for the current domain."""
    good_rule = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"CODE": {"fires": 20, "misfires": 1}},
    )
    bad_rule = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="TONE",
        description="Be concise",
        domain_scores={"CODE": {"fires": 10, "misfires": 5}},
    )
    scope = RuleScope(domain="CODE")
    results = apply_rules([good_rule, bad_rule], scope)
    descriptions = [r.lesson.description for r in results]
    assert "Use active voice" in descriptions
    assert "Be concise" not in descriptions


def test_rule_scoped_out_event_emitted():
    """rule_scoped_out event fires when a rule is filtered by domain."""
    from gradata.events_bus import EventBus

    bus = EventBus()
    events_received = []
    bus.on("rule_scoped_out", lambda payload: events_received.append(payload))

    bad_rule = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="TONE",
        description="Be concise in all output",
        domain_scores={"CODE": {"fires": 10, "misfires": 5}},
    )
    scope = RuleScope(domain="CODE")
    apply_rules([bad_rule], scope, bus=bus)

    assert len(events_received) == 1
    assert events_received[0]["domain"] == "CODE"
    assert events_received[0]["lesson_category"] == "TONE"


def test_attribute_domain_fires_increments():
    """_attribute_domain_fires increments fires for correction category."""
    from gradata._core import _attribute_domain_fires
    from unittest.mock import MagicMock

    brain = MagicMock()
    rule = Lesson(
        date="2026-04-06", state=LessonState.RULE,
        confidence=0.95, category="DRAFTING",
        description="Use active voice",
        domain_scores={"DRAFTING": {"fires": 5, "misfires": 0}},
    )
    brain._fired_rules = [rule]

    _attribute_domain_fires(brain, "DRAFTING", "some correction")

    assert rule.domain_scores["DRAFTING"]["fires"] == 6
