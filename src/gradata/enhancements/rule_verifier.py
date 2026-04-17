"""Rule verification: pre-execution filtering and post-hoc output checking.

Pre-execution: TOOL_RULE_MATRIX maps tool/task types to relevant rule
categories so irrelevant rules are skipped before verification runs.

Post-hoc: scans output text for checkable patterns (em dashes, pricing,
links) and reports violations. Feeds results back into confidence scoring.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Pre-execution decision tree
# ---------------------------------------------------------------------------

# Maps tool/task types to the rule categories that are relevant for them.
# If a tool_type is not in the matrix, all categories are checked (safe default).
# Extend this dict at runtime via update_tool_rule_matrix() — no code changes needed.
TOOL_RULE_MATRIX: dict[str, list[str]] = {
    "Write": ["DRAFTING", "ARCHITECTURE", "IP_PROTECTION", "ACCURACY"],
    "Edit": ["DRAFTING", "ARCHITECTURE", "ACCURACY"],
    "Bash": ["PROCESS", "VERIFICATION", "CONSTRAINT"],
    "email_draft": ["DRAFTING", "COMMUNICATION", "POSITIONING", "PRICING"],
    "demo_prep": ["DEMO_PREP", "ACCURACY", "PRESENTATION"],
    "prospecting": ["LEADS", "CONSTRAINT", "DATA_INTEGRITY"],
    "code": ["ARCHITECTURE", "THOROUGHNESS", "VERIFICATION"],
}



def should_verify(tool_type: str, rule_category: str) -> bool:
    """Pre-execution gate: is this rule relevant for this tool/task?

    If *tool_type* is not in TOOL_RULE_MATRIX, returns ``True`` (verify
    everything by default — safe fallback for unknown tools).

    Args:
        tool_type: The current tool or task type (e.g. "email_draft", "Bash").
        rule_category: The category of the rule being considered.

    Returns:
        ``True`` if the rule should be checked, ``False`` to skip it.
    """
    relevant = TOOL_RULE_MATRIX.get(tool_type)
    if relevant is None:
        return True  # unknown tool -> check everything
    return rule_category.upper() in (c.upper() for c in relevant)


def get_relevant_rules(tool_type: str, all_rules: list[dict]) -> list[dict]:
    """Filter rules to only those relevant for the current tool/task.

    Each rule dict must have a ``"category"`` key. Rules whose category is
    not relevant for *tool_type* (per TOOL_RULE_MATRIX) are dropped.

    Args:
        tool_type: The current tool or task type.
        all_rules: Full list of rule dicts (each with at least ``"category"``).

    Returns:
        Filtered list of rule dicts relevant to the tool type.
    """
    return [
        rule for rule in all_rules
        if should_verify(tool_type, rule.get("category", "UNKNOWN"))
    ]



# ---------------------------------------------------------------------------
# Verification pattern registry
# ---------------------------------------------------------------------------

# (keyword_in_rule, regex_pattern, should_be_absent, description)
_PATTERNS: list[tuple[str, str, bool, str]] = [
    ("em dash", r"\u2014|--", True, "contains em dash or double dash"),
    ("em dashes", r"\u2014|--", True, "contains em dash or double dash"),
    ("pricing", r"\$\d+", True, "contains dollar amount"),
    ("dollar", r"\$\d+", True, "contains dollar amount"),
    ("booking link", r"https?://\S+/\S+", False, "missing booking link"),
    ("hyperlink", r"<a\s+href=", False, "missing HTML hyperlink"),
    ("bold", r"\*\*[^*]+\*\*", True, "contains markdown bold"),
    ("annual", r"\bannual\b|\byearly\b|\bper year\b", True, "references annual pricing"),
    ("raw url", r"(?<!\")https?://\S+(?!\")", True, "contains raw URL (should be hyperlinked)"),
]


@dataclass
class RuleVerification:
    rule_category: str
    rule_description: str
    passed: bool
    violation_detail: str = ""
    output_snippet: str = ""


def auto_detect_verification(rule_description: str) -> list[tuple[re.Pattern, bool, str]]:
    """Scan rule description for checkable patterns.

    Returns list of (compiled_regex, should_be_absent, violation_description).
    """
    desc_lower = rule_description.lower()
    checks = []
    seen = set()
    for keyword, pattern, absent, desc in _PATTERNS:
        if keyword in desc_lower and pattern not in seen:
            checks.append((re.compile(pattern, re.IGNORECASE), absent, desc))
            seen.add(pattern)
    return checks


def verify_rules(
    output: str,
    applied_rules: list[dict],
    context: dict | None = None,
) -> list[RuleVerification]:
    """Check output against applied rules for verifiable violations.

    When *context* contains a ``"tool_type"`` key, pre-execution filtering
    via :func:`should_verify` is applied first — rules whose category is
    irrelevant for the tool are skipped entirely, making verification both
    faster and less prone to false positives from mismatched rules.

    Args:
        output: The AI-generated text to check.
        applied_rules: List of dicts with at least 'category' and 'description'.
        context: Optional context dict. Recognized keys:
            - ``tool_type``: enables pre-execution category filtering.

    Returns:
        List of RuleVerification results (one per checkable rule).
    """
    # Pre-execution filter: skip rules irrelevant to the current tool
    tool_type = (context or {}).get("tool_type", "")
    if tool_type:
        applied_rules = get_relevant_rules(tool_type, applied_rules)

    results = []
    for rule in applied_rules:
        desc = rule.get("description", "")
        cat = rule.get("category", "UNKNOWN")
        checks = auto_detect_verification(desc)
        if not checks:
            continue

        for regex, should_be_absent, violation_desc in checks:
            match = regex.search(output)
            if should_be_absent and match:
                results.append(RuleVerification(
                    rule_category=cat,
                    rule_description=desc[:200],
                    passed=False,
                    violation_detail=violation_desc,
                    output_snippet=output[max(0, match.start() - 30):match.end() + 30][:200],
                ))
            elif not should_be_absent and not match:
                results.append(RuleVerification(
                    rule_category=cat,
                    rule_description=desc[:200],
                    passed=False,
                    violation_detail=violation_desc,
                    output_snippet=output[:200],
                ))
            else:
                results.append(RuleVerification(
                    rule_category=cat,
                    rule_description=desc[:200],
                    passed=True,
                ))
    return results


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS rule_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session INTEGER,
    rule_category TEXT,
    rule_description TEXT,
    passed BOOLEAN,
    violation_detail TEXT,
    output_snippet TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_table(db_path: Path) -> None:
    from gradata._db import ensure_table as _ensure
    from gradata._db import get_connection
    conn = get_connection(db_path)
    _ensure(conn, _CREATE_TABLE)
    conn.close()


def log_verification(
    session: int,
    results: list[RuleVerification],
    db_path: Path,
) -> None:
    """Write verification results to SQLite."""
    ensure_table(db_path)
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(str(db_path)) as conn:
        for r in results:
            conn.execute(
                "INSERT INTO rule_verifications "
                "(session, rule_category, rule_description, passed, violation_detail, output_snippet, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session, r.rule_category, r.rule_description, r.passed,
                 r.violation_detail, r.output_snippet, now),
            )


def get_verification_stats(db_path: Path) -> dict:
    """Return summary stats from rule_verifications table."""
    ensure_table(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM rule_verifications").fetchone()[0]
        passed = conn.execute("SELECT COUNT(*) FROM rule_verifications WHERE passed = 1").fetchone()[0]
        violations = conn.execute(
            "SELECT rule_category, COUNT(*) FROM rule_verifications "
            "WHERE passed = 0 GROUP BY rule_category ORDER BY COUNT(*) DESC"
        ).fetchall()

    return {
        "total_checks": total,
        "passed": passed,
        "pass_rate": passed / total if total > 0 else 1.0,
        "violations_by_category": {cat: count for cat, count in violations},
    }
