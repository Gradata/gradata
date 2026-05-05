"""Tests for Disposition and DispositionTracker in behavioral_engine."""

import pytest

from gradata.enhancements.behavioral_engine import Disposition, DispositionTracker

# ---------------------------------------------------------------------------
# Disposition defaults
# ---------------------------------------------------------------------------


class TestDispositionDefaults:
    def test_default_values(self):
        d = Disposition()
        assert d.skepticism == 3.0
        assert d.literalism == 3.0
        assert d.empathy == 3.0

    def test_custom_construction(self):
        d = Disposition(skepticism=1.5, literalism=4.5, empathy=2.0)
        assert d.skepticism == 1.5
        assert d.literalism == 4.5
        assert d.empathy == 2.0


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------


class TestDispositionClamp:
    def test_clamp_upper_boundary(self):
        d = Disposition(skepticism=6.0, literalism=10.0, empathy=5.5)
        d.clamp()
        assert d.skepticism == 5.0
        assert d.literalism == 5.0
        assert d.empathy == 5.0

    def test_clamp_lower_boundary(self):
        d = Disposition(skepticism=0.0, literalism=-1.0, empathy=0.5)
        d.clamp()
        assert d.skepticism == 1.0
        assert d.literalism == 1.0
        assert d.empathy == 1.0

    def test_clamp_at_exact_boundaries(self):
        d = Disposition(skepticism=1.0, literalism=5.0, empathy=3.0)
        d.clamp()
        assert d.skepticism == 1.0
        assert d.literalism == 5.0
        assert d.empathy == 3.0

    def test_clamp_midrange_unchanged(self):
        d = Disposition(skepticism=2.5, literalism=3.5, empathy=4.0)
        d.clamp()
        assert d.skepticism == 2.5
        assert d.literalism == 3.5
        assert d.empathy == 4.0


# ---------------------------------------------------------------------------
# behavioral_instructions
# ---------------------------------------------------------------------------


class TestBehavioralInstructions:
    def test_all_neutral_returns_empty(self):
        d = Disposition(skepticism=3.0, literalism=3.0, empathy=3.0)
        assert d.behavioral_instructions() == []

    def test_high_skepticism(self):
        d = Disposition(skepticism=4.0)
        instructions = d.behavioral_instructions()
        assert any("Cross-reference" in i for i in instructions)

    def test_low_skepticism(self):
        d = Disposition(skepticism=2.0)
        instructions = d.behavioral_instructions()
        assert any("Trust provided context" in i for i in instructions)

    def test_high_literalism(self):
        d = Disposition(literalism=4.0)
        instructions = d.behavioral_instructions()
        assert any("explicitly stated facts" in i for i in instructions)

    def test_low_literalism(self):
        d = Disposition(literalism=2.0)
        instructions = d.behavioral_instructions()
        assert any("Synthesize and infer" in i for i in instructions)

    def test_high_empathy(self):
        d = Disposition(empathy=4.0)
        instructions = d.behavioral_instructions()
        assert any("emotional context" in i for i in instructions)

    def test_low_empathy(self):
        d = Disposition(empathy=2.0)
        instructions = d.behavioral_instructions()
        assert any("factual and clinical" in i for i in instructions)

    def test_boundary_3_produces_no_instruction(self):
        # 3.0 is neutral — neither >= 4.0 nor <= 2.0
        d = Disposition(skepticism=3.0, literalism=3.0, empathy=3.0)
        assert d.behavioral_instructions() == []

    def test_boundary_3_5_produces_no_instruction(self):
        d = Disposition(skepticism=3.5, literalism=3.5, empathy=3.5)
        assert d.behavioral_instructions() == []

    def test_multiple_instructions_combined(self):
        d = Disposition(skepticism=4.5, literalism=1.5, empathy=4.5)
        instructions = d.behavioral_instructions()
        assert len(instructions) == 3


# ---------------------------------------------------------------------------
# format_for_prompt
# ---------------------------------------------------------------------------


class TestFormatForPrompt:
    def test_format_contains_all_scales(self):
        d = Disposition(skepticism=2.0, literalism=4.0, empathy=3.0)
        output = d.format_for_prompt()
        assert "skepticism=2.0" in output
        assert "literalism=4.0" in output
        assert "empathy=3.0" in output

    def test_format_neutral_no_instructions(self):
        d = Disposition()
        output = d.format_for_prompt()
        lines = output.strip().splitlines()
        assert len(lines) == 1
        assert "Disposition:" in lines[0]

    def test_format_includes_instructions_when_active(self):
        d = Disposition(skepticism=4.5)
        output = d.format_for_prompt()
        assert "  - " in output
        assert "Cross-reference" in output

    def test_format_decimal_precision(self):
        d = Disposition(skepticism=3.0, literalism=3.0, empathy=3.0)
        output = d.format_for_prompt()
        assert "skepticism=3.0" in output


# ---------------------------------------------------------------------------
# DispositionTracker
# ---------------------------------------------------------------------------


class TestDispositionTrackerBasics:
    def test_get_creates_default_on_first_access(self):
        tracker = DispositionTracker()
        d = tracker.get("sales")
        assert d.skepticism == 3.0
        assert d.literalism == 3.0
        assert d.empathy == 3.0

    def test_get_returns_same_object_on_second_call(self):
        tracker = DispositionTracker()
        d1 = tracker.get("sales")
        d2 = tracker.get("sales")
        assert d1 is d2

    def test_get_default_domain_is_global(self):
        tracker = DispositionTracker()
        tracker.get()
        assert "global" in tracker.domains

    def test_domains_property_lists_all(self):
        tracker = DispositionTracker()
        tracker.get("sales")
        tracker.get("ops")
        assert set(tracker.domains) == {"sales", "ops"}


