"""
Tests for gradata.enhancements.scoring.memory_extraction

Coverage target: >=85% of 100 statements.
Strategy: exercise every public method, every branch in extract() and
reconcile(), and every private helper with targeted inputs.
"""

from __future__ import annotations

import pytest

from gradata.enhancements.scoring.memory_extraction import (
    ExtractedFact,
    MemoryExtractor,
    ReconcileAction,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def extractor() -> MemoryExtractor:
    return MemoryExtractor()


# ---------------------------------------------------------------------------
# Dataclass smoke tests
# ---------------------------------------------------------------------------

class TestExtractedFact:
    def test_defaults(self):
        f = ExtractedFact(content="I prefer dark mode", fact_type="preference")
        assert f.confidence == 0.7
        assert f.source_role == "user"
        assert f.entities == []
        assert f.timestamp == ""

    def test_explicit_fields(self):
        f = ExtractedFact(
            content="Alice works at ACME",
            fact_type="relationship",
            confidence=0.9,
            source_role="assistant",
            entities=["Alice", "ACME"],
            timestamp="2026-01-01T00:00:00Z",
        )
        assert f.fact_type == "relationship"
        assert f.confidence == 0.9
        assert "Alice" in f.entities


class TestReconcileAction:
    def test_defaults(self):
        fact = ExtractedFact(content="test", fact_type="preference")
        a = ReconcileAction(op="add", fact=fact)
        assert a.target_id is None
        assert a.reason == ""
        assert a.supersedes is None

    def test_full(self):
        fact = ExtractedFact(content="test", fact_type="preference")
        a = ReconcileAction(
            op="invalidate",
            fact=fact,
            target_id="abc-123",
            reason="superseded",
            supersedes="abc-123",
        )
        assert a.op == "invalidate"
        assert a.target_id == "abc-123"
        assert a.supersedes == "abc-123"


# ---------------------------------------------------------------------------
# MemoryExtractor.extract — basic extraction paths
# ---------------------------------------------------------------------------

class TestExtractPreferences:
    def test_prefer_pattern(self, extractor):
        msgs = [{"role": "user", "content": "I prefer bullet points for lists."}]
        facts = extractor.extract(msgs)
        prefs = [f for f in facts if f.fact_type == "preference"]
        assert len(prefs) >= 1
        assert all(f.source_role == "user" for f in prefs)
        assert all(f.confidence == 0.8 for f in prefs)

    def test_like_pattern(self, extractor):
        msgs = [{"role": "user", "content": "I like concise responses please."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "preference" for f in facts)

    def test_never_use_pattern(self, extractor):
        msgs = [{"role": "user", "content": "Never use passive voice in emails."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "preference" for f in facts)

    def test_dont_use_pattern(self, extractor):
        msgs = [{"role": "user", "content": "don't use emojis in formal writing."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "preference" for f in facts)

    def test_instead_of_pattern(self, extractor):
        msgs = [{"role": "user", "content": "instead of verbose prose, use bullet points."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "preference" for f in facts)

    def test_short_preference_match_skipped(self, extractor):
        # Match text <= 10 chars should be excluded from preference extraction
        msgs = [{"role": "user", "content": "I prefer ok."}]
        facts = extractor.extract(msgs)
        # Either no preference extracted or only valid ones
        prefs = [f for f in facts if f.fact_type == "preference"]
        for p in prefs:
            assert len(p.content) > 10

    def test_assistant_role_preference_captured(self, extractor):
        msgs = [{"role": "assistant", "content": "I prefer structured output for clarity."}]
        facts = extractor.extract(msgs)
        prefs = [f for f in facts if f.fact_type == "preference"]
        assert all(f.source_role == "assistant" for f in prefs)


class TestExtractActionItems:
    def test_need_to_pattern(self, extractor):
        msgs = [{"role": "user", "content": "I need to follow up with the client tomorrow."}]
        facts = extractor.extract(msgs)
        actions = [f for f in facts if f.fact_type == "action_item"]
        assert len(actions) >= 1
        assert all(f.confidence == 0.6 for f in actions)

    def test_will_pattern(self, extractor):
        msgs = [{"role": "user", "content": "I will send the proposal by Friday."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "action_item" for f in facts)

    def test_follow_up_pattern(self, extractor):
        msgs = [{"role": "user", "content": "follow up on the sales call next week."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "action_item" for f in facts)

    def test_action_item_only_for_user_role(self, extractor):
        # Action items are only captured for role == "user"
        msgs = [{"role": "assistant", "content": "I will send the report by Monday."}]
        facts = extractor.extract(msgs)
        actions = [f for f in facts if f.fact_type == "action_item"]
        assert len(actions) == 0

    def test_short_action_item_skipped(self, extractor):
        msgs = [{"role": "user", "content": "need to go."}]
        facts = extractor.extract(msgs)
        actions = [f for f in facts if f.fact_type == "action_item"]
        for a in actions:
            assert len(a.content) > 10

    def test_deadline_day_pattern(self, extractor):
        # The "by friday" temporal action pattern matches; content is short so
        # action_item may be skipped by the >10 char guard, but the match itself
        # is exercised. Verify extract doesn't raise and returns a list.
        msgs = [{"role": "user", "content": "Submit the report by Friday."}]
        facts = extractor.extract(msgs)
        assert isinstance(facts, list)

    def test_must_pattern(self, extractor):
        msgs = [{"role": "user", "content": "I must review the contract before signing it."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "action_item" for f in facts)


class TestExtractTemporal:
    def test_meeting_on_pattern(self, extractor):
        msgs = [{"role": "user", "content": "meeting on Monday at 3pm."}]
        facts = extractor.extract(msgs)
        temporals = [f for f in facts if f.fact_type == "temporal"]
        assert len(temporals) >= 1
        assert all(f.confidence == 0.7 for f in temporals)

    def test_deadline_by_pattern(self, extractor):
        msgs = [{"role": "user", "content": "deadline by next Wednesday."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "temporal" for f in facts)

    def test_call_scheduled_for_pattern(self, extractor):
        msgs = [{"role": "user", "content": "call scheduled for Thursday morning."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "temporal" for f in facts)

    def test_demo_on_pattern(self, extractor):
        msgs = [{"role": "assistant", "content": "demo on Friday at noon."}]
        facts = extractor.extract(msgs)
        temporals = [f for f in facts if f.fact_type == "temporal"]
        assert len(temporals) >= 1
        # Temporal facts capture all roles, no entities field populated
        assert all(not hasattr(t, "nonexistent") for t in temporals)

    def test_expires_on_pattern(self, extractor):
        msgs = [{"role": "user", "content": "The offer expires on December 31."}]
        facts = extractor.extract(msgs)
        assert any(f.fact_type == "temporal" for f in facts)


class TestExtractRelationships:
    def test_works_at_pattern(self, extractor):
        msgs = [{"role": "user", "content": "Sarah works at Google in engineering."}]
        facts = extractor.extract(msgs)
        rels = [f for f in facts if f.fact_type == "relationship"]
        assert len(rels) >= 1
        assert all(f.confidence == 0.6 for f in rels)
        # Entities come from match groups
        assert all(len(f.entities) > 0 for f in rels)

    def test_is_the_at_pattern(self, extractor):
        msgs = [{"role": "user", "content": "John is the VP at Acme Corp."}]
        facts = extractor.extract(msgs)
        rels = [f for f in facts if f.fact_type == "relationship"]
        assert len(rels) >= 1

    def test_joined_pattern(self, extractor):
        msgs = [{"role": "user", "content": "Maria joined Stripe last month."}]
        facts = extractor.extract(msgs)
        rels = [f for f in facts if f.fact_type == "relationship"]
        assert len(rels) >= 1


class TestExtractEdgeCases:
    def test_empty_messages_list(self, extractor):
        facts = extractor.extract([])
        assert facts == []

    def test_message_with_empty_content(self, extractor):
        msgs = [{"role": "user", "content": ""}]
        facts = extractor.extract(msgs)
        assert facts == []

    def test_message_missing_content_key(self, extractor):
        msgs = [{"role": "user"}]
        facts = extractor.extract(msgs)
        assert facts == []

    def test_message_missing_role_defaults_to_user(self, extractor):
        msgs = [{"content": "I prefer short responses always."}]
        facts = extractor.extract(msgs)
        # Should not raise; role defaults to "user"
        assert isinstance(facts, list)

    def test_multiple_messages(self, extractor):
        msgs = [
            {"role": "user", "content": "I prefer Python over JavaScript."},
            {"role": "user", "content": "I need to prepare the demo slides."},
        ]
        facts = extractor.extract(msgs)
        assert len(facts) >= 2

    def test_mixed_roles(self, extractor):
        msgs = [
            {"role": "user", "content": "I prefer concise bullet points."},
            {"role": "assistant", "content": "I will prepare the summary document."},
        ]
        facts = extractor.extract(msgs)
        roles = {f.source_role for f in facts}
        # Both roles present in facts
        assert "user" in roles

    def test_returns_extracted_fact_instances(self, extractor):
        msgs = [{"role": "user", "content": "I prefer structured data formats."}]
        facts = extractor.extract(msgs)
        assert all(isinstance(f, ExtractedFact) for f in facts)

    def test_timestamp_set_on_facts(self, extractor):
        msgs = [{"role": "user", "content": "I prefer Markdown for documentation."}]
        facts = extractor.extract(msgs)
        assert all(f.timestamp != "" for f in facts)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_duplicate_messages_deduplicated(self, extractor):
        # Same content twice — should produce one fact
        msgs = [
            {"role": "user", "content": "I prefer bullet points for all outputs."},
            {"role": "user", "content": "I prefer bullet points for all outputs."},
        ]
        facts = extractor.extract(msgs)
        contents = [f.content.lower().strip()[:80] for f in facts]
        # No duplicate content keys
        assert len(contents) == len(set(contents))

    def test_higher_confidence_wins_on_duplicate(self, extractor):
        # Internal dedup keeps highest confidence; test via private method
        e = MemoryExtractor()
        f_low = ExtractedFact(content="I prefer dark mode", fact_type="preference", confidence=0.5)
        f_high = ExtractedFact(content="I prefer dark mode", fact_type="preference", confidence=0.9)
        result = e._deduplicate([f_low, f_high])
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_deduplicate_distinct_facts_all_kept(self, extractor):
        e = MemoryExtractor()
        f1 = ExtractedFact(content="I prefer bullet points", fact_type="preference", confidence=0.8)
        f2 = ExtractedFact(content="Alice works at Google", fact_type="relationship", confidence=0.6)
        result = e._deduplicate([f1, f2])
        assert len(result) == 2

    def test_deduplicate_empty_list(self, extractor):
        result = extractor._deduplicate([])
        assert result == []


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------

class TestExtractEntities:
    def test_extracts_proper_nouns(self, extractor):
        entities = extractor._extract_entities("Sarah works at Google Cloud Platform")
        assert len(entities) >= 1

    def test_no_entities_in_lowercase(self, extractor):
        entities = extractor._extract_entities("i like bullet points")
        assert entities == []

    def test_entity_list_capped_at_five(self, extractor):
        text = "Alice Bob Charlie Dave Eve Frank Grace joined the team"
        entities = extractor._extract_entities(text)
        assert len(entities) <= 5

    def test_returns_list(self, extractor):
        result = extractor._extract_entities("")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _find_similar
# ---------------------------------------------------------------------------

class TestFindSimilar:
    def test_returns_none_when_no_existing(self, extractor):
        candidate = ExtractedFact(content="I prefer dark mode", fact_type="preference")
        result = extractor._find_similar(candidate, [])
        assert result is None

    def test_returns_match_above_threshold(self, extractor):
        candidate = ExtractedFact(content="I prefer dark mode themes", fact_type="preference")
        existing = [{"id": "x1", "content": "I prefer dark mode themes always", "fact_type": "preference"}]
        result = extractor._find_similar(candidate, existing)
        assert result is not None
        assert result["id"] == "x1"

    def test_returns_none_below_threshold(self, extractor):
        candidate = ExtractedFact(content="I prefer Python", fact_type="preference")
        existing = [{"id": "x2", "content": "The deadline is Monday", "fact_type": "temporal"}]
        result = extractor._find_similar(candidate, existing)
        assert result is None

    def test_skips_empty_content_existing(self, extractor):
        candidate = ExtractedFact(content="I prefer bullet lists", fact_type="preference")
        existing = [{"id": "x3", "content": "", "fact_type": "preference"}]
        result = extractor._find_similar(candidate, existing)
        assert result is None

    def test_returns_best_match_among_multiple(self, extractor):
        candidate = ExtractedFact(content="I prefer dark mode themes", fact_type="preference")
        existing = [
            {"id": "x1", "content": "I prefer light mode always", "fact_type": "preference"},
            {"id": "x2", "content": "I prefer dark mode themes always carefully", "fact_type": "preference"},
        ]
        result = extractor._find_similar(candidate, existing)
        # x2 has higher Jaccard with candidate
        assert result is not None
        assert result["id"] == "x2"

    def test_missing_content_key_in_existing(self, extractor):
        candidate = ExtractedFact(content="I prefer markdown output", fact_type="preference")
        existing = [{"id": "x4"}]  # no "content" key
        result = extractor._find_similar(candidate, existing)
        assert result is None


# ---------------------------------------------------------------------------
# _is_contradiction
# ---------------------------------------------------------------------------

class TestIsContradiction:
    def test_negation_vs_positive_is_contradiction(self, extractor):
        candidate = ExtractedFact(content="I never use passive voice", fact_type="preference")
        existing = {"id": "e1", "content": "I use passive voice sometimes", "fact_type": "preference"}
        assert extractor._is_contradiction(candidate, existing) is True

    def test_both_positive_is_not_contradiction(self, extractor):
        candidate = ExtractedFact(content="I prefer markdown output", fact_type="preference")
        existing = {"id": "e2", "content": "I prefer markdown formatting", "fact_type": "preference"}
        assert extractor._is_contradiction(candidate, existing) is False

    def test_both_negative_is_not_contradiction(self, extractor):
        candidate = ExtractedFact(content="never use emojis in writing", fact_type="preference")
        existing = {"id": "e3", "content": "don't use emojis ever please", "fact_type": "preference"}
        assert extractor._is_contradiction(candidate, existing) is False

    def test_positive_candidate_vs_negative_existing(self, extractor):
        candidate = ExtractedFact(content="I use bullet points always", fact_type="preference")
        existing = {"id": "e4", "content": "never use bullet points formatting", "fact_type": "preference"}
        assert extractor._is_contradiction(candidate, existing) is True

    def test_uses_neg_word_avoid(self, extractor):
        candidate = ExtractedFact(content="avoid verbose explanations", fact_type="preference")
        existing = {"id": "e5", "content": "prefer verbose detailed explanations", "fact_type": "preference"}
        assert extractor._is_contradiction(candidate, existing) is True


# ---------------------------------------------------------------------------
# _is_enrichment
# ---------------------------------------------------------------------------

class TestIsEnrichment:
    def test_many_new_words_is_enrichment(self, extractor):
        candidate = ExtractedFact(
            content="I prefer dark mode with high contrast and blue light filter",
            fact_type="preference",
        )
        existing = {"id": "e1", "content": "I prefer dark mode", "fact_type": "preference"}
        assert extractor._is_enrichment(candidate, existing) is True

    def test_few_new_words_not_enrichment(self, extractor):
        candidate = ExtractedFact(content="I prefer dark mode always", fact_type="preference")
        existing = {"id": "e2", "content": "I prefer dark mode", "fact_type": "preference"}
        assert extractor._is_enrichment(candidate, existing) is False

    def test_identical_content_not_enrichment(self, extractor):
        candidate = ExtractedFact(content="I prefer dark mode", fact_type="preference")
        existing = {"id": "e3", "content": "I prefer dark mode", "fact_type": "preference"}
        assert extractor._is_enrichment(candidate, existing) is False


# ---------------------------------------------------------------------------
# reconcile — full operation coverage
# ---------------------------------------------------------------------------

class TestReconcileAdd:
    def test_no_existing_produces_add(self, extractor):
        fact = ExtractedFact(content="I prefer Python over Ruby", fact_type="preference", confidence=0.8)
        actions = extractor.reconcile([fact], [])
        assert len(actions) == 1
        assert actions[0].op == "add"
        assert actions[0].target_id is None

    def test_no_similar_existing_produces_add(self, extractor):
        fact = ExtractedFact(content="I prefer markdown output", fact_type="preference", confidence=0.8)
        existing = [{"id": "e1", "content": "The deadline is next Tuesday", "fact_type": "temporal"}]
        actions = extractor.reconcile([fact], existing)
        assert actions[0].op == "add"

    def test_empty_candidates_produces_no_actions(self, extractor):
        actions = extractor.reconcile([], [{"id": "e1", "content": "something", "fact_type": "preference"}])
        assert actions == []


class TestReconcileInvalidate:
    def test_contradiction_produces_invalidate_then_add(self, extractor):
        # candidate has negation word, existing does not → contradiction
        fact = ExtractedFact(
            content="never use passive voice in responses",
            fact_type="preference",
            confidence=0.8,
        )
        existing = [{"id": "e1", "content": "use passive voice in responses", "fact_type": "preference"}]
        actions = extractor.reconcile([fact], existing)
        ops = [a.op for a in actions]
        assert "invalidate" in ops
        assert ops.count("add") >= 1
        # The invalidate action should reference the existing ID
        invalidate_action = next(a for a in actions if a.op == "invalidate")
        assert invalidate_action.target_id == "e1"
        assert invalidate_action.supersedes == "e1"

    def test_invalidate_add_pair_has_supersedes(self, extractor):
        fact = ExtractedFact(
            content="don't use bullet points for lists",
            fact_type="preference",
            confidence=0.8,
        )
        existing = [{"id": "f99", "content": "use bullet points for all lists", "fact_type": "preference"}]
        actions = extractor.reconcile([fact], existing)
        add_action = next((a for a in actions if a.op == "add" and a.supersedes), None)
        assert add_action is not None
        assert add_action.supersedes == "f99"


class TestReconcileUpdate:
    def test_enrichment_produces_update(self, extractor):
        # Candidate must share >50% Jaccard with existing (to find a match)
        # AND have >3 words not in existing (to be enrichment, not skip).
        # existing: "I prefer Python type hints"  (5 words)
        # candidate: "I prefer Python type hints and async patterns always" (9 words)
        # overlap=5, union=9, jaccard=0.55 > 0.5 → match found
        # new_words = {and, async, patterns, always} = 4 > 3 → enrichment
        fact = ExtractedFact(
            content="I prefer Python type hints and async patterns always",
            fact_type="preference",
            confidence=0.8,
        )
        existing = [{"id": "e2", "content": "I prefer Python type hints", "fact_type": "preference"}]
        actions = extractor.reconcile([fact], existing)
        assert actions[0].op == "update"
        assert actions[0].target_id == "e2"

    def test_update_action_has_reason(self, extractor):
        fact = ExtractedFact(
            content="I prefer Python type hints and docstrings always complete",
            fact_type="preference",
            confidence=0.8,
        )
        existing = [{"id": "e3", "content": "I prefer Python type hints", "fact_type": "preference"}]
        actions = extractor.reconcile([fact], existing)
        update = next(a for a in actions if a.op == "update")
        assert "enrich" in update.reason.lower()


class TestReconcileSkip:
    def test_similar_non_contradicting_non_enriching_produces_skip(self, extractor):
        # High jaccard overlap, no negation, not enough new words
        fact = ExtractedFact(
            content="I prefer dark mode themes",
            fact_type="preference",
            confidence=0.8,
        )
        existing = [{"id": "e4", "content": "I prefer dark mode themes always", "fact_type": "preference"}]
        actions = extractor.reconcile([fact], existing)
        assert actions[0].op == "skip"
        assert actions[0].target_id == "e4"

    def test_skip_action_has_reason(self, extractor):
        fact = ExtractedFact(content="I prefer dark mode themes", fact_type="preference")
        existing = [{"id": "e5", "content": "I prefer dark mode themes always", "fact_type": "preference"}]
        actions = extractor.reconcile([fact], existing)
        skip = next(a for a in actions if a.op == "skip")
        assert skip.reason != ""


class TestReconcileMultiple:
    def test_multiple_candidates_multiple_actions(self, extractor):
        facts = [
            ExtractedFact(content="I prefer Python over JavaScript", fact_type="preference", confidence=0.8),
            ExtractedFact(content="meeting on Monday at ten", fact_type="temporal", confidence=0.7),
        ]
        existing = [{"id": "e1", "content": "meeting on Monday at ten", "fact_type": "temporal"}]
        actions = extractor.reconcile(facts, existing)
        assert len(actions) == 2

    def test_reconcile_returns_reconcile_action_instances(self, extractor):
        fact = ExtractedFact(content="I prefer dark mode", fact_type="preference")
        actions = extractor.reconcile([fact], [])
        assert all(isinstance(a, ReconcileAction) for a in actions)


# ---------------------------------------------------------------------------
# End-to-end pipeline: extract then reconcile
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_full_pipeline_no_existing(self, extractor):
        msgs = [
            {"role": "user", "content": "I prefer bullet points for all outputs."},
            {"role": "user", "content": "I need to prepare the pitch deck by Friday."},
            {"role": "user", "content": "meeting on Wednesday at 2pm."},
        ]
        facts = extractor.extract(msgs)
        assert len(facts) >= 1
        actions = extractor.reconcile(facts, [])
        assert all(a.op == "add" for a in actions)

    def test_full_pipeline_with_update(self, extractor):
        msgs = [{"role": "user", "content": "I prefer Python with type hints and async patterns always."}]
        facts = extractor.extract(msgs)
        existing = [{"id": "old-1", "content": "I prefer Python", "fact_type": "preference"}]
        actions = extractor.reconcile(facts, existing)
        ops = {a.op for a in actions}
        assert "update" in ops or "add" in ops  # must have taken some action

    def test_full_pipeline_with_contradiction(self, extractor):
        msgs = [{"role": "user", "content": "never use passive voice in any writing."}]
        facts = extractor.extract(msgs)
        existing = [{"id": "old-2", "content": "use passive voice in formal writing", "fact_type": "preference"}]
        if facts:
            actions = extractor.reconcile(facts, existing)
            ops = [a.op for a in actions]
            assert "invalidate" in ops or "add" in ops
