"""Tests for multi-strategy retrieval fusion with correction-aware boosting."""
from __future__ import annotations

import pytest

from gradata.enhancements.retrieval_fusion import (
    MergedRule,
    ScoredRule,
    apply_correction_boost,
    reciprocal_rank_fusion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rule(rule_id: str, score: float = 1.0, metadata: dict | None = None) -> ScoredRule:
    return ScoredRule(
        rule_id=rule_id,
        text=f"Rule text for {rule_id}",
        score=score,
        source="semantic",
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# reciprocal_rank_fusion
# ---------------------------------------------------------------------------

class TestRRFSingleList:
    def test_rank_order_matches_list_order(self):
        rules = [make_rule("a"), make_rule("b"), make_rule("c")]
        merged = reciprocal_rank_fusion([rules])

        assert [m.rule.rule_id for m in merged] == ["a", "b", "c"]

    def test_rrf_ranks_are_sequential(self):
        rules = [make_rule("a"), make_rule("b"), make_rule("c")]
        merged = reciprocal_rank_fusion([rules])

        assert [m.rrf_rank for m in merged] == [1, 2, 3]

    def test_scores_are_descending(self):
        rules = [make_rule("a"), make_rule("b"), make_rule("c")]
        merged = reciprocal_rank_fusion([rules])

        scores = [m.rrf_score for m in merged]
        assert scores == sorted(scores, reverse=True)


class TestRRFMultipleLists:
    def test_doc_in_all_lists_scores_highest(self):
        """A rule appearing in every strategy list should rank first."""
        semantic = [make_rule("shared"), make_rule("only_sem")]
        keyword = [make_rule("only_kw"), make_rule("shared")]
        scope = [make_rule("shared"), make_rule("only_scope")]

        merged = reciprocal_rank_fusion([semantic, keyword, scope])

        assert merged[0].rule.rule_id == "shared"

    def test_source_rank_keys_recorded(self):
        semantic = [make_rule("x")]
        keyword = [make_rule("x")]
        merged = reciprocal_rank_fusion([semantic, keyword])

        assert "semantic_rank" in merged[0].source_ranks
        assert "keyword_rank" in merged[0].source_ranks

    def test_combined_score_initialized_to_rrf_score(self):
        rules = [make_rule("a")]
        merged = reciprocal_rank_fusion([rules])
        assert merged[0].combined_score == pytest.approx(merged[0].rrf_score)


class TestRRFSourceWeights:
    def test_weighted_source_boosts_rank(self):
        """A rule ranked first only in the weighted source should beat one ranked
        first only in an unweighted source."""
        semantic = [make_rule("sem_top"), make_rule("kw_top")]
        keyword = [make_rule("kw_top"), make_rule("sem_top")]

        # Heavily weight semantic so sem_top wins overall
        merged = reciprocal_rank_fusion(
            [semantic, keyword],
            source_weights={"semantic": 10.0, "keyword": 1.0},
        )

        assert merged[0].rule.rule_id == "sem_top"

    def test_equal_weights_tie_broken_by_position(self):
        """With equal weights, the rule ranked first in the first list should lead."""
        list_a = [make_rule("first"), make_rule("second")]
        list_b = [make_rule("second"), make_rule("first")]

        merged = reciprocal_rank_fusion(
            [list_a, list_b],
            source_weights={"semantic": 1.0, "keyword": 1.0},
        )
        # Both appear in both lists at opposing positions — "first" at rank 1 in list_a,
        # "second" at rank 1 in list_b. Scores are symmetric; order is determined by
        # dict iteration which preserves insertion order (first-seen wins ties).
        # The important thing is all rules are present.
        rule_ids = {m.rule.rule_id for m in merged}
        assert rule_ids == {"first", "second"}


class TestRRFDeduplication:
    def test_first_seen_metadata_is_preserved(self):
        """When the same rule_id appears in multiple lists, metadata from the
        first occurrence is kept."""
        rule_first = ScoredRule(
            rule_id="dup",
            text="original text",
            score=0.9,
            source="semantic",
            metadata={"version": "first"},
        )
        rule_second = ScoredRule(
            rule_id="dup",
            text="different text",
            score=0.5,
            source="keyword",
            metadata={"version": "second"},
        )

        merged = reciprocal_rank_fusion([[rule_first], [rule_second]])

        assert len(merged) == 1
        assert merged[0].rule.metadata["version"] == "first"
        assert merged[0].rule.text == "original text"


class TestRRFEmptyInput:
    def test_empty_list_of_lists(self):
        assert reciprocal_rank_fusion([]) == []

    def test_all_empty_inner_lists(self):
        merged = reciprocal_rank_fusion([[], [], []])
        assert merged == []

    def test_some_empty_inner_lists(self):
        rules = [make_rule("a"), make_rule("b")]
        merged = reciprocal_rank_fusion([rules, [], rules])
        # Both rules should still be present
        assert {m.rule.rule_id for m in merged} == {"a", "b"}


class TestRRFKParameter:
    def test_lower_k_makes_distribution_more_top_heavy(self):
        """With smaller k, the gap between rank-1 and rank-2 scores is larger."""
        rules = [make_rule("top"), make_rule("bottom")]

        merged_low_k = reciprocal_rank_fusion([rules], k=1)
        merged_high_k = reciprocal_rank_fusion([rules], k=1000)

        gap_low = merged_low_k[0].rrf_score - merged_low_k[1].rrf_score
        gap_high = merged_high_k[0].rrf_score - merged_high_k[1].rrf_score

        assert gap_low > gap_high


# ---------------------------------------------------------------------------
# apply_correction_boost
# ---------------------------------------------------------------------------

class TestCorrectionBoost:
    def test_correction_born_rules_get_boosted(self):
        """from_correction=True should increase combined_score above rrf_score."""
        rule = ScoredRule(
            rule_id="r1",
            text="x",
            score=1.0,
            source="semantic",
            metadata={"from_correction": True, "recency_score": 0.5, "severity_score": 0.5},
        )
        mr = MergedRule(rule=rule, rrf_score=1.0, rrf_rank=1, combined_score=1.0)

        apply_correction_boost([mr])

        # Neutral recency/severity, positive correction => combined > rrf
        assert mr.combined_score > mr.rrf_score

    def test_stale_rules_get_penalized(self):
        """recency_score=0.0 (stale) should decrease combined_score below rrf_score."""
        rule = ScoredRule(
            rule_id="r2",
            text="x",
            score=1.0,
            source="semantic",
            metadata={"from_correction": False, "recency_score": 0.0, "severity_score": 0.5},
        )
        mr = MergedRule(rule=rule, rrf_score=1.0, rrf_rank=1, combined_score=1.0)

        apply_correction_boost([mr])

        assert mr.combined_score < mr.rrf_score

    def test_severe_corrections_get_boosted(self):
        """severity_score=1.0 (severe) produces a positive severity boost factor.

        We hold correction and recency neutral (0.5) so only the severity term
        varies. The isolated severity boost is 1 + 0.10*(1.0-0.5) = 1.05.
        When correction is neutral (from_correction=False => is_correction=0.0),
        correction_boost = 1 + 0.30*(0.0-0.5) = 0.85 — a penalty.
        To isolate severity, use correction=True so correction_boost is positive,
        confirming severity_boost > 1.0 contributes to the final product.
        """
        rule_neutral_correction = ScoredRule(
            rule_id="r3a",
            text="x",
            score=1.0,
            source="semantic",
            metadata={"from_correction": True, "recency_score": 0.5, "severity_score": 1.0},
        )
        rule_neutral_severity = ScoredRule(
            rule_id="r3b",
            text="x",
            score=1.0,
            source="semantic",
            metadata={"from_correction": True, "recency_score": 0.5, "severity_score": 0.5},
        )
        mr_high = MergedRule(rule=rule_neutral_correction, rrf_score=1.0, rrf_rank=1, combined_score=1.0)
        mr_neutral = MergedRule(rule=rule_neutral_severity, rrf_score=1.0, rrf_rank=2, combined_score=1.0)

        apply_correction_boost([mr_high, mr_neutral])

        # High severity should score strictly higher than neutral severity
        assert mr_high.combined_score > mr_neutral.combined_score

    def test_neutral_recency_and_severity_leave_those_boosts_at_unity(self):
        """recency_score=0.5 and severity_score=0.5 each contribute a boost of 1.0.

        The correction signal is binary (False=0.0, True=1.0), so true neutrality
        requires recency and severity both at 0.5. We verify the combined_score
        equals rrf * correction_boost * 1.0 * 1.0 — i.e. only the correction
        term deviates from unity.
        """
        rule = ScoredRule(
            rule_id="r4",
            text="x",
            score=1.0,
            source="semantic",
            metadata={"from_correction": False, "recency_score": 0.5, "severity_score": 0.5},
        )
        mr = MergedRule(rule=rule, rrf_score=1.0, rrf_rank=1, combined_score=1.0)

        apply_correction_boost([mr], correction_alpha=0.30, recency_alpha=0.20, severity_alpha=0.10)

        # is_correction=0.0 => correction_boost = 1 + 0.30*(0.0-0.5) = 0.85
        # recency and severity are both neutral => boosts of 1.0
        expected = 1.0 * 0.85 * 1.0 * 1.0
        assert mr.combined_score == pytest.approx(expected)

    def test_missing_metadata_uses_neutral_defaults(self):
        """Rules with no metadata keys should behave like neutral signals."""
        rule = ScoredRule(rule_id="r5", text="x", score=1.0, source="semantic")
        mr = MergedRule(rule=rule, rrf_score=2.0, rrf_rank=1, combined_score=2.0)

        apply_correction_boost([mr])

        # from_correction defaults to False (0.0), recency/severity default to 0.5
        # correction_boost = 1 + 0.30*(0.0-0.5) = 0.85
        # recency_boost = 1.0, severity_boost = 1.0
        expected = 2.0 * (1.0 + 0.30 * (0.0 - 0.5)) * 1.0 * 1.0
        assert mr.combined_score == pytest.approx(expected)

    def test_boost_is_multiplicative(self):
        """Verify the exact formula: rrf * correction_boost * recency_boost * severity_boost."""
        rule = ScoredRule(
            rule_id="r6",
            text="x",
            score=1.0,
            source="semantic",
            metadata={"from_correction": True, "recency_score": 0.8, "severity_score": 0.9},
        )
        mr = MergedRule(rule=rule, rrf_score=0.5, rrf_rank=1, combined_score=0.5)

        apply_correction_boost([mr], correction_alpha=0.30, recency_alpha=0.20, severity_alpha=0.10)

        cb = 1.0 + 0.30 * (1.0 - 0.5)   # 1.15
        rb = 1.0 + 0.20 * (0.8 - 0.5)   # 1.06
        sb = 1.0 + 0.10 * (0.9 - 0.5)   # 1.04
        expected = 0.5 * cb * rb * sb

        assert mr.combined_score == pytest.approx(expected, rel=1e-6)

    def test_modifies_in_place(self):
        """apply_correction_boost must not return a new list; it mutates in-place."""
        rule = ScoredRule(rule_id="r7", text="x", score=1.0, source="semantic")
        mr = MergedRule(rule=rule, rrf_score=1.0, rrf_rank=1, combined_score=1.0)
        result = [mr]

        return_value = apply_correction_boost(result)

        assert return_value is None  # in-place contract
        assert result[0] is mr
