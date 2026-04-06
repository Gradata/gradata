"""Tests for per-category similarity thresholds."""
from gradata._config import CATEGORY_SIMILARITY_THRESHOLDS, get_similarity_threshold


def test_factual_has_higher_threshold():
    assert get_similarity_threshold("ACCURACY") > get_similarity_threshold("DRAFTING")
    assert get_similarity_threshold("FACTUAL") > get_similarity_threshold("TONE")


def test_default_threshold():
    assert get_similarity_threshold("UNKNOWN_CATEGORY") == 0.35


def test_stylistic_categories_are_loose():
    for cat in ["DRAFTING", "TONE", "STYLE"]:
        assert get_similarity_threshold(cat) <= 0.35
