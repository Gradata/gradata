"""Tests for contextual_bandit.py — Thompson Sampling explore/exploit for rule selection.

Tests cover:
- Reward update increments alpha (accepted) / beta (rejected)
- Arm with best expected value wins selection over many trials
- Exploration bonus for under-sampled rules
- Context key tracking with EMA
- export_arms / load_arms roundtrip
- select() with k > candidates returns all candidates
- RuleArm expected_value property
"""
import random
import pytest
from gradata.enhancements.bandits.contextual_bandit import (
    RuleArm,
    RuleBandit,
    SelectionResult,
)


# ---------------------------------------------------------------------------
# RuleArm
# ---------------------------------------------------------------------------

class TestRuleArm:
    def test_expected_value_is_alpha_over_alpha_plus_beta(self):
        arm = RuleArm(rule_id="R1", alpha=3.0, beta=1.0)
        assert arm.expected_value == pytest.approx(3.0 / 4.0)

    def test_expected_value_uniform_prior(self):
        arm = RuleArm(rule_id="R1")
        assert arm.expected_value == pytest.approx(0.5)

    def test_sample_returns_value_in_0_1(self):
        arm = RuleArm(rule_id="R1", alpha=2.0, beta=2.0)
        for _ in range(50):
            s = arm.sample()
            assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# RuleBandit — reward update
# ---------------------------------------------------------------------------

class TestRuleBanditUpdate:
    def test_accepted_update_increments_alpha(self):
        bandit = RuleBandit()
        arm = bandit.get_or_create_arm("R1")
        alpha_before = arm.alpha
        bandit.update("R1", accepted=True)
        assert arm.alpha == alpha_before + 1.0
        assert arm.beta == 1.0  # unchanged

    def test_rejected_update_increments_beta(self):
        bandit = RuleBandit()
        arm = bandit.get_or_create_arm("R1")
        beta_before = arm.beta
        bandit.update("R1", accepted=False)
        assert arm.beta == beta_before + 1.0
        assert arm.alpha == 1.0  # unchanged

    def test_update_increments_total_pulls(self):
        bandit = RuleBandit()
        bandit.update("R1", accepted=True)
        bandit.update("R1", accepted=True)
        assert bandit.get_or_create_arm("R1").total_pulls == 2

    def test_context_key_initialises_to_0_5(self):
        bandit = RuleBandit()
        bandit.update("R1", accepted=True, context_key="email_draft:exec")
        arm = bandit.get_or_create_arm("R1")
        # After first accepted update the EMA should be above 0.5
        assert "email_draft:exec" in arm.context_scores
        assert arm.context_scores["email_draft:exec"] > 0.5

    def test_context_key_ema_decreases_on_rejection(self):
        bandit = RuleBandit()
        # Prime with initial accepted to set a value
        bandit.update("R1", accepted=True, context_key="ctx")
        arm = bandit.get_or_create_arm("R1")
        score_before = arm.context_scores["ctx"]
        bandit.update("R1", accepted=False, context_key="ctx")
        assert arm.context_scores["ctx"] < score_before

    def test_update_creates_arm_if_not_exists(self):
        bandit = RuleBandit()
        assert "NEW_RULE" not in bandit._arms
        bandit.update("NEW_RULE", accepted=True)
        assert "NEW_RULE" in bandit._arms


# ---------------------------------------------------------------------------
# RuleBandit — selection
# ---------------------------------------------------------------------------

