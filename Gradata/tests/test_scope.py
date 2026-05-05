"""Tests for _scope — temporal scope fields and decay."""

from gradata._scope import RuleScope, temporal_decay


class TestTemporalScope:
    def test_default_temporal_fields(self):
        scope = RuleScope()
        assert scope.temporal_relevance == ""
        assert scope.max_idle_sessions == 0
        assert scope.created_session == 0

    def test_custom_temporal_fields(self):
        scope = RuleScope(
            domain="sales", temporal_relevance="seasonal", max_idle_sessions=15, created_session=42
        )
        assert scope.temporal_relevance == "seasonal"
        assert scope.max_idle_sessions == 15
        assert scope.created_session == 42

    def test_decay_fresh_rule(self):
        assert temporal_decay(sessions_since_fire=0, max_idle=20) == 1.0

    def test_decay_midpoint(self):
        factor = temporal_decay(sessions_since_fire=10, max_idle=20)
        assert 0.4 < factor < 0.8

    def test_decay_at_limit(self):
        factor = temporal_decay(sessions_since_fire=20, max_idle=20)
        assert factor < 0.15

    def test_decay_beyond_limit(self):
        factor = temporal_decay(sessions_since_fire=30, max_idle=20)
        assert factor == 0.05

    def test_decay_zero_max_idle(self):
        assert temporal_decay(sessions_since_fire=100, max_idle=0) == 1.0

    def test_scope_serialization_roundtrip(self):
        from gradata._scope import scope_from_dict, scope_to_dict

        scope = RuleScope(
            domain="sales", temporal_relevance="recent", max_idle_sessions=10, created_session=5
        )
        d = scope_to_dict(scope)
        restored = scope_from_dict(d)
        assert restored.temporal_relevance == "recent"
        assert restored.max_idle_sessions == 10
        assert restored.created_session == 5
