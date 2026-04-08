"""PII and credential detection/redaction for the Gradata pipeline.

Critical pipeline order: diff engine and behavioral extraction run on FULL text
first, THEN PII is redacted BEFORE writing to events.jsonl.

Zero external dependencies — regex only.
"""

from __future__ import annotations

import re

# Order matters: API keys before emails to avoid partial matches on key prefixes.
_PII_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    # API keys / secrets
    ("openai_api_key", "[REDACTED_OPENAI_KEY]",
     re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("github_token", "[REDACTED_GITHUB_TOKEN]",
     re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}")),
    ("slack_token", "[REDACTED_SLACK_TOKEN]",
     re.compile(r"(?:xoxb|xoxp|xapp|xwfp)-[A-Za-z0-9\-]{20,}")),
    ("aws_access_key", "[REDACTED_AWS_KEY]",
     re.compile(r"AKIA[A-Z0-9]{16}")),
    ("google_api_key", "[REDACTED_GOOGLE_KEY]",
     re.compile(r"AIza[A-Za-z0-9_-]{35}")),
    ("gitlab_token", "[REDACTED_GITLAB_TOKEN]",
     re.compile(r"glpat-[A-Za-z0-9_-]{20,}")),
    # Credit card numbers (4-4-4-4 grouped format only to avoid false positives)
    ("credit_card", "[REDACTED_CC]",
     re.compile(r"\b(?:\d{4}[- ]){3}\d{4}\b")),
    # SSN (xxx-xx-xxxx)
    ("ssn", "[REDACTED_SSN]",
     re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Phone numbers (various formats)
    ("phone", "[REDACTED_PHONE]",
     re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")),
    # Email addresses (last to avoid clashing with API key patterns)
    ("email", "[REDACTED_EMAIL]",
     re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
]


def redact_pii(text: str) -> str:
    """Return *text* with all detected PII replaced by placeholders."""
    if not text:
        return text
    for _label, placeholder, pattern in _PII_PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def redact_pii_with_report(text: str) -> tuple[str, dict]:
    """Return (cleaned_text, report_dict).

    Report dict keys:
        redactions_count  – total number of replacements made
        types_found       – list of distinct PII type labels found
        redacted          – bool, True if any replacement was made
    """
    if not text:
        return text, {"redactions_count": 0, "types_found": [], "redacted": False}

    total = 0
    types_found: list[str] = []
    for label, placeholder, pattern in _PII_PATTERNS:
        new_text, n = pattern.subn(placeholder, text)
        if n > 0:
            total += n
            types_found.append(label)
            text = new_text

    report = {
        "redactions_count": total,
        "types_found": types_found,
        "redacted": total > 0,
    }
    return text, report