class TestRuleBanditSelect:
    def test_select_returns_selection_result(self):
        bandit = RuleBandit()
        result = bandit.select(["R1", "R2", "R3"], k=2)
        assert isinstance(result, SelectionResult)
        assert len(result.selected_rules) == 2

    def test_select_k_larger_than_candidates_returns_all(self):
        bandit = RuleBandit()
        result = bandit.select(["R1", "R2"], k=10)
        assert len(result.selected_rules) == 2

    def test_select_empty_candidates_returns_empty(self):
        bandit = RuleBandit()
        result = bandit.select([], k=5)
        assert result.selected_rules == []

    def test_high_ev_rule_wins_most_selections(self):
        """A rule with alpha=20, beta=1 (EV ~0.95) should be selected far more often
        than a rule with alpha=1, beta=20 (EV ~0.048) in 100 trials."""
        random.seed(42)
        bandit = RuleBandit()
        # Manually prime arm states
        strong_arm = bandit.get_or_create_arm("STRONG")
        strong_arm.alpha = 20.0
        strong_arm.beta = 1.0
        strong_arm.total_pulls = 50

        weak_arm = bandit.get_or_create_arm("WEAK")
        weak_arm.alpha = 1.0
        weak_arm.beta = 20.0
        weak_arm.total_pulls = 50

        win_count = 0
        trials = 200
        for _ in range(trials):
            result = bandit.select(["STRONG", "WEAK"], k=1)
            if "STRONG" in result.selected_rules:
                win_count += 1

        # High EV arm should win at least 85% of the time
        assert win_count > trials * 0.85, f"STRONG won only {win_count}/{trials}"

    def test_under_sampled_rule_gets_exploration_bonus(self):
        """A rule with 0 pulls should receive was_exploration=True."""
        bandit = RuleBandit()
        result = bandit.select(["NEWRULE"], k=1)
        # Under 5 pulls → exploration
        assert result.was_exploration.get("NEWRULE") is True

    def test_scores_dict_includes_selected_rules_only(self):
        bandit = RuleBandit()
        result = bandit.select(["R1", "R2", "R3"], k=2)
        assert set(result.scores.keys()) == set(result.selected_rules)

    def test_context_boosts_rule_with_good_history(self):
        """A rule with a known good context score should outperform a naive rule."""
        random.seed(99)
        bandit = RuleBandit()

        # Prime rule A with many successes in this context
        arm_a = bandit.get_or_create_arm("A")
        arm_a.alpha = 15.0
        arm_a.beta = 2.0
        arm_a.total_pulls = 50
        arm_a.context_scores["task:email_draft"] = 0.95

        arm_b = bandit.get_or_create_arm("B")
        arm_b.alpha = 5.0
        arm_b.beta = 5.0
        arm_b.total_pulls = 50

        # Rule A should win selection in this context most of the time
        win_a = sum(
            1 for _ in range(100)
            if "A" in bandit.select(["A", "B"], context={"task": "email_draft"}, k=1).selected_rules
        )
        assert win_a >= 70


# ---------------------------------------------------------------------------
# Export / load roundtrip
# ---------------------------------------------------------------------------

class TestArmPersistence:
    def test_export_arms_contains_all_arms(self):
        bandit = RuleBandit()
        bandit.update("R1", accepted=True)
        bandit.update("R2", accepted=False)
        data = bandit.export_arms()
        rule_ids = [d["rule_id"] for d in data]
        assert "R1" in rule_ids
        assert "R2" in rule_ids

    def test_load_arms_restores_alpha_beta(self):
        bandit = RuleBandit()
        bandit.load_arms([
            {"rule_id": "R1", "alpha": 8.0, "beta": 2.0, "total_pulls": 10, "context_scores": {}},
        ])
        arm = bandit.get_or_create_arm("R1")
        assert arm.alpha == 8.0
        assert arm.beta == 2.0
        assert arm.total_pulls == 10

    def test_export_then_load_roundtrip(self):
        bandit1 = RuleBandit()
        for _ in range(5):
            bandit1.update("R1", accepted=True, context_key="ctx")
        bandit1.update("R1", accepted=False)
        data = bandit1.export_arms()

        bandit2 = RuleBandit()
        bandit2.load_arms(data)
        arm = bandit2.get_or_create_arm("R1")
        assert arm.alpha == bandit1.get_or_create_arm("R1").alpha
        assert arm.beta == bandit1.get_or_create_arm("R1").beta

    def test_load_arms_uses_defaults_for_missing_fields(self):
        bandit = RuleBandit()
        bandit.load_arms([{"rule_id": "MINIMAL"}])
        arm = bandit.get_or_create_arm("MINIMAL")
        assert arm.alpha == 1.0
        assert arm.beta == 1.0
        assert arm.total_pulls == 0


# ---------------------------------------------------------------------------
# Context key construction
# ---------------------------------------------------------------------------

class TestContextKeyBuilding:
    def test_context_key_uses_task_audience_domain(self):
        bandit = RuleBandit()
        key = bandit._build_context_key({"task": "email_draft", "audience": "executive", "domain": "saas"})
        assert "task:email_draft" in key
        assert "audience:executive" in key
        assert "domain:saas" in key

    def test_context_key_ignores_unknown_fields(self):
        bandit = RuleBandit()
        key = bandit._build_context_key({"task": "email_draft", "unknown_field": "ignored"})
        assert "unknown_field" not in key

    def test_empty_context_returns_empty_key(self):
        bandit = RuleBandit()
        key = bandit._build_context_key({})
        assert key == ""
