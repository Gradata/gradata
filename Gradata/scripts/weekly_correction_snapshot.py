#!/usr/bin/env python3
"""Compute weekly correction/graduation aggregates from NDJSON events."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from typing import Any


def _normalize_category(value: Any) -> str:
    if value is None:
        return "unknown"
    normalized = str(value).strip().lower()
    return normalized or "unknown"


def _is_correction(row: dict[str, Any]) -> bool:
    event = str(row.get("event", "")).strip().lower()
    kind = str(row.get("kind", "")).strip().lower()
    return event == "correction.created" or kind == "correction"


def _is_graduation_accepted(row: dict[str, Any]) -> bool:
    event = str(row.get("event", "")).strip().lower()
    outcome = str(row.get("outcome", "")).strip().lower()
    accepted_flag = row.get("accepted")
    status = str(row.get("status", "")).strip().lower()
    return (
        event in {"lesson.graduated", "graduation.accepted"}
        or outcome == "accepted"
        or accepted_flag is True
        or status in {"accepted", "graduated"}
    )


def _is_rejection(row: dict[str, Any]) -> bool:
    event = str(row.get("event", "")).strip().lower()
    outcome = str(row.get("outcome", "")).strip().lower()
    accepted_flag = row.get("accepted")
    status = str(row.get("status", "")).strip().lower()
    return (
        event in {"graduation.rejected", "lesson.rejected"}
        or outcome == "rejected"
        or accepted_flag is False
        or status == "rejected"
    )


def parse_rows(lines: list[str]) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(row, dict):
            skipped += 1
            continue
        rows.append(row)
    return rows, skipped


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_corrections = 0
    accepted_graduations = 0
    rejection_count = 0
    categories: Counter[str] = Counter()

    for row in rows:
        if _is_correction(row):
            total_corrections += 1
            categories[_normalize_category(row.get("category"))] += 1
        if _is_graduation_accepted(row):
            accepted_graduations += 1
        if _is_rejection(row):
            rejection_count += 1

    denominator = accepted_graduations + rejection_count
    acceptance_rate = round(accepted_graduations / denominator, 6) if denominator else 0.0

    top_categories = [
        {"category": name, "count": count}
        for name, count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

    return {
        "total_corrections": total_corrections,
        "accepted_graduations": accepted_graduations,
        "rejection_count": rejection_count,
        "acceptance_rate": acceptance_rate,
        "top_rule_categories": top_categories,
    }


def _read_lines(path: str | None) -> list[str]:
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.readlines()
    return sys.stdin.readlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute correction-outcome aggregates for weekly trend snapshots."
    )
    parser.add_argument("--input", help="Path to newline-delimited JSON input file")
    args = parser.parse_args(argv)

    lines = _read_lines(args.input)
    rows, skipped_rows = parse_rows(lines)
    snapshot = aggregate(rows)
    snapshot["skipped_rows"] = skipped_rows

    json.dump(snapshot, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
