"""
Behavior-focused tests for gradata.enhancements.bandits.collaborative_filter.

Target: >=85% line coverage of the 56-statement module.
stdlib + pytest only. No network, no filesystem side-effects outside tmp_path.
"""

from __future__ import annotations

import hashlib
import math
from types import SimpleNamespace

import pytest

from gradata.enhancements.bandits.collaborative_filter import (
    BrainFingerprint,
    RuleFingerprint,
    TransferRecommendation,
    apply_transfer_boost,
    compute_brain_similarity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lesson(
    category: str,
    description: str,
    confidence: float,
    fire_count: int = 1,
) -> SimpleNamespace:
    """Minimal lesson-like object that BrainFingerprint.from_lessons expects."""
    return SimpleNamespace(
        category=category,
        description=description,
        confidence=confidence,
        fire_count=fire_count,
    )


def _rec(
    category: str = "DRAFTING",
    description: str = "some pattern",
    source_confidence: float = 0.80,
    transfer_boost: float = 0.10,
    source_brain_similarity: float = 1.0,
    n_brains_graduated: int = 3,
) -> TransferRecommendation:
    return TransferRecommendation(
        category=category,
        description=description,
        source_confidence=source_confidence,
        transfer_boost=transfer_boost,
        source_brain_similarity=source_brain_similarity,
        n_brains_graduated=n_brains_graduated,
    )


def _fingerprint(cat_dist: dict[str, int], domain: str = "test") -> BrainFingerprint:
    return BrainFingerprint(
        domain=domain,
        total_sessions=10,
        rules=[],
        category_distribution=cat_dist,
    )


# ---------------------------------------------------------------------------
# RuleFingerprint dataclass
# ---------------------------------------------------------------------------

class TestRuleFingerprint:
    def test_fields_stored(self):
        rf = RuleFingerprint(
            category="TONE",
            description_hash="abc12345",
            confidence=0.75,
            fire_count=4,
            domain="sales",
        )
        assert rf.category == "TONE"
        assert rf.description_hash == "abc12345"
        assert rf.confidence == 0.75
        assert rf.fire_count == 4
        assert rf.domain == "sales"

    def test_domain_defaults_to_empty_string(self):
        rf = RuleFingerprint(
            category="TONE",
            description_hash="abc12345",
            confidence=0.70,
            fire_count=1,
        )
        assert rf.domain == ""


# ---------------------------------------------------------------------------
# TransferRecommendation dataclass
# ---------------------------------------------------------------------------

class TestTransferRecommendation:
    def test_fields_stored(self):
        rec = TransferRecommendation(
            category="FORMAT",
            description="always use bullet lists",
            source_confidence=0.85,
            transfer_boost=0.12,
            source_brain_similarity=0.75,
            n_brains_graduated=7,
        )
        assert rec.category == "FORMAT"
        assert rec.description == "always use bullet lists"
        assert rec.source_confidence == 0.85
        assert rec.transfer_boost == 0.12
        assert rec.source_brain_similarity == 0.75
        assert rec.n_brains_graduated == 7


# ---------------------------------------------------------------------------
# BrainFingerprint dataclass + from_lessons
# ---------------------------------------------------------------------------

class TestBrainFingerprintFromLessons:
    def test_empty_lessons_gives_empty_fingerprint(self):
        fp = BrainFingerprint.from_lessons([], domain="sales", total_sessions=5)
        assert fp.rules == []
        assert fp.category_distribution == {}
        assert fp.domain == "sales"
        assert fp.total_sessions == 5

    def test_low_confidence_lessons_excluded(self):
        """Lessons with confidence < 0.5 must not appear in the fingerprint."""
        lessons = [
            _lesson("TONE", "be concise", 0.49),
            _lesson("TONE", "use active voice", 0.0),
        ]
        fp = BrainFingerprint.from_lessons(lessons)
        assert fp.rules == []
        assert fp.category_distribution == {}

    def test_threshold_is_exclusive_at_05(self):
        """Confidence == 0.5 is below threshold (strictly < 0.5 excluded)."""
        lessons = [
            _lesson("TONE", "be concise", 0.50),   # exactly 0.5 — included
            _lesson("TONE", "be brief", 0.499),     # just below — excluded
        ]
        fp = BrainFingerprint.from_lessons(lessons)
        assert len(fp.rules) == 1
        assert fp.rules[0].confidence == 0.50

    def test_qualifying_lesson_produces_rule_fingerprint(self):
        lessons = [_lesson("DRAFTING", "Start with conclusion", 0.75, fire_count=3)]
        fp = BrainFingerprint.from_lessons(lessons, domain="eng")
        assert len(fp.rules) == 1
        rule = fp.rules[0]
        assert rule.category == "DRAFTING"
        assert rule.confidence == 0.75
        assert rule.fire_count == 3
        assert rule.domain == "eng"

    def test_description_hash_is_first_8_chars_of_sha256(self):
        desc = "  Start With CONCLUSION  "
        expected_hash = hashlib.sha256(desc.lower().strip().encode()).hexdigest()[:8]
        lessons = [_lesson("DRAFTING", desc, 0.80)]
        fp = BrainFingerprint.from_lessons(lessons)
        assert fp.rules[0].description_hash == expected_hash

    def test_category_distribution_counts_qualifying_lessons(self):
        lessons = [
            _lesson("TONE", "be direct", 0.60),
            _lesson("TONE", "no jargon", 0.70),
            _lesson("FORMAT", "use headers", 0.80),
            _lesson("DRAFTING", "low confidence", 0.30),  # excluded
        ]
        fp = BrainFingerprint.from_lessons(lessons)
        assert fp.category_distribution == {"TONE": 2, "FORMAT": 1}
        assert len(fp.rules) == 3

    def test_default_domain_and_sessions(self):
        fp = BrainFingerprint.from_lessons([])
        assert fp.domain == ""
        assert fp.total_sessions == 0

    def test_multiple_categories_each_counted_independently(self):
        lessons = [_lesson(cat, "desc", 0.60) for cat in ["A", "B", "C", "A"]]
        fp = BrainFingerprint.from_lessons(lessons)
        assert fp.category_distribution["A"] == 2
        assert fp.category_distribution["B"] == 1
        assert fp.category_distribution["C"] == 1


# ---------------------------------------------------------------------------
# compute_brain_similarity
# ---------------------------------------------------------------------------

class TestComputeBrainSimilarity:
    def test_identical_distributions_returns_1(self):
        cats = {"TONE": 5, "FORMAT": 3}
        a = _fingerprint(cats)
        b = _fingerprint(cats)
        assert compute_brain_similarity(a, b) == 1.0

    def test_both_empty_returns_0(self):
        a = _fingerprint({})
        b = _fingerprint({})
        assert compute_brain_similarity(a, b) == 0.0

    def test_disjoint_categories_returns_0(self):
        a = _fingerprint({"TONE": 4})
        b = _fingerprint({"FORMAT": 4})
        assert compute_brain_similarity(a, b) == 0.0

    def test_one_empty_returns_0(self):
        """One brain has no rules — magnitude is 0, so similarity is 0."""
        a = _fingerprint({"TONE": 5})
        b = _fingerprint({})
        assert compute_brain_similarity(a, b) == 0.0

    def test_partial_overlap_is_between_0_and_1(self):
        a = _fingerprint({"TONE": 3, "FORMAT": 1})
        b = _fingerprint({"TONE": 3, "DRAFTING": 1})
        sim = compute_brain_similarity(a, b)
        assert 0.0 < sim < 1.0

    def test_similarity_is_symmetric(self):
        a = _fingerprint({"TONE": 3, "FORMAT": 1})
        b = _fingerprint({"TONE": 2, "FORMAT": 4, "DRAFTING": 1})
        assert compute_brain_similarity(a, b) == compute_brain_similarity(b, a)

    def test_result_is_rounded_to_4_decimal_places(self):
        a = _fingerprint({"TONE": 1, "FORMAT": 2})
        b = _fingerprint({"TONE": 3, "FORMAT": 1})
        result = compute_brain_similarity(a, b)
        # Result should not have more than 4 decimal places
        assert result == round(result, 4)

    def test_known_cosine_value(self):
        """Manual cosine: a=[2,0] b=[1,1] -> dot=2, |a|=2, |b|=sqrt(2) -> 2/(2*sqrt(2))=sqrt(2)/2."""
        a = _fingerprint({"X": 2})           # sorted cats: X, Y -> [2, 0]
        b = _fingerprint({"X": 1, "Y": 1})   # [1, 1]
        expected = round(2 / (2 * math.sqrt(2)), 4)
        assert compute_brain_similarity(a, b) == expected

    def test_zero_vector_brain_returns_0(self):
        """Edge: category exists but count is 0 (zero magnitude)."""
        a = _fingerprint({"TONE": 0})
        b = _fingerprint({"TONE": 3})
        assert compute_brain_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# apply_transfer_boost
# ---------------------------------------------------------------------------

class TestApplyTransferBoost:
    def _mutable_lesson(
        self,
        category: str = "DRAFTING",
        confidence: float = 0.60,
    ) -> SimpleNamespace:
        return SimpleNamespace(category=category, confidence=confidence)

    def test_no_lessons_returns_empty_list(self):
        result = apply_transfer_boost([], [_rec()])
        assert result == []

    def test_no_recommendations_leaves_lessons_unchanged(self):
        lesson = self._mutable_lesson()
        original_conf = lesson.confidence
        result = apply_transfer_boost([lesson], [])
        assert result[0].confidence == original_conf

    def test_matching_category_applies_boost(self):
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec = _rec(category="DRAFTING", transfer_boost=0.10, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec])
        assert lesson.confidence == round(min(0.89, 0.60 + 0.10 * 1.0), 2)

    def test_non_matching_category_does_not_boost(self):
        lesson = self._mutable_lesson("TONE", 0.60)
        rec = _rec(category="FORMAT", transfer_boost=0.10, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec])
        assert lesson.confidence == 0.60

    def test_boost_capped_at_max_boost(self):
        """transfer_boost * similarity exceeds default max_boost of 0.15."""
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec = _rec(category="DRAFTING", transfer_boost=0.50, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec], max_boost=0.15)
        assert lesson.confidence == round(min(0.89, 0.60 + 0.15), 2)

    def test_boost_capped_below_rule_threshold(self):
        """Confidence can never reach 0.90 (RULE threshold)."""
        lesson = self._mutable_lesson("DRAFTING", 0.88)
        rec = _rec(category="DRAFTING", transfer_boost=0.20, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec])
        assert lesson.confidence <= 0.89

    def test_lesson_at_or_above_090_not_boosted(self):
        """Lessons already at RULE threshold are not touched."""
        lesson = self._mutable_lesson("DRAFTING", 0.90)
        rec = _rec(category="DRAFTING", transfer_boost=0.10, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec])
        assert lesson.confidence == 0.90

    def test_zero_transfer_boost_skips(self):
        """transfer_boost == 0 must not trigger the boost path."""
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec = _rec(category="DRAFTING", transfer_boost=0.0, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec])
        assert lesson.confidence == 0.60

    def test_only_first_matching_rec_applied_per_lesson(self):
        """break after first match — second matching rec must not stack."""
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec1 = _rec(category="DRAFTING", transfer_boost=0.10, source_brain_similarity=1.0)
        rec2 = _rec(category="DRAFTING", transfer_boost=0.10, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec1, rec2])
        # Should only see one boost of 0.10, not two stacked
        assert lesson.confidence == round(min(0.89, 0.60 + 0.10), 2)

    def test_multiple_lessons_boosted_independently(self):
        l1 = self._mutable_lesson("TONE", 0.55)
        l2 = self._mutable_lesson("FORMAT", 0.65)
        recs = [
            _rec(category="TONE", transfer_boost=0.08, source_brain_similarity=1.0),
            _rec(category="FORMAT", transfer_boost=0.12, source_brain_similarity=1.0),
        ]
        apply_transfer_boost([l1, l2], recs)
        assert l1.confidence == round(min(0.89, 0.55 + 0.08), 2)
        assert l2.confidence == round(min(0.89, 0.65 + 0.12), 2)

    def test_boost_scaled_by_similarity(self):
        """Effective boost = transfer_boost * source_brain_similarity."""
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec = _rec(category="DRAFTING", transfer_boost=0.20, source_brain_similarity=0.50)
        apply_transfer_boost([lesson], [rec])
        # 0.20 * 0.50 = 0.10; below max_boost default 0.15
        assert lesson.confidence == round(min(0.89, 0.60 + 0.10), 2)

    def test_custom_max_boost_respected(self):
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec = _rec(category="DRAFTING", transfer_boost=0.30, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec], max_boost=0.05)
        assert lesson.confidence == round(min(0.89, 0.60 + 0.05), 2)

    def test_returns_same_list_object(self):
        """Mutates and returns the original list."""
        lessons = [self._mutable_lesson()]
        result = apply_transfer_boost(lessons, [])
        assert result is lessons

    def test_negative_boost_does_not_apply(self):
        """Negative transfer_boost fails the > 0 guard — no change."""
        lesson = self._mutable_lesson("DRAFTING", 0.60)
        rec = _rec(category="DRAFTING", transfer_boost=-0.10, source_brain_similarity=1.0)
        apply_transfer_boost([lesson], [rec])
        assert lesson.confidence == 0.60
