"""Tests for Meta-Harness D synthesized prompt injection."""

from __future__ import annotations

from gradata.enhancements.prompt_synthesizer import (
    DEFAULT_BUDGET_TOKENS,
    SLOT_ORDER,
    SynthesizedPrompt,
    classify_slot,
    extract_anchors,
    synthesize_brain_injection,
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
    out = synthesize_rules_prompt(
        [
            _rule("DRAFTING", "never attribute quotes prospects didn't say", "a1f92b3c4d5e"),
        ]
    )
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
    rules = [_rule("DRAFTING", f"rule number {i}", f"{i:04x}00000000") for i in range(10)]
    out = synthesize_rules_prompt(rules, max_per_category=3)
    # 3 anchors max from the capped category
    assert len(out.anchors_used) == 3


def test_token_saving_vs_flat_list():
    """Sanity check — synthesized form fits in fewer tokens than the
    equivalent ``[RULE:0.92] {cat}: {desc}`` flat list it replaces."""
    rules = [_rule("DRAFTING", f"directive {i}", f"{i:04x}abcdef01") for i in range(8)]
    out = synthesize_rules_prompt(rules, max_per_category=8)

    flat = "\n".join(
        f"[RULE:0.92] {r['category']}: {r['description']} r:{r['rule_id'][:4]}" for r in rules
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


# ---------------------------------------------------------------------------
# Slot classification + slot-grouped (brain-injection) synthesis
# ---------------------------------------------------------------------------


def test_classify_slot_explicit_wins():
    assert classify_slot({"slot": "tone", "category": "DRAFTING"}) == "tone"


def test_classify_slot_example_pair_is_examples():
    item = {
        "category": "DRAFTING",
        "description": "prefer concise tone",
        "example_draft": "before",
        "example_corrected": "after",
    }
    assert classify_slot(item) == "examples"


def test_classify_slot_category_mapping():
    assert classify_slot({"category": "DRAFTING"}) == "format"
    assert classify_slot({"category": "TONE"}) == "tone"
    assert classify_slot({"category": "PROCESS"}) == "task"
    assert classify_slot({"category": "ACCURACY"}) == "context"
    # Hyphen/underscore variants both resolve.
    assert classify_slot({"category": "EXECUTION-DISCIPLINE"}) == "task"
    assert classify_slot({"category": "DATA_INTEGRITY"}) == "context"


def test_classify_slot_unknown_category_defaults_to_context():
    assert classify_slot({"category": "ZEBRA"}) == "context"


def test_brain_injection_empty_is_empty():
    out = synthesize_brain_injection([])
    assert isinstance(out, SynthesizedPrompt)
    assert out.text == ""
    assert out.anchors_used == []


def test_brain_injection_orders_slots_per_preston():
    rules = [
        _rule("TONE", "lead with empathy", "c3d41a2b3c4d"),
        _rule("DRAFTING", "tight copy under 150 words", "a1f92b3c4d5e"),
        _rule("PROCESS", "plan before implementing", "b2c31a2b3c4d"),
    ]
    out = synthesize_brain_injection(rules)
    # Task comes before Format which comes before Tone.
    task_idx = out.text.index("Task:")
    format_idx = out.text.index("Format:")
    tone_idx = out.text.index("Tone:")
    assert task_idx < format_idx < tone_idx
    # All anchors preserved.
    for anchor in ("a1f9", "b2c3", "c3d4"):
        assert f"r:{anchor}" in out.text


def test_brain_injection_persona_baseline_seeded():
    rules = [_rule("PERSONA", "never attribute unverified quotes", "d4e51a2b3c4d")]
    baseline = "Direct, consultative, curious tone. Never em dashes."
    out = synthesize_brain_injection(rules, persona_baseline=baseline)
    assert "Persona:" in out.text
    assert "Direct, consultative" in out.text
    assert "Overrides:" in out.text
    assert "r:d4e5" in out.text


def test_brain_injection_persona_baseline_without_rules_still_emits():
    baseline = "Empathetic, playbook-driven."
    out = synthesize_brain_injection([], persona_baseline=baseline)
    assert "Persona: Empathetic, playbook-driven." in out.text


def test_brain_injection_loads_persona_from_path(tmp_path):
    soul = tmp_path / "soul.md"
    soul.write_text(
        "# Voice\n\n> ignored blockquote\n\n* Direct, not aggressive.\n* No em dashes anywhere.\n",
        encoding="utf-8",
    )
    out = synthesize_brain_injection([], persona_baseline=soul)
    assert "Direct, not aggressive." in out.text
    assert "No em dashes anywhere." in out.text
    # Header and blockquote stripped.
    assert "# Voice" not in out.text
    assert "ignored blockquote" not in out.text


def test_brain_injection_missing_persona_path_is_silent(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    out = synthesize_brain_injection(
        [_rule("DRAFTING", "concise", "a1f92b3c4d5e")],
        persona_baseline=missing,
    )
    # Falls back gracefully — no Persona block, format block still emitted.
    assert "Persona:" not in out.text
    assert "Format:" in out.text


def test_brain_injection_default_budget_respects_env(monkeypatch):
    monkeypatch.delenv("GRADATA_SYNTH_BUDGET", raising=False)
    assert DEFAULT_BUDGET_TOKENS == 400

    monkeypatch.setenv("GRADATA_SYNTH_BUDGET", "50")
    # Build enough rules to blow past 50 tokens.
    rules = [
        _rule(cat, f"rule {i} with some padding text here", f"{i:04x}{i:04x}{i:04x}")
        for i, cat in enumerate(["PROCESS", "ACCURACY", "DRAFTING", "TONE", "PERSONA", "RESEARCH"])
    ]
    out = synthesize_brain_injection(rules)
    # Under budget: token count estimate fits.
    assert out.token_count_estimate() <= 50


def test_brain_injection_budget_drops_lowest_priority_first():
    rules = [
        _rule("PROCESS", "task rule lorem ipsum dolor", "aaaa11112222"),
        _rule("TONE", "tone rule lorem ipsum dolor sit amet", "bbbb11112222"),
    ]
    # Squeeze budget so only one slot fits: task sentence is ~7 tokens,
    # tone sentence is ~8 — budget 10 keeps task, drops tone.
    out = synthesize_brain_injection(rules, budget_tokens=10)
    # Task (high priority) survives, Tone (low priority) dropped.
    assert "Task:" in out.text
    assert "Tone:" not in out.text
    # Only task anchor retained.
    assert "aaaa" in out.anchors_used
    assert "bbbb" not in out.anchors_used


def test_brain_injection_examples_slot_triggered_by_example_fields():
    rules = [
        {
            "category": "DRAFTING",
            "description": "prefer short subject lines",
            "rule_id": "e5e51a2b3c4d",
            "example_draft": "Quick chat about growth",
            "example_corrected": "Chat?",
        }
    ]
    out = synthesize_brain_injection(rules)
    assert "Examples:" in out.text
    assert "Format:" not in out.text


def test_brain_injection_accepts_lesson_like_objects():
    class FakeLesson:
        category = "TONE"
        description = "be curious"
        slot = "tone"
        example_draft = None
        example_corrected = None

        def __init__(self, rid: str) -> None:
            self.rule_id = rid

    out = synthesize_brain_injection([FakeLesson("f0f01a2b3c4d")])
    assert "Tone: be curious" in out.text
    assert "r:f0f0" in out.text


def test_brain_injection_max_per_slot_caps():
    rules = [_rule("PROCESS", f"rule {i}", f"{i:04x}00000000") for i in range(6)]
    out = synthesize_brain_injection(rules, max_per_slot=2, budget_tokens=1000)
    # Only two task rules rendered.
    assert out.text.count("rule ") == 2


def test_slot_order_is_preston_rhodes():
    assert SLOT_ORDER == ("task", "context", "examples", "persona", "format", "tone")
