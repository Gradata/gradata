from __future__ import annotations

import json

from scripts import weekly_correction_snapshot as snapshot


def test_parse_rows_skips_malformed_and_non_object_rows():
    rows, skipped = snapshot.parse_rows(
        [
            '{"event":"correction.created","category":"tone"}',
            "not-json",
            '["array-row"]',
            "",
            "   ",
        ]
    )
    assert skipped == 2
    assert len(rows) == 1


def test_aggregate_empty_input_has_zero_division_safe_defaults():
    data = snapshot.aggregate([])
    assert data["total_corrections"] == 0
    assert data["accepted_graduations"] == 0
    assert data["rejection_count"] == 0
    assert data["acceptance_rate"] == 0.0
    assert data["top_rule_categories"] == []


def test_aggregate_counts_and_top_categories_deterministically():
    rows = [
        {"event": "correction.created", "category": "Tone"},
        {"event": "correction.created", "category": "tone"},
        {"event": "correction.created", "category": "factual"},
        {"event": "correction.created", "category": "  PROCESS  "},
        {"kind": "correction", "category": ""},
        {"event": "lesson.graduated"},
        {"event": "graduation.accepted"},
        {"outcome": "accepted"},
        {"event": "graduation.rejected"},
        {"accepted": False},
    ]
    data = snapshot.aggregate(rows)
    assert data["total_corrections"] == 5
    assert data["accepted_graduations"] == 3
    assert data["rejection_count"] == 2
    assert data["acceptance_rate"] == 0.6
    assert data["top_rule_categories"] == [
        {"category": "tone", "count": 2},
        {"category": "factual", "count": 1},
        {"category": "process", "count": 1},
        {"category": "unknown", "count": 1},
    ]


def test_main_emits_deterministic_json_with_skipped_rows(capsys, monkeypatch):
    payload = (
        '{"event":"correction.created","category":"tone"}\n'
        '{"event":"lesson.graduated"}\n'
        '{"event":"graduation.rejected"}\n'
        "bad-row\n"
    )
    monkeypatch.setattr("sys.stdin.readlines", lambda: payload.splitlines(keepends=True))
    rc = snapshot.main([])
    assert rc == 0
    out = capsys.readouterr().out
    result = json.loads(out)
    assert result == {
        "acceptance_rate": 0.5,
        "accepted_graduations": 1,
        "rejection_count": 1,
        "skipped_rows": 1,
        "top_rule_categories": [{"category": "tone", "count": 1}],
        "total_corrections": 1,
    }
