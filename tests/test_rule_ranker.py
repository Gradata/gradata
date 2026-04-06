import pytest
from gradata.rules.rule_ranker import rank_rules

class TestRuleRanker:
    def _make_rule(self, desc, confidence=0.8, category="CODE", fire_count=5, session=1):
        return {
            "description": desc, "confidence": confidence,
            "category": category, "fire_count": fire_count, "last_session": session,
        }

    def test_higher_confidence_ranks_higher(self):
        rules = [self._make_rule("low", confidence=0.6), self._make_rule("high", confidence=0.95)]
        ranked = rank_rules(rules, current_session=10)
        assert ranked[0]["description"] == "high"

    def test_context_keywords_boost_relevant(self):
        rules = [
            self._make_rule("validate email before upload", confidence=0.8),
            self._make_rule("always clamp confidence to 0-1", confidence=0.8),
        ]
        ranked = rank_rules(rules, current_session=10, context_keywords=["confidence", "clamp", "meta_rules"])
        assert ranked[0]["description"] == "always clamp confidence to 0-1"

    def test_no_context_uses_default(self):
        rules = [self._make_rule("a", confidence=0.95), self._make_rule("b", confidence=0.60)]
        ranked = rank_rules(rules, current_session=10)
        assert ranked[0]["description"] == "a"

    def test_empty_rules(self):
        assert rank_rules([], current_session=1) == []

    def test_effectiveness_boosts(self):
        rules = [self._make_rule("proven", confidence=0.75), self._make_rule("unproven", confidence=0.85)]
        effectiveness = {
            "proven": {"effective": True, "sessions_survived": 10},
            "unproven": {"effective": False, "sessions_survived": 0},
        }
        ranked = rank_rules(rules, current_session=10, effectiveness=effectiveness)
        assert ranked[0]["description"] == "proven"

    def test_max_rules_limits_output(self):
        rules = [self._make_rule(f"rule{i}") for i in range(20)]
        ranked = rank_rules(rules, current_session=10, max_rules=5)
        assert len(ranked) == 5
