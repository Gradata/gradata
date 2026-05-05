from __future__ import annotations

import json
from pathlib import Path

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons
from gradata.mcp_tools import gradata_recall


def _write_lessons(path: Path, lessons: list[Lesson]) -> None:
    path.write_text(format_lessons(lessons), encoding="utf-8")


def _lesson(i: int, *, path: str = "") -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=LessonState.RULE,
        confidence=0.95 - (i * 0.01),
        category="EMAIL",
        description=f"cold email ecommerce CMO rule {i} with relevant detail",
        path=path,
    )


def test_gradata_recall_caps_output_under_budget(tmp_path: Path) -> None:
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [_lesson(i) for i in range(10)])

    text = gradata_recall(
        "cold email ecommerce CMO",
        max_tokens=100,
        lessons_path=lessons_path,
        meta_rules_path=tmp_path / "missing.json",
    )

    assert text.startswith("<brain-rules>")
    assert len(text) // 4 <= 100
    assert text.count("[RULE:") < 10


def test_gradata_recall_empty_returns_self_closing_xml(tmp_path: Path) -> None:
    assert (
        gradata_recall(
            "anything",
            lessons_path=tmp_path / "missing.md",
            meta_rules_path=tmp_path / "missing.json",
        )
        == "<brain-rules/>"
    )


def test_gradata_recall_reserves_meta_rule_slot(tmp_path: Path) -> None:
    lessons_path = tmp_path / "lessons.md"
    meta_path = tmp_path / "meta-rules.json"
    _write_lessons(lessons_path, [_lesson(i) for i in range(50)])
    meta_path.write_text(
        json.dumps(
            [
                {
                    "id": "meta-1",
                    "principle": "cold email ecommerce CMO meta principle",
                    "confidence": 0.91,
                    "source": "human_curated",
                }
            ]
        ),
        encoding="utf-8",
    )

    text = gradata_recall(
        "cold email ecommerce CMO",
        max_tokens=80,
        lessons_path=lessons_path,
        meta_rules_path=meta_path,
    )

    assert "[META:0.91]" in text


def test_gradata_recall_ranker_values_produce_distinct_ordering(tmp_path: Path) -> None:
    lessons_path = tmp_path / "lessons.md"
    lessons = [
        _lesson(0, path="EMAIL/sales/email_draft"),
        _lesson(1, path="EMAIL/sales/email_draft"),
        Lesson(
            date="2026-01-01",
            state=LessonState.RULE,
            confidence=0.99,
            category="PROCESS",
            description="cold email ecommerce CMO process rule",
            path="PROCESS/ops/checklist",
        ),
    ]
    _write_lessons(lessons_path, lessons)

    outputs = {
        ranker: gradata_recall(
            "cold email ecommerce CMO",
            max_tokens=200,
            ranker=ranker,
            lessons_path=lessons_path,
            meta_rules_path=tmp_path / "missing.json",
        )
        for ranker in ("hybrid", "flat", "tree_only")
    }

    assert len(set(outputs.values())) == 3
