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
