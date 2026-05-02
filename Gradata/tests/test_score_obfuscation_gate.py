from __future__ import annotations

import re

from gradata import Brain
from gradata.middleware._core import RuleSource, build_brain_rules_block

_RAW_CONFIDENCE_FLOAT = re.compile(r"(?<![\w.])(?:0(?:\.\d+)?|1(?:\.0+)?)(?![\w.])")


def _assert_no_raw_confidence_float(prompt: str) -> None:
    leaks = _RAW_CONFIDENCE_FLOAT.findall(prompt)
    assert not leaks, f"raw confidence float leaked into prompt-bound text: {prompt}"


def test_apply_brain_rules_prompt_does_not_leak_raw_confidence(tmp_path) -> None:
    brain = Brain.init(
        tmp_path / "brain",
        name="ObfuscationGate",
        domain="Testing",
        embedding="local",
        interactive=False,
    )
    result = brain.add_rule(
        "Prefer concrete dates over relative dates",
        "PROCESS",
        state="RULE",
        confidence=0.95,
    )
    assert result["added"] is True

    prompt = brain.apply_brain_rules("write a status update", max_rules=5)

    assert "<brain-rules>" in prompt
    _assert_no_raw_confidence_float(prompt)


def test_middleware_brain_rules_block_does_not_leak_raw_confidence() -> None:
    source = RuleSource(
        lessons=[
            {
                "state": "RULE",
                "confidence": 0.95,
                "category": "PROCESS",
                "description": "Prefer concrete dates over relative dates",
            },
            {
                "state": "PATTERN",
                "confidence": 0.72,
                "category": "STYLE",
                "description": "Keep summaries short",
            },
        ]
    )

    prompt = build_brain_rules_block(source)

    assert "<brain-rules>" in prompt
    _assert_no_raw_confidence_float(prompt)
