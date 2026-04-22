"""Apply-path tests: MaterializeResult → Lesson list + RULE_CONFLICT emission."""

from __future__ import annotations

from gradata._types import Lesson, LessonState
from gradata.cloud._apply_materialized import apply_to_lessons, emit_conflict_events
from gradata.cloud.materializer import Conflict, MaterializedRule, MaterializeResult


def _lesson(
    *,
    category: str = "style",
    description: str = "use active voice",
    state: LessonState = LessonState.INSTINCT,
    confidence: float = 0.50,
    fire_count: int = 1,
) -> Lesson:
    return Lesson(
        date="2026-04-20",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
    )


def _materialized(
    *,
    category: str = "style",
    description: str = "use active voice",
    state: str = "PATTERN",
    confidence: float = 0.62,
    fire_count: int = 3,
    ts: str = "2026-04-20T00:00:00Z",
) -> MaterializedRule:
    return MaterializedRule(
        category=category,
        description=description,
        state=state,
        confidence=confidence,
        fire_count=fire_count,
        winning_event_ts=ts,
        winning_device_id="dev_a",
    )


class TestApplyToLessons:
    def test_existing_lesson_gets_state_and_confidence_updated(self) -> None:
        lessons = [_lesson(state=LessonState.INSTINCT, confidence=0.50)]
        result = MaterializeResult(rules={("style", "use active voice"): _materialized()})
        updated = apply_to_lessons(lessons, result)
        assert len(updated) == 1
        assert updated[0].state == LessonState.PATTERN
        assert updated[0].confidence == 0.62

    def test_materialized_rule_without_lesson_is_appended(self) -> None:
        result = MaterializeResult(
            rules={
                ("structure", "headings first"): _materialized(
                    category="structure",
                    description="headings first",
                    state="RULE",
                    confidence=0.92,
                )
            }
        )
        updated = apply_to_lessons([], result)
        assert len(updated) == 1
        assert updated[0].category == "structure"
        assert updated[0].state == LessonState.RULE
        assert updated[0].date == "2026-04-20"

    def test_conflicting_rule_does_not_overwrite_local(self) -> None:
        lessons = [_lesson(state=LessonState.INSTINCT, confidence=0.50)]
        result = MaterializeResult(
            rules={("style", "use active voice"): _materialized(state="RULE", confidence=0.95)},
            conflicts=[
                Conflict(
                    key=("style", "use active voice"),
                    left_event={"ts": "1", "data": {}},
                    right_event={"ts": "2", "data": {}},
                    reason="confidence_drift",
                )
            ],
        )
        updated = apply_to_lessons(lessons, result)
        assert updated[0].state == LessonState.INSTINCT  # unchanged
        assert updated[0].confidence == 0.50

    def test_unrelated_lesson_is_left_alone(self) -> None:
        lessons = [
            _lesson(category="tone", description="warm not flowery"),
            _lesson(category="style", description="use active voice"),
        ]
        result = MaterializeResult(rules={("style", "use active voice"): _materialized()})
        updated = apply_to_lessons(lessons, result)
        tone = next(l for l in updated if l.category == "tone")
        assert tone.state == LessonState.INSTINCT
        assert tone.confidence == 0.50

    def test_unknown_state_name_skips_update(self) -> None:
        lessons = [_lesson()]
        result = MaterializeResult(
            rules={("style", "use active voice"): _materialized(state="LOL_NOT_A_STATE")}
        )
        updated = apply_to_lessons(lessons, result)
        assert updated[0].state == LessonState.INSTINCT  # unchanged

    def test_fire_count_never_decreases(self) -> None:
        lessons = [_lesson(fire_count=10)]
        result = MaterializeResult(
            rules={("style", "use active voice"): _materialized(fire_count=3)}
        )
        updated = apply_to_lessons(lessons, result)
        assert updated[0].fire_count == 10


class TestEmitConflictEvents:
    def test_no_conflicts_emits_nothing(self) -> None:
        calls: list = []

        def record(*args):
            calls.append(args)

        emitted = emit_conflict_events(MaterializeResult(), emit_fn=record)
        assert emitted == 0
        assert calls == []

    def test_each_conflict_emits_one_rule_conflict_event(self) -> None:
        calls: list = []

        def record(event_type, source, payload, tags):
            calls.append((event_type, payload))

        result = MaterializeResult(
            conflicts=[
                Conflict(
                    key=("style", "use active voice"),
                    left_event={"ts": "2026-04-20T00:00:00Z", "data": {"device_id": "dev_a"}},
                    right_event={"ts": "2026-04-20T00:01:00Z", "data": {"device_id": "dev_b"}},
                    reason="confidence_drift",
                ),
                Conflict(
                    key=("tone", "warm not flowery"),
                    left_event={"ts": "2026-04-20T00:02:00Z", "data": {}},
                    right_event={"ts": "2026-04-20T00:03:00Z", "data": {}},
                    reason="state_disagreement",
                ),
            ]
        )
        emitted = emit_conflict_events(result, emit_fn=record)
        assert emitted == 2
        assert calls[0][0] == "RULE_CONFLICT"
        assert calls[0][1]["reason"] == "confidence_drift"
        assert calls[0][1]["left_device"] == "dev_a"
        assert calls[1][1]["reason"] == "state_disagreement"

    def test_emit_failure_is_swallowed(self) -> None:
        def raising(*args):
            raise RuntimeError("boom")

        result = MaterializeResult(
            conflicts=[
                Conflict(
                    key=("style", "x"),
                    left_event={"ts": "1", "data": {}},
                    right_event={"ts": "2", "data": {}},
                    reason="confidence_drift",
                )
            ]
        )
        # Must not raise
        emitted = emit_conflict_events(result, emit_fn=raising)
        assert emitted == 0
