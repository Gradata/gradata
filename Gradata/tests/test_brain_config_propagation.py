from __future__ import annotations

import json
import os

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons


def _long_lessons(count: int = 12) -> list[Lesson]:
    long_tail = "alpha beta gamma " * 80
    return [
        Lesson(
            date="2026-05-06",
            state=LessonState.RULE,
            confidence=0.95,
            category="CODE",
            description=f"rule {i} {long_tail}",
        )
        for i in range(count)
    ]


def test_brain_config_max_recall_tokens_reaches_all_injection_paths(tmp_path, monkeypatch):
    max_tokens = 500
    max_chars = max_tokens * 4
    (tmp_path / "brain-config.json").write_text(
        json.dumps({"max_recall_tokens": max_tokens, "ranker": "flat"}),
        encoding="utf-8",
    )
    (tmp_path / "lessons.md").write_text(format_lessons(_long_lessons()), encoding="utf-8")
    monkeypatch.setenv("BRAIN_DIR", str(tmp_path))
    monkeypatch.setenv("GRADATA_BRAIN_DIR", str(tmp_path))
    monkeypatch.setenv("GRADATA_JIT_ENABLED", "1")
    monkeypatch.setenv("GRADATA_SUBAGENT_DEDUP", "0")

    from gradata.hooks import agent_precontext, inject_brain_rules, jit_inject
    from gradata.middleware import RuleSource, build_brain_rules_block

    session_result = inject_brain_rules.main({"session_type": "alpha beta", "session_number": 1})
    agent_result = agent_precontext.main(
        {"tool_name": "Agent", "tool_input": {"subagent_type": "code", "prompt": "fix code"}}
    )
    jit_result = jit_inject.main({"prompt": "alpha beta gamma " * 10})
    middleware_block = build_brain_rules_block(RuleSource(brain_path=tmp_path))

    assert session_result is not None
    assert agent_result is not None
    assert jit_result is not None
    assert len(session_result["result"]) <= max_chars
    assert len(agent_result["result"]) <= max_chars
    assert len(jit_result["result"]) <= max_chars
    assert len(middleware_block) <= max_chars
    assert os.environ["GRADATA_JIT_ENABLED"] == "1"
