from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from gradata.cli import cmd_report
from gradata.enhancements.case_study_seed import (
    generate_case_study_seed,
    render_case_study_markdown,
)


def _seed_brain(brain_dir: Path) -> None:
    brain_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(brain_dir / "system.db")
    con.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            session INTEGER,
            type TEXT NOT NULL,
            source TEXT,
            data_json TEXT
        )
        """
    )
    con.commit()
    con.close()


def _event(brain_dir: Path, etype: str, data: dict, *, session: int = 1, ts: str = "2026-06-08T10:00:00+00:00") -> None:
    con = sqlite3.connect(brain_dir / "system.db")
    con.execute(
        "INSERT INTO events(ts, session, type, source, data_json) VALUES (?,?,?,?,?)",
        (ts, session, etype, "test", json.dumps(data)),
    )
    con.commit()
    con.close()


def test_case_study_seed_uses_top_repeated_mistake_and_omits_raw_prompt(tmp_path):
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    for session in (1, 2, 3):
        _event(
            brain_dir,
            "CORRECTION",
            {
                "category": "tone",
                "pattern": "AI draft sounds too formal",
                "before": "Dear Jane, confidential enterprise pricing is attached",
                "after": "Jane — quick note with pricing next steps",
                "before_summary": "Overly formal outreach",
                "after_summary": "Short direct AE-style note",
            },
            session=session,
        )
    _event(
        brain_dir,
        "CORRECTION",
        {"category": "format", "pattern": "Too many bullets", "before": "SECRET", "after": "ok"},
        session=4,
    )
    _event(
        brain_dir,
        "RULE_GRADUATED",
        {"category": "tone", "pattern": "AI draft sounds too formal", "rule": "Use concise AE-style language."},
        session=5,
    )
    _event(
        brain_dir,
        "LESSON_APPLIED",
        {"category": "tone", "lesson_description": "Use concise AE-style language."},
        session=6,
    )

    seed = generate_case_study_seed(brain_dir / "system.db")

    assert seed["top_repeated_mistake"]["category"] == "tone"
    assert seed["top_repeated_mistake"]["pattern"] == "AI draft sounds too formal"
    assert seed["event_counts"] == {
        "corrections": 4,
        "matching_corrections": 3,
        "rules_graduated": 1,
        "injections_or_applications": 1,
    }
    assert seed["before_after_evidence"][0] == {
        "session": 1,
        "before_summary": "Overly formal outreach",
        "after_summary": "Short direct AE-style note",
    }
    assert len(seed["before_after_evidence"]) == 3
    assert "confidential enterprise pricing" not in json.dumps(seed)
    assert seed["privacy"]["raw_prompt_content_included"] is False


def test_render_case_study_markdown_is_evidence_not_testimonial(tmp_path):
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    _event(brain_dir, "CORRECTION", {"category": "testing", "pattern": "Skipped focused tests"})

    markdown = render_case_study_markdown(generate_case_study_seed(brain_dir / "system.db"))

    assert "# Case-study seed" in markdown
    assert "Top repeated mistake" in markdown
    assert "Evidence counts" in markdown
    assert "Caveats" in markdown
    assert "testimonial" not in markdown.lower()


def test_report_case_study_seed_json_cli_output(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GRADATA_BRAIN", raising=False)
    monkeypatch.delenv("BRAIN_DIR", raising=False)
    brain_dir = tmp_path / "brain"
    _seed_brain(brain_dir)
    _event(brain_dir, "CORRECTION", {"category": "api", "pattern": "Invented API fields"})

    cmd_report(SimpleNamespace(brain_dir=brain_dir, type="case-study-seed", window=20, json=True))

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["top_repeated_mistake"]["pattern"] == "Invented API fields"
