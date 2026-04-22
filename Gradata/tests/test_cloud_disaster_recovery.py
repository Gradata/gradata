"""End-to-end disaster recovery: a blank brain reconstructs the same
``lessons.md`` state as the origin brain purely by applying the pulled
event stream.

This is the ship-gate the marketing copy implies: ``gradata cloud
sync-pull --apply`` on a device that has nothing must converge to the
same rule set as the device those events came from.

We drive both devices through ``pull_events(apply=True)`` against the
same mocked HTTP response so the test covers the actual merge pipeline,
not a stub.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gradata import Brain
from gradata.cloud import _credentials as _creds
from gradata.cloud.pull import pull_events
from gradata.cloud.sync import CloudConfig, save_config
from gradata.enhancements.self_improvement import parse_lessons


@pytest.fixture(autouse=True)
def _isolate_keyfile(tmp_path, monkeypatch):
    """Isolate the keyfile per test so credential resolution is hermetic."""
    fake = tmp_path / ".gradata_test_key"
    monkeypatch.setattr(_creds, "KEYFILE_PATH", fake)
    monkeypatch.setattr(_creds, "KEYFILE_DIR", fake.parent)
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    monkeypatch.delenv("GRADATA_CLOUD_SYNC_DISABLE", raising=False)
    yield


def _enable_cloud(brain_dir):
    cfg = CloudConfig(sync_enabled=True, api_base="https://api.example.com")
    _tok = "gk_live_test"
    cfg.token = _tok
    save_config(brain_dir, cfg)


class _FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _multi_rule_stream() -> bytes:
    """Three graduations across two categories — enough to prove convergence
    is non-trivial (not just one-rule luck)."""
    return json.dumps(
        {
            "events": [
                {
                    "event_id": "e1",
                    "ts": "2026-04-20T00:00:00Z",
                    "type": "RULE_GRADUATED",
                    "source": "graduate",
                    "data": {
                        "category": "style",
                        "description": "use active voice",
                        "new_state": "PATTERN",
                        "confidence": 0.62,
                        "fire_count": 3,
                        "device_id": "origin",
                    },
                },
                {
                    "event_id": "e2",
                    "ts": "2026-04-20T00:01:00Z",
                    "type": "RULE_GRADUATED",
                    "source": "graduate",
                    "data": {
                        "category": "structure",
                        "description": "headings before prose",
                        "new_state": "PATTERN",
                        "confidence": 0.70,
                        "fire_count": 4,
                        "device_id": "origin",
                    },
                },
                {
                    "event_id": "e3",
                    "ts": "2026-04-20T00:02:00Z",
                    "type": "RULE_GRADUATED",
                    "source": "graduate",
                    "data": {
                        "category": "style",
                        "description": "use active voice",
                        "new_state": "PATTERN",
                        "confidence": 0.68,
                        "fire_count": 6,
                        "device_id": "origin",
                    },
                },
            ],
            "watermark": "origin-wm",
            "end_of_stream": True,
        }
    ).encode()


def _pull_and_apply(brain_dir, body: bytes) -> dict:
    with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
        return pull_events(brain_dir, apply=True)


def _rules_from_lessons(brain_dir) -> dict[tuple[str, str], tuple[str, float, int]]:
    """Project lessons.md into a comparable dict keyed by (category, description)."""
    path = brain_dir / "lessons.md"
    if not path.is_file():
        return {}
    out: dict[tuple[str, str], tuple[str, float, int]] = {}
    for lesson in parse_lessons(path.read_text(encoding="utf-8")):
        out[(lesson.category, lesson.description)] = (
            lesson.state.name,
            round(lesson.confidence, 6),
            lesson.fire_count,
        )
    return out


def test_blank_brain_converges_to_origin_after_apply(tmp_path):
    """A brand-new brain with empty lessons.md matches origin after one pull."""
    (tmp_path / "origin").mkdir()
    (tmp_path / "blank").mkdir()

    origin = Brain(tmp_path / "origin")
    origin.emit("SEED", "test", {"x": 1}, [])
    _enable_cloud(origin.dir)
    origin_result = _pull_and_apply(origin.dir, _multi_rule_stream())
    assert origin_result["applied"] is True

    blank = Brain(tmp_path / "blank")
    blank.emit("SEED", "test", {"x": 1}, [])
    _enable_cloud(blank.dir)
    blank_result = _pull_and_apply(blank.dir, _multi_rule_stream())
    assert blank_result["applied"] is True

    origin_rules = _rules_from_lessons(origin.dir)
    blank_rules = _rules_from_lessons(blank.dir)
    assert origin_rules == blank_rules
    # Locate the 'use active voice' rule regardless of how the serializer
    # casts category (lessons.md uppercases category on persist).
    active = next(k for k in origin_rules if k[1] == "use active voice")
    assert origin_rules[active] == ("PATTERN", 0.68, 6)


def test_replay_is_idempotent_end_to_end(tmp_path):
    """Applying the same stream twice produces byte-identical lessons.md."""
    brain = Brain(tmp_path)
    brain.emit("SEED", "test", {"x": 1}, [])
    _enable_cloud(brain.dir)

    _pull_and_apply(brain.dir, _multi_rule_stream())
    first = (brain.dir / "lessons.md").read_text(encoding="utf-8")

    _pull_and_apply(brain.dir, _multi_rule_stream())
    second = (brain.dir / "lessons.md").read_text(encoding="utf-8")

    assert first == second


def test_converges_despite_local_unrelated_lesson(tmp_path):
    """Pre-existing local lessons survive the merge untouched."""
    from gradata._db import write_lessons_safe
    from gradata._types import Lesson, LessonState
    from gradata.enhancements.self_improvement import format_lessons

    brain = Brain(tmp_path)
    brain.emit("SEED", "test", {"x": 1}, [])
    _enable_cloud(brain.dir)

    local = Lesson(
        date="2026-04-19",
        state=LessonState.INSTINCT,
        confidence=0.45,
        category="tone",
        description="avoid hedging",
        fire_count=2,
    )
    write_lessons_safe(brain.dir / "lessons.md", format_lessons([local]))

    _pull_and_apply(brain.dir, _multi_rule_stream())

    rules = _rules_from_lessons(brain.dir)
    descriptions = {desc for (_cat, desc) in rules}
    assert "avoid hedging" in descriptions
    assert "use active voice" in descriptions
    assert "headings before prose" in descriptions
