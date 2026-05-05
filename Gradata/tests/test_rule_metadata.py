"""Tests for RuleMetadata dataclass and its integration with Lesson."""

from gradata._types import Lesson, LessonState, RuleMetadata


class TestRuleMetadataDefaults:
    def test_defaults(self):
        m = RuleMetadata()
        assert m.what == ""
        assert m.why == ""
        assert m.who == ""
        assert m.when_created == ""
        assert m.when_validated == ""
        assert m.where_scope == ""
        assert m.how_enforced == "injected"
        assert m.utility_score == 0.5
        assert m.safety_score == 0.5


class TestRuleMetadataCustom:
    def test_custom_values(self):
        m = RuleMetadata(
            what="no em dashes",
            why="user preference",
            who="oliver",
            when_created="2026-04-07",
            when_validated="2026-04-08",
            where_scope="email",
            how_enforced="injected",
            utility_score=0.8,
            safety_score=0.3,
        )
        assert m.what == "no em dashes"
        assert m.why == "user preference"
        assert m.who == "oliver"
        assert m.when_created == "2026-04-07"
        assert m.when_validated == "2026-04-08"
        assert m.where_scope == "email"
        assert m.utility_score == 0.8
        assert m.safety_score == 0.3


class TestRuleMetadataClamping:
    def test_clamp_high(self):
        m = RuleMetadata(utility_score=1.5, safety_score=2.0)
        assert m.utility_score == 1.0
        assert m.safety_score == 1.0

    def test_clamp_low(self):
        m = RuleMetadata(utility_score=-0.2, safety_score=-5.0)
        assert m.utility_score == 0.0
        assert m.safety_score == 0.0

    def test_clamp_edge(self):
        m = RuleMetadata(utility_score=0.0, safety_score=1.0)
        assert m.utility_score == 0.0
        assert m.safety_score == 1.0


class TestRuleMetadataToDict:
    def test_to_dict_all_fields(self):
        m = RuleMetadata(what="test", utility_score=0.7)
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d["what"] == "test"
        assert d["utility_score"] == 0.7
        assert d["safety_score"] == 0.5
        assert set(d.keys()) == {
            "what",
            "why",
            "who",
            "when_created",
            "when_validated",
            "where_scope",
            "how_enforced",
            "utility_score",
            "safety_score",
        }


class TestLessonMetadataField:
    def test_lesson_has_metadata(self):
        lesson = Lesson(
            date="2026-04-07",
            state=LessonState.INSTINCT,
            confidence=0.4,
            category="TEST",
            description="test lesson",
        )
        assert isinstance(lesson.metadata, RuleMetadata)
        assert lesson.metadata.utility_score == 0.5

    def test_lesson_metadata_independent(self):
        """Each Lesson gets its own RuleMetadata (not shared)."""
        a = Lesson(
            date="2026-01-01",
            state=LessonState.INSTINCT,
            confidence=0.4,
            category="A",
            description="a",
        )
        b = Lesson(
            date="2026-01-01",
            state=LessonState.INSTINCT,
            confidence=0.4,
            category="B",
            description="b",
        )
        a.metadata.utility_score = 0.9
        assert b.metadata.utility_score == 0.5
        assert a.metadata is not b.metadata
