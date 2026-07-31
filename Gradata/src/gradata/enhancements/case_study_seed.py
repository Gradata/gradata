"""Case-study seed reports from local Gradata evidence.

The report is intentionally evidence-first: it summarizes correction/rule/application
counts without emitting raw prompts or drafts by default.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

_RULE_EVENT_TYPES = {"RULE_GRADUATED"}
_INJECTION_EVENT_TYPES = {
    "LESSON_APPLIED",
    "LESSON_FIRED",
    "RULE_APPLICATION",
    "JIT_INJECTION",
}


def _rows(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with contextlib.closing(sqlite3.connect(str(db_path))) as con:
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT ts, session, type, source, data_json FROM events ORDER BY id ASC"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            data = json.loads(row["data_json"] or "{}")
        except json.JSONDecodeError:
            data = {}
        out.append(
            {
                "ts": row["ts"],
                "session": row["session"],
                "type": row["type"],
                "source": row["source"],
                "data": data if isinstance(data, dict) else {},
            }
        )
    return out


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def _category_pattern(event: dict[str, Any]) -> tuple[str, str]:
    data = _event_data(event)
    category = str(data.get("category") or data.get("rule_category") or "uncategorized")
    pattern = str(
        data.get("pattern")
        or data.get("lesson_description")
        or data.get("rule")
        or data.get("text")
        or "unspecified pattern"
    )
    return category, pattern


def _matches(event: dict[str, Any], category: str, pattern: str) -> bool:
    ev_category, ev_pattern = _category_pattern(event)
    return ev_category == category and (ev_pattern == pattern or pattern in ev_pattern or ev_pattern in pattern)


def _safe_before_after(event: dict[str, Any]) -> dict[str, Any]:
    data = _event_data(event)
    before_summary = data.get("before_summary") or data.get("draft_summary") or "raw content omitted"
    after_summary = data.get("after_summary") or data.get("final_summary") or "raw content omitted"
    return {
        "session": event.get("session"),
        "before_summary": str(before_summary),
        "after_summary": str(after_summary),
    }


def generate_case_study_seed(db_path: str | Path) -> dict[str, Any]:
    """Return a privacy-safe case-study seed from local event evidence.

    Raw fields such as ``before``, ``after``, ``draft``, ``final``, and prompts are
    not included. Callers get summaries/counts/caveats suitable for requesting a
    real customer's publication permission; not a synthetic testimonial.
    """
    db = Path(db_path)
    events = _rows(db)
    corrections = [e for e in events if e.get("type") == "CORRECTION"]
    rule_events = [e for e in events if e.get("type") in _RULE_EVENT_TYPES]
    injection_events = [e for e in events if e.get("type") in _INJECTION_EVENT_TYPES]

    counts = Counter(_category_pattern(e) for e in corrections)
    if counts:
        (category, pattern), matching_count = counts.most_common(1)[0]
    else:
        category, pattern, matching_count = "none", "no correction evidence found", 0

    matching_corrections = [e for e in corrections if _category_pattern(e) == (category, pattern)]
    associated_rules = []
    for event in rule_events:
        if _matches(event, category, pattern):
            data = _event_data(event)
            associated_rules.append(
                {
                    "session": event.get("session"),
                    "rule": str(data.get("rule") or data.get("text") or data.get("pattern") or pattern),
                    "category": str(data.get("category") or category),
                }
            )

    matching_injections = [e for e in injection_events if _category_pattern(e)[0] == category]

    return {
        "report": "case-study-seed",
        "source_db": str(db),
        "top_repeated_mistake": {
            "category": category,
            "pattern": pattern,
            "correction_count": matching_count,
        },
        "associated_rules": associated_rules[:5],
        "before_after_evidence": [_safe_before_after(e) for e in matching_corrections[:3]],
        "event_counts": {
            "corrections": len(corrections),
            "matching_corrections": len(matching_corrections),
            "rules_graduated": len(associated_rules),
            "injections_or_applications": len(matching_injections),
        },
        "privacy": {
            "raw_prompt_content_included": False,
            "redaction_note": "Raw drafts/prompts/finals are omitted by default; only summaries/counts are emitted.",
        },
        "caveats": [
            "This is a seed for human review and customer permission, not a publish-ready claim.",
            "Counts are local to this brain's system.db and may miss unsynced/cloud-only events.",
            "Before/after evidence uses summary fields when present; otherwise it records that raw content was omitted.",
        ],
    }


def render_case_study_markdown(seed: dict[str, Any]) -> str:
    top = seed.get("top_repeated_mistake", {})
    counts = seed.get("event_counts", {})
    lines = [
        "# Case-study seed",
        "",
        "Evidence-only draft for human review and publication permission.",
        "",
        "## Top repeated mistake",
        f"- Category: {top.get('category', 'unknown')}",
        f"- Pattern: {top.get('pattern', 'unknown')}",
        f"- Matching corrections: {top.get('correction_count', 0)}",
        "",
        "## Associated rules",
    ]
    rules = seed.get("associated_rules") or []
    if rules:
        for rule in rules:
            lines.append(f"- {rule.get('rule', '')}")
    else:
        lines.append("- None found in local RULE_GRADUATED events.")
    lines.extend(["", "## Before/after evidence"])
    evidence = seed.get("before_after_evidence") or []
    if evidence:
        for item in evidence:
            lines.append(
                f"- Session {item.get('session')}: before={item.get('before_summary')} -> after={item.get('after_summary')}"
            )
    else:
        lines.append("- No correction summaries available.")
    lines.extend(
        [
            "",
            "## Evidence counts",
            f"- Corrections: {counts.get('corrections', 0)}",
            f"- Matching corrections: {counts.get('matching_corrections', 0)}",
            f"- Rules graduated: {counts.get('rules_graduated', 0)}",
            f"- Injections/applications: {counts.get('injections_or_applications', 0)}",
            "",
            "## Privacy",
            f"- Raw prompt content included: {seed.get('privacy', {}).get('raw_prompt_content_included', False)}",
            f"- Note: {seed.get('privacy', {}).get('redaction_note', '')}",
            "",
            "## Caveats",
        ]
    )
    for caveat in seed.get("caveats", []):
        lines.append(f"- {caveat}")
    return "\n".join(lines) + "\n"
