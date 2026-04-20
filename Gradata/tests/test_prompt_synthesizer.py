"""Tests for Meta-Harness D synthesized prompt injection."""
from __future__ import annotations

from gradata.enhancements.prompt_synthesizer import (
    SynthesizedPrompt,
    extract_anchors,
    synthesize_rules_prompt,
)


def _rule(cat: str, desc: str, rid: str) -> dict:
    return {"category": cat, "description": desc, "rule_id": rid}


def test_empty_rules_yields_empty_prompt():
    out = synthesize_rules_prompt([])
    assert isinstance(out, SynthesizedPrompt)
    assert out.text == ""
    assert out.anchors_used == []


def test_single_rule_gets_inline_anchor():
    out = synthesize_rules_prompt([
        _rule("DRAFTING", "never attribute quotes prospects didn't say",
              "a1f92b3c4d5e"),
    ])
    assert "r:a1f9" in out.text
    assert "a1f9" in out.anchors_used
    assert out.anchor_to_rule_id["a1f9"] == "a1f92b3c4d5e"
    assert "Drafting:" in out.text


def test_multi_category_grouping_preserves_all_anchors():
    rules = [
        _rule("DRAFTING", "use writer and critic agents", "a1f92b3c4d5e"),
        _rule("DRAFTING", "never attribute quotes", "b2c31a2b3c4d"),
        _rule("TONE", "start with empathy, not confidence", "c3d41a2b3c4d"),
    ]
    out = synthesize_rules_prompt(rules)
    assert "Drafting:" in out.text
    assert "Tone:" in out.text
    assert "r:a1f9" in out.text
    assert "r:b2c3" in out.text
    assert "r:c3d4" in out.text
    assert len(out.anchors_used) == 3


def test_strips_noise_prefixes():
    rules = [
        _rule("DRAFTING", "User corrected: send plain text emails", "a1f92b3c4d5e"),
        _rule("CODE", "[AUTO] prefer dedicated tools", "b2c31a2b3c4d"),
    ]
    out = synthesize_rules_prompt(rules)
    assert "User corrected:" not in out.text
    assert "[AUTO]" not in out.text
    assert "send plain text emails" in out.text
    assert "prefer dedicated tools" in out.text


def test_max_per_category_caps_output():
    rules = [
        _rule("DRAFTING", f"rule number {i}", f"{i:04x}00000000")
        for i in range(10)
    ]
    out = synthesize_rules_prompt(rules, max_per_category=3)
    # 3 anchors max from the capped category
    assert len(out.anchors_used) == 3


def test_token_saving_vs_flat_list():
    """Sanity check — synthesized form fits in fewer tokens than the
    equivalent ``[RULE:0.92] {cat}: {desc}`` flat list it replaces."""
    rules = [
        _rule("DRAFTING", f"directive {i}", f"{i:04x}abcdef01")
        for i in range(8)
    ]
    out = synthesize_rules_prompt(rules, max_per_category=8)

    flat = "\n".join(
        f"[RULE:0.92] {r['category']}: {r['description']} r:{r['rule_id'][:4]}"
        for r in rules
    )
    # Synthesis should produce fewer tokens than the flat dump.
    assert out.token_count_estimate() < len(flat.split())


def test_extract_anchors_from_synthesized_text():
    rules = [
        _rule("DRAFTING", "rule one", "a1f92b3c4d5e"),
        _rule("TONE", "rule two", "b2c31a2b3c4d"),
    ]
    out = synthesize_rules_prompt(rules)
    anchors = extract_anchors(out.text)
    assert "a1f9" in anchors
    assert "b2c3" in anchors


def test_extract_anchors_handles_trailing_ref_sweep():
    text = "some prose without inline anchors [ref: a1f9,b2c3,c3d4]"
    assert extract_anchors(text) == ["a1f9", "b2c3", "c3d4"]


def test_extract_anchors_dedup_preserves_order():
    text = "r:a1f9 and r:b2c3 and again r:a1f9"
    assert extract_anchors(text) == ["a1f9", "b2c3"]


def test_extract_anchors_empty_string():
    assert extract_anchors("") == []
    assert extract_anchors(None) == []  # type: ignore[arg-type]


def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GRADATA_SYNTHESIZE_WITH_LLM", raising=False)
    calls: list[str] = []

    def fake_llm(s: str) -> str:
        calls.append(s)
        return "LLM OUTPUT"

    rules = [_rule("DRAFTING", "keep diffs small", "a1f92b3c4d5e")]
    out = synthesize_rules_prompt(rules, llm_fn=fake_llm)
    assert calls == []  # llm_fn must not be invoked when env is off
    assert "keep diffs small" in out.text


def test_llm_enabled_passes_stripped_template(monkeypatch):
    monkeypatch.setenv("GRADATA_SYNTHESIZE_WITH_LLM", "1")
    received: list[str] = []

    def fake_llm(s: str) -> str:
        received.append(s)
        return "Rewritten prose form."

    rules = [
        _rule("DRAFTING", "keep diffs small", "a1f92b3c4d5e"),
        _rule("TONE", "lead with empathy", "b2c31a2b3c4d"),
    ]
    out = synthesize_rules_prompt(rules, llm_fn=fake_llm)
    assert len(received) == 1
    # Anchors must have been stripped before handing to the LLM.
    assert "r:a1f9" not in received[0]
    # But anchors must be preserved in the final output (via ref sweep).
    assert "a1f9" in out.text
    assert "b2c3" in out.text
    assert "Rewritten prose" in out.text


def test_llm_failure_falls_back_to_template(monkeypatch):
    monkeypatch.setenv("GRADATA_SYNTHESIZE_WITH_LLM", "1")

    def bad_llm(s: str) -> str:
        raise RuntimeError("transient")

    rules = [_rule("DRAFTING", "keep diffs small", "a1f92b3c4d5e")]
    out = synthesize_rules_prompt(rules, llm_fn=bad_llm)
    # Falls back to template, which still has the inline anchor
    assert "r:a1f9" in out.text
    assert "keep diffs small" in out.text
