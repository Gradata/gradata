"""Tests for brain_benchmark.py — replays events and scores brain quality."""

import json
import tempfile
from pathlib import Path
import sys
import pytest

# Add brain/scripts to path so we can import brain_benchmark
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain" / "scripts"))


def _make_events_jsonl(tmp: Path, events: list[dict]) -> Path:
    p = tmp / "events.jsonl"
    with open(p, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    return p


def _make_brain_dir(tmp_path: Path) -> Path:
    brain = tmp_path / "test_brain"
    brain.mkdir()
    (brain / "system.db").touch()
    return brain


class TestBenchmarkScoring:
    def test_score_returns_dict_with_composite(self, tmp_path):
        from brain_benchmark import score_brain

        brain_dir = _make_brain_dir(tmp_path)
        events_path = _make_events_jsonl(
            tmp_path,
            [
                {
                    "ts": "2026-01-01T00:00:00Z",
                    "type": "CORRECTION",
                    "session": 1,
                    "source": "user",
                    "data": {
                        "category": "TONE",
                        "severity": "moderate",
                        "draft": "Dear Sir,",
                        "final": "Hey,",
                        "description": "Too formal",
                    },
                },
            ],
        )
        result = score_brain(brain_dir, events_path, use_llm_judge=False)
        assert "composite_score" in result
        assert 0 <= result["composite_score"] <= 100
        assert "graduation_speed" in result
        assert "rule_count" in result
        assert "confidence_distribution" in result

    def test_empty_events_returns_zero(self, tmp_path):
        from brain_benchmark import score_brain

        brain_dir = _make_brain_dir(tmp_path)
        events_path = _make_events_jsonl(tmp_path, [])
        result = score_brain(brain_dir, events_path, use_llm_judge=False)
        assert result["composite_score"] == 0.0

    def test_score_with_subset(self, tmp_path):
        from brain_benchmark import score_brain

        brain_dir = _make_brain_dir(tmp_path)
        events = [
            {
                "ts": f"2026-01-0{i + 1}T00:00:00Z",
                "type": "CORRECTION",
                "session": i,
                "source": "user",
                "data": {
                    "category": "TONE",
                    "severity": "moderate",
                    "draft": f"draft {i}",
                    "final": f"final {i}",
                    "description": f"correction {i}",
                },
            }
            for i in range(1, 11)
        ]
        events_path = _make_events_jsonl(tmp_path, events)
        result = score_brain(brain_dir, events_path, max_events=5, use_llm_judge=False)
        # Raw events capped at 5; synthetic graduation events may be added
        assert result["events_replayed"] >= 5
