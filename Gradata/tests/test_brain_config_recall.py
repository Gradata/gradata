from __future__ import annotations

import json
from typing import TYPE_CHECKING

from gradata._config import (
    BrainConfig,
    GraduationThresholds,
    current_brain_config,
    reload_config,
)
from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons
from gradata.mcp_tools import gradata_recall

if TYPE_CHECKING:
    from gradata import Brain


def test_brain_config_loads_recall_defaults(tmp_path) -> None:
    (tmp_path / "brain-config.json").write_text(
        json.dumps({"max_recall_tokens": 40, "ranker": "flat"}),
        encoding="utf-8",
    )

    reload_config(tmp_path)

    assert current_brain_config() == BrainConfig(max_recall_tokens=40, ranker="flat")


def test_brain_config_loads_graduation_thresholds(tmp_path) -> None:
    (tmp_path / "brain-config.json").write_text(
        json.dumps(
            {
                "graduation_thresholds": {
                    "min_applications_for_pattern": 4,
                    "min_applications_for_rule": 8,
                    "beta_lb_threshold": 0.82,
                    "beta_lb_min_fires": 7,
                }
            }
        ),
        encoding="utf-8",
    )

    reload_config(tmp_path)

    assert current_brain_config().graduation_thresholds == GraduationThresholds(
        min_applications_for_pattern=4,
        min_applications_for_rule=8,
        beta_lb_threshold=0.82,
        beta_lb_min_fires=7,
    )


def test_gradata_recall_uses_brain_config_default_tokens(tmp_path) -> None:
    lessons = [
        Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="EMAIL",
            description=f"cold email rule {i} with enough text to consume budget",
        )
        for i in range(8)
    ]
    lessons_path = tmp_path / "lessons.md"
    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    (tmp_path / "brain-config.json").write_text(
        json.dumps({"max_recall_tokens": 45, "ranker": "flat"}),
        encoding="utf-8",
    )
    reload_config(tmp_path)

    text = gradata_recall(
        "cold email",
        lessons_path=lessons_path,
        meta_rules_path=tmp_path / "missing.json",
    )

    assert len(text) // 4 <= 45


def test_brain_apply_brain_rules_accepts_config_overrides(fresh_brain: Brain) -> None:
    lessons = [
        Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.95,
            category="EMAIL",
            description="cold email concise rule",
        )
    ]
    (fresh_brain.dir / "lessons.md").write_text(format_lessons(lessons), encoding="utf-8")

    text = fresh_brain.apply_brain_rules("cold email", max_recall_tokens=50, ranker="flat")

    assert "<brain-rules>" in text
