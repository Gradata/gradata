"""Tests for CausalChain tracking in the learning pipeline."""

from gradata.enhancements.causal_chains import CausalChain, CausalRelation

# ---------------------------------------------------------------------------
# 1. Add correction_to_rule link and trace back
# ---------------------------------------------------------------------------


def test_trace_rule_origin_correction_to_rule():
    chain = CausalChain()
    chain.add_link("corr-1", "rule-A", CausalRelation.CORRECTION_TO_RULE, strength=0.9)
    origins = chain.trace_rule_origin("rule-A")
    assert len(origins) == 1
    assert origins[0].source_id == "corr-1"
    assert origins[0].relation == CausalRelation.CORRECTION_TO_RULE


# ---------------------------------------------------------------------------
# 2. Add rule_to_behavior link and trace forward
# ---------------------------------------------------------------------------


def test_trace_rule_impact_rule_to_behavior():
    chain = CausalChain()
    chain.add_link("rule-A", "behavior-X", CausalRelation.RULE_TO_BEHAVIOR, strength=0.8)
    impacts = chain.trace_rule_impact("rule-A")
    assert len(impacts) == 1
    assert impacts[0].target_id == "behavior-X"
    assert impacts[0].relation == CausalRelation.RULE_TO_BEHAVIOR


# ---------------------------------------------------------------------------
# 3. Add correction_chain links and find related
# ---------------------------------------------------------------------------


def test_find_correction_chains():
    chain = CausalChain()
    chain.add_link("corr-1", "corr-2", CausalRelation.CORRECTION_CHAIN)
    chain.add_link("corr-3", "corr-1", CausalRelation.CORRECTION_CHAIN)
    # Unrelated link — must not appear
    chain.add_link("corr-4", "corr-5", CausalRelation.CORRECTION_CHAIN)

    related = chain.find_correction_chains("corr-1")
    target_ids = {(l.source_id, l.target_id) for l in related}
    assert ("corr-1", "corr-2") in target_ids
    assert ("corr-3", "corr-1") in target_ids
    assert ("corr-4", "corr-5") not in target_ids


# ---------------------------------------------------------------------------
# 4. get_rule_provenance returns complete picture
# ---------------------------------------------------------------------------


def test_get_rule_provenance():
    chain = CausalChain()
    chain.add_link("corr-1", "rule-A", CausalRelation.CORRECTION_TO_RULE, strength=0.9, session=1)
    chain.add_link("corr-2", "rule-A", CausalRelation.REINFORCEMENT, strength=0.7, session=2)
    chain.add_link("rule-A", "beh-X", CausalRelation.RULE_TO_BEHAVIOR, strength=0.85, session=3)

    prov = chain.get_rule_provenance("rule-A")
    assert prov["rule_id"] == "rule-A"
    assert len(prov["correction_sources"]) == 2
    assert len(prov["behavioral_impacts"]) == 1
    assert prov["total_evidence"] == 3

    source_ids = {s["id"] for s in prov["correction_sources"]}
    assert "corr-1" in source_ids
    assert "corr-2" in source_ids
    assert prov["behavioral_impacts"][0]["id"] == "beh-X"


# ---------------------------------------------------------------------------
# 5. to_list / from_list roundtrip
# ---------------------------------------------------------------------------


def test_roundtrip_serialization():
    chain = CausalChain()
    chain.add_link("corr-1", "rule-A", CausalRelation.CORRECTION_TO_RULE, strength=0.9, session=5)
    chain.add_link("rule-A", "beh-X", CausalRelation.RULE_TO_BEHAVIOR, strength=0.75, session=6)

    data = chain.to_list()
    restored = CausalChain.from_list(data)

    assert restored.link_count == chain.link_count
    restored_data = restored.to_list()
    assert restored_data == data


# ---------------------------------------------------------------------------
# 6. Empty chain returns empty traces
# ---------------------------------------------------------------------------


def test_empty_chain():
    chain = CausalChain()
    assert chain.trace_rule_origin("rule-X") == []
    assert chain.trace_rule_impact("rule-X") == []
    assert chain.find_correction_chains("corr-X") == []
    prov = chain.get_rule_provenance("rule-X")
    assert prov["correction_sources"] == []
    assert prov["behavioral_impacts"] == []
    assert prov["total_evidence"] == 0


# ---------------------------------------------------------------------------
# 7. Multiple links for same rule accumulate
# ---------------------------------------------------------------------------


def test_multiple_links_accumulate():
    chain = CausalChain()
    for i in range(5):
        chain.add_link(f"corr-{i}", "rule-A", CausalRelation.CORRECTION_TO_RULE)
    for j in range(3):
        chain.add_link("rule-A", f"beh-{j}", CausalRelation.RULE_TO_BEHAVIOR)

    assert len(chain.trace_rule_origin("rule-A")) == 5
    assert len(chain.trace_rule_impact("rule-A")) == 3
    assert chain.link_count == 8


# ---------------------------------------------------------------------------
# 8. strength defaults to 1.0
# ---------------------------------------------------------------------------


def test_strength_default():
    chain = CausalChain()
    link = chain.add_link("corr-1", "rule-A", CausalRelation.CORRECTION_TO_RULE)
    assert link.strength == 1.0


# ---------------------------------------------------------------------------
# 9. REINFORCEMENT links appear in trace_rule_origin
# ---------------------------------------------------------------------------


def test_reinforcement_appears_in_origin():
    chain = CausalChain()
    chain.add_link("corr-1", "rule-A", CausalRelation.REINFORCEMENT, strength=0.6)
    origins = chain.trace_rule_origin("rule-A")
    assert len(origins) == 1
    assert origins[0].relation == CausalRelation.REINFORCEMENT


# ---------------------------------------------------------------------------
# 10. from_list uses default strength and session when keys absent
# ---------------------------------------------------------------------------


def test_from_list_defaults():
    data = [
        {
            "source_id": "corr-1",
            "target_id": "rule-A",
            "relation": "correction_to_rule",
            # strength and session omitted intentionally
        }
    ]
    chain = CausalChain.from_list(data)
    link = chain._links[0]
    assert link.strength == 1.0
    assert link.session == 0