class TestDispositionTrackerUpdateFromCorrection:
    def test_known_category_updates_disposition(self):
        tracker = DispositionTracker()
        disp = tracker.update_from_correction("sales", "too_trusting", "minor")
        assert disp.skepticism > 3.0

    def test_unknown_category_returns_unchanged(self):
        tracker = DispositionTracker()
        disp_before = tracker.get("sales")
        original_skepticism = disp_before.skepticism
        disp_after = tracker.update_from_correction("sales", "nonexistent_category", "major")
        assert disp_after.skepticism == original_skepticism

    def test_severity_scaling_trivial_vs_rewrite(self):
        tracker_trivial = DispositionTracker()
        tracker_rewrite = DispositionTracker()
        tracker_trivial.update_from_correction("x", "too_trusting", "trivial")
        tracker_rewrite.update_from_correction("x", "too_trusting", "rewrite")
        assert tracker_rewrite.get("x").skepticism > tracker_trivial.get("x").skepticism

    def test_clamping_applied_after_update(self):
        tracker = DispositionTracker()
        # Push skepticism to max by repeated corrections
        for _ in range(30):
            tracker.update_from_correction("x", "too_trusting", "rewrite")
        assert tracker.get("x").skepticism <= 5.0

    def test_opposite_corrections_converge(self):
        tracker = DispositionTracker()
        tracker.update_from_correction("x", "too_trusting", "moderate")
        tracker.update_from_correction("x", "too_skeptical", "moderate")
        # Should be back near 3.0
        assert abs(tracker.get("x").skepticism - 3.0) < 0.01

    def test_all_known_categories_update_without_error(self):
        categories = [
            "too_literal",
            "too_inferential",
            "too_trusting",
            "too_skeptical",
            "too_cold",
            "too_warm",
            "hallucination",
            "missed_context",
        ]
        tracker = DispositionTracker()
        for cat in categories:
            tracker.update_from_correction("global", cat, "minor")

    def test_multi_domain_isolation(self):
        tracker = DispositionTracker()
        tracker.update_from_correction("sales", "too_trusting", "major")
        tracker.update_from_correction("ops", "too_cold", "major")
        sales_disp = tracker.get("sales")
        ops_disp = tracker.get("ops")
        assert sales_disp.skepticism != 3.0
        assert ops_disp.empathy != 3.0
        # Cross-contamination check
        assert sales_disp.empathy == 3.0
        assert ops_disp.skepticism == 3.0

    @pytest.mark.parametrize(
        "severity,expected_delta",
        [
            ("trivial", 0.1),
            ("minor", 0.15),
            ("moderate", 0.2),
            ("major", 0.25),
            ("rewrite", 0.3),
        ],
    )
    def test_severity_deltas_correct(self, severity, expected_delta):
        tracker = DispositionTracker()
        disp = tracker.update_from_correction("x", "too_trusting", severity)
        assert abs(disp.skepticism - (3.0 + expected_delta)) < 1e-9

    def test_unknown_severity_uses_fallback(self):
        tracker = DispositionTracker()
        # "unknown" severity should fall back to 0.15 (minor default)
        disp = tracker.update_from_correction("x", "too_trusting", "unknown_severity")
        assert abs(disp.skepticism - 3.15) < 1e-9


# ---------------------------------------------------------------------------
# to_dict / from_dict roundtrip
# ---------------------------------------------------------------------------


class TestDispositionTrackerSerialization:
    def test_to_dict_structure(self):
        tracker = DispositionTracker()
        tracker.get("sales")
        tracker.get("ops")
        d = tracker.to_dict()
        assert "sales" in d
        assert "ops" in d
        assert set(d["sales"].keys()) == {"skepticism", "literalism", "empathy"}

    def test_to_dict_reflects_updates(self):
        tracker = DispositionTracker()
        tracker.update_from_correction("sales", "too_trusting", "major")
        d = tracker.to_dict()
        assert d["sales"]["skepticism"] == pytest.approx(3.25)

    def test_from_dict_roundtrip(self):
        tracker = DispositionTracker()
        tracker.update_from_correction("sales", "too_trusting", "major")
        tracker.update_from_correction("ops", "too_cold", "minor")
        data = tracker.to_dict()

        restored = DispositionTracker.from_dict(data)
        assert restored.get("sales").skepticism == pytest.approx(tracker.get("sales").skepticism)
        assert restored.get("ops").empathy == pytest.approx(tracker.get("ops").empathy)

    def test_from_dict_missing_keys_use_defaults(self):
        data = {"sales": {"skepticism": 4.0}}  # literalism and empathy missing
        tracker = DispositionTracker.from_dict(data)
        d = tracker.get("sales")
        assert d.skepticism == 4.0
        assert d.literalism == 3.0
        assert d.empathy == 3.0

    def test_from_dict_empty(self):
        tracker = DispositionTracker.from_dict({})
        assert tracker.domains == []

    def test_roundtrip_with_custom_values(self):
        tracker = DispositionTracker()
        tracker._dispositions["test"] = Disposition(skepticism=1.5, literalism=4.8, empathy=2.2)
        restored = DispositionTracker.from_dict(tracker.to_dict())
        d = restored.get("test")
        assert d.skepticism == pytest.approx(1.5)
        assert d.literalism == pytest.approx(4.8)
        assert d.empathy == pytest.approx(2.2)
