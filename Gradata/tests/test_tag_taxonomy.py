"""Tests for _tag_taxonomy — cognitive load tag and enrichment."""

from gradata._tag_taxonomy import TAXONOMY, validate_tag, enrich_tags


class TestCognitiveLoadTaxonomy:
    def test_cognitive_load_in_taxonomy(self):
        assert "cognitive_load" in TAXONOMY
        spec = TAXONOMY["cognitive_load"]
        assert spec["mode"] == "closed"
        assert spec["values"] == {"intrinsic", "extraneous", "germane"}

    def test_validate_valid(self):
        valid, msg = validate_tag("cognitive_load:intrinsic")
        assert valid
        valid, msg = validate_tag("cognitive_load:extraneous")
        assert valid
        valid, msg = validate_tag("cognitive_load:germane")
        assert valid

    def test_validate_invalid(self):
        valid, msg = validate_tag("cognitive_load:bogus")
        assert not valid
        assert "Invalid cognitive_load value" in msg

    def test_enrich_factual_is_intrinsic(self):
        tags = enrich_tags([], event_type="CORRECTION", data={"category": "FACTUAL"})
        assert "cognitive_load:intrinsic" in tags

    def test_enrich_style_is_extraneous(self):
        tags = enrich_tags([], event_type="CORRECTION", data={"category": "STYLE"})
        assert "cognitive_load:extraneous" in tags

    def test_enrich_process_is_germane(self):
        tags = enrich_tags([], event_type="CORRECTION", data={"category": "PROCESS"})
        assert "cognitive_load:germane" in tags

    def test_enrich_does_not_override_explicit(self):
        tags = enrich_tags(
            ["cognitive_load:extraneous"],
            event_type="CORRECTION",
            data={"category": "FACTUAL"},
        )
        # Should keep explicit value, not add intrinsic
        assert tags.count("cognitive_load:extraneous") == 1
        assert "cognitive_load:intrinsic" not in tags


class TestRuleEventEnrichment:
    def test_rule_graduated_auto_tags_category(self):
        tags = enrich_tags([], event_type="RULE_GRADUATED", data={"category": "style"})
        assert "category:STYLE" in tags

    def test_rule_override_auto_tags_category(self):
        tags = enrich_tags([], event_type="RULE_OVERRIDE", data={"category": "structure"})
        assert "category:STRUCTURE" in tags

    def test_rule_conflict_auto_tags_reason_and_category(self):
        tags = enrich_tags(
            [],
            event_type="RULE_CONFLICT",
            data={"category": "style", "reason": "confidence_drift"},
        )
        assert "category:STYLE" in tags
        assert "conflict_reason:confidence_drift" in tags

    def test_rule_conflict_resolved_auto_tags_category_only(self):
        tags = enrich_tags(
            [],
            event_type="RULE_CONFLICT_RESOLVED",
            data={"category": "content"},
        )
        assert "category:CONTENT" in tags
        # RULE_CONFLICT_RESOLVED has no conflict_reason field to surface.
        assert not any(t.startswith("conflict_reason:") for t in tags)

    def test_conflict_reason_validator_accepts_known_values(self):
        ok, _ = validate_tag("conflict_reason:confidence_drift")
        assert ok
        ok, _ = validate_tag("conflict_reason:state_disagreement")
        assert ok

    def test_conflict_reason_validator_rejects_unknown_values(self):
        ok, msg = validate_tag("conflict_reason:cosmic_ray")
        assert not ok
        assert "Invalid conflict_reason value" in msg

    def test_enrich_keeps_explicit_category(self):
        # If the caller already tagged category, enrichment must not duplicate.
        tags = enrich_tags(
            ["category:CUSTOM_FROM_CALLER"],
            event_type="RULE_GRADUATED",
            data={"category": "style"},
        )
        assert tags.count("category:CUSTOM_FROM_CALLER") == 1
        assert "category:STYLE" not in tags
