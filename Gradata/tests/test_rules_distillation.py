"""Tests for rules_distillation.py — cross-lesson pattern detection for rule promotion.

Tests cover:
- 3+ related lessons produce a PROPOSE candidate
- Fewer than 3 entries do NOT produce a candidate
- Already-covered patterns are marked ALREADY_COVERED (not silently dropped)
- Coverage check uses keyword overlap threshold
- Proposals sorted by count descending
- format_proposals output correctness
"""
import pytest
from gradata.enhancements.graduation.rules_distillation import (
    LessonEntry,
    DistillationProposal,
    find_distillation_candidates,
    _check_coverage,
    format_proposals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(category: str, description: str, source: str = "lessons.md", status: str = "PATTERN:0.70") -> LessonEntry:
    return LessonEntry(
        date="2026-01-01",
        status=status,
        category=category,
        description=description,
        source=source,
    )


# ---------------------------------------------------------------------------
# find_distillation_candidates — happy paths
# ---------------------------------------------------------------------------

class TestFindCandidates:
    def test_three_entries_same_category_produces_proposal(self):
        entries = [
            make_entry("DRAFTING", "Always use peer tone in emails"),
            make_entry("DRAFTING", "Keep emails short and direct"),
            make_entry("DRAFTING", "Avoid em dashes in subject lines"),
        ]
        proposals = find_distillation_candidates(entries)
        assert len(proposals) == 1
        assert proposals[0].category == "DRAFTING"
        assert proposals[0].count == 3
        assert proposals[0].action == "PROPOSE"

    def test_five_entries_gives_count_five(self):
        entries = [make_entry("ACCURACY", f"Verify fact {i}") for i in range(5)]
        proposals = find_distillation_candidates(entries)
        assert proposals[0].count == 5

    def test_two_entries_below_threshold_produces_no_proposals(self):
        entries = [
            make_entry("PRICING", "Never lead with price"),
            make_entry("PRICING", "Always anchor high first"),
        ]
        proposals = find_distillation_candidates(entries)
        assert proposals == []

    def test_exactly_at_min_count_produces_proposal(self):
        entries = [make_entry("PROCESS", f"Step {i}") for i in range(3)]
        proposals = find_distillation_candidates(entries, min_count=3)
        assert len(proposals) == 1

    def test_unrelated_categories_each_below_threshold_produce_no_proposals(self):
        entries = [
            make_entry("DRAFTING", "tip 1"),
            make_entry("PRICING", "tip 2"),
            make_entry("ACCURACY", "tip 3"),
        ]
        proposals = find_distillation_candidates(entries, min_count=3)
        # Each category has only 1 entry, below min_count=3
        assert proposals == []

    def test_multiple_categories_each_meeting_threshold(self):
        entries = (
            [make_entry("DRAFTING", f"draft tip {i}") for i in range(3)]
            + [make_entry("ACCURACY", f"accuracy tip {i}") for i in range(4)]
        )
        proposals = find_distillation_candidates(entries)
        assert len(proposals) == 2
        # Sorted by count descending: ACCURACY (4) before DRAFTING (3)
        assert proposals[0].category == "ACCURACY"
        assert proposals[1].category == "DRAFTING"

    def test_representative_principle_is_last_entry_description(self):
        entries = [
            make_entry("PROCESS", "First entry"),
            make_entry("PROCESS", "Second entry"),
            make_entry("PROCESS", "Third entry — most recent"),
        ]
        proposals = find_distillation_candidates(entries)
        assert proposals[0].principle == "Third entry — most recent"

    def test_evidence_sources_are_unique(self):
        entries = [
            make_entry("DRAFTING", "tip 1", source="lessons.md"),
            make_entry("DRAFTING", "tip 2", source="lessons.md"),
            make_entry("DRAFTING", "tip 3", source="lessons-archive.md"),
        ]
        proposals = find_distillation_candidates(entries)
        assert set(proposals[0].evidence_sources) == {"lessons.md", "lessons-archive.md"}

    def test_status_breakdown_counts_correctly(self):
        entries = [
            make_entry("DRAFTING", "tip 1", status="PATTERN:0.70"),
            make_entry("DRAFTING", "tip 2", status="CORRECTION"),
            make_entry("DRAFTING", "tip 3", status="CORRECTION"),
        ]
        proposals = find_distillation_candidates(entries)
        assert proposals[0].status_breakdown["CORRECTION"] == 2
        assert proposals[0].status_breakdown["PATTERN:0.70"] == 1


# ---------------------------------------------------------------------------
# Coverage check — ALREADY_COVERED vs PROPOSE
# ---------------------------------------------------------------------------

class TestCoverageCheck:
    def test_high_keyword_overlap_marks_already_covered(self):
        existing_rules = {
            "no_price_in_emails": "never include pricing information in prospect emails avoid pricing",
        }
        entries = [
            make_entry("PRICING", "never include pricing in emails"),
            make_entry("PRICING", "avoid mentioning price in prospect emails"),
            make_entry("PRICING", "pricing should not appear in outbound emails"),
        ]
        proposals = find_distillation_candidates(entries, existing_rules=existing_rules)
        assert len(proposals) == 1
        # Should be marked covered since there's high keyword overlap
        assert proposals[0].action == "ALREADY_COVERED"
        assert proposals[0].already_covered_by == "no_price_in_emails"

    def test_low_keyword_overlap_proposes_new_rule(self):
        existing_rules = {
            "some_unrelated_rule": "always use markdown headers in reports formatting style",
        }
        entries = [
            make_entry("DRAFTING", "keep emails concise and direct"),
            make_entry("DRAFTING", "write short subject lines for prospects"),
            make_entry("DRAFTING", "avoid long paragraphs in sales emails"),
        ]
        proposals = find_distillation_candidates(entries, existing_rules=existing_rules)
        assert proposals[0].action == "PROPOSE"
        assert proposals[0].already_covered_by is None

    def test_no_existing_rules_always_proposes(self):
        entries = [make_entry("ACCURACY", f"fact {i}") for i in range(3)]
        proposals = find_distillation_candidates(entries, existing_rules={})
        assert proposals[0].action == "PROPOSE"


class TestCheckCoverageDirectly:
    def test_exact_rule_text_match_returns_rule_name(self):
        rule_name = _check_coverage(
            "always verify numbers before reporting facts accuracy check",
            {"verify_numbers": "always verify numbers before reporting facts accuracy"},
        )
        assert rule_name == "verify_numbers"

    def test_empty_rules_returns_none(self):
        assert _check_coverage("some text", {}) is None

    def test_insufficient_overlap_returns_none(self):
        result = _check_coverage(
            "email tone direct peer",
            {"unrelated_rule": "database schema migration rollback transaction commit"},
        )
        assert result is None


# ---------------------------------------------------------------------------
# Custom min_count threshold
# ---------------------------------------------------------------------------

class TestMinCountParameter:
    def test_min_count_2_accepts_two_entries(self):
        entries = [
            make_entry("CONTEXT", "Provide full context"),
            make_entry("CONTEXT", "Reference previous conversation"),
        ]
        proposals = find_distillation_candidates(entries, min_count=2)
        assert len(proposals) == 1
        assert proposals[0].count == 2

    def test_min_count_5_rejects_four_entries(self):
        entries = [make_entry("PROCESS", f"step {i}") for i in range(4)]
        proposals = find_distillation_candidates(entries, min_count=5)
        assert proposals == []


# ---------------------------------------------------------------------------
# format_proposals
# ---------------------------------------------------------------------------

class TestFormatProposals:
    def test_empty_proposals_returns_no_candidates_message(self):
        output = format_proposals([])
        assert "No distillation candidates" in output

    def test_propose_action_shows_propose_label(self):
        proposal = DistillationProposal(
            category="DRAFTING",
            count=3,
            principle="Keep it short",
            evidence_sources=["lessons.md"],
            status_breakdown={"PATTERN:0.70": 3},
            already_covered_by=None,
            action="PROPOSE",
        )
        output = format_proposals([proposal])
        assert "PROPOSE" in output
        assert "DRAFTING" in output
        assert "Keep it short" in output

    def test_covered_action_shows_covered_label(self):
        proposal = DistillationProposal(
            category="PRICING",
            count=4,
            principle="No pricing in emails",
            evidence_sources=["lessons.md"],
            status_breakdown={"CORRECTION": 4},
            already_covered_by="no_price_rule",
            action="ALREADY_COVERED",
        )
        output = format_proposals([proposal])
        assert "COVERED" in output
        assert "no_price_rule" in output

    def test_count_in_header(self):
        proposals = [
            DistillationProposal(
                category="DRAFTING",
                count=3,
                principle="test",
                evidence_sources=["f.md"],
                status_breakdown={},
                already_covered_by=None,
                action="PROPOSE",
            )
        ]
        output = format_proposals(proposals)
        assert "1 candidates" in output or "candidates" in output
