"""Rule-based mode classifier — Signal 5.

Detects user intent mode from prompt text using keyword/regex matching.
No LLM calls, no external dependencies.
"""

from __future__ import annotations

import re

# ── Mode pattern definitions ──────────────────────────────────────────

_MODE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "code": [
        re.compile(r"\bimplement\b", re.IGNORECASE),
        re.compile(r"\bfix\b", re.IGNORECASE),
        re.compile(r"\brefactor\b", re.IGNORECASE),
        re.compile(r"\bdebug\b", re.IGNORECASE),
        re.compile(r"\btest\b", re.IGNORECASE),
        re.compile(r"\bfunction\b", re.IGNORECASE),
        re.compile(r"\bclass\b", re.IGNORECASE),
        re.compile(r"\bmethod\b", re.IGNORECASE),
        re.compile(r"\.\b(?:py|js|ts|tsx|jsx|rs|go|java|rb)\b", re.IGNORECASE),
        re.compile(r"\b(?:src|lib)/", re.IGNORECASE),
        re.compile(r"\b(?:TypeError|ValueError|KeyError|bug)\b"),
        re.compile(r"\b(?:API|endpoint|REST)\b", re.IGNORECASE),
    ],
    "email": [
        re.compile(r"\bemail\b", re.IGNORECASE),
        re.compile(r"\bfollow[\s-]?up\b", re.IGNORECASE),
        re.compile(r"\bdraft\b.*\bemail\b", re.IGNORECASE),
        re.compile(r"\bprospect\b", re.IGNORECASE),
        re.compile(r"\bsubject\s+line\b", re.IGNORECASE),
        re.compile(r"\breply\b", re.IGNORECASE),
        re.compile(r"\boutreach\b", re.IGNORECASE),
    ],
    "config": [
        re.compile(r"\bconfig\b", re.IGNORECASE),
        re.compile(r"\bsettings\b", re.IGNORECASE),
        re.compile(r"\benvironment\b", re.IGNORECASE),
        re.compile(r"\.env\b", re.IGNORECASE),
        re.compile(r"\.(?:yaml|yml|toml)\b", re.IGNORECASE),
        re.compile(r"\bdocker\b", re.IGNORECASE),
        re.compile(r"\bkubernetes\b", re.IGNORECASE),
        re.compile(r"\bCI/?CD\b", re.IGNORECASE),
    ],
    "documentation": [
        re.compile(r"\bREADME\b"),
        re.compile(r"\bdocs\b", re.IGNORECASE),
        re.compile(r"\bexplain\b", re.IGNORECASE),
        re.compile(r"\bdocument\b", re.IGNORECASE),
        re.compile(r"\barchitecture\b", re.IGNORECASE),
        re.compile(r"\bguide\b", re.IGNORECASE),
        re.compile(r"\btutorial\b", re.IGNORECASE),
    ],
}

# ── Category mapping ──────────────────────────────────────────────────

MODE_CATEGORY_MAP: dict[str, set[str]] = {
    "code": {"CODE", "STYLE", "TESTING", "ARCHITECTURE"},
    "email": {"TONE", "FORMAT", "CONTENT", "DRAFTING"},
    "config": {"CONFIG", "DEVOPS", "INFRASTRUCTURE"},
    "documentation": {"CONTENT", "FORMAT", "DOCUMENTATION"},
    "chat": set(),
}

# ── Public API ────────────────────────────────────────────────────────


def classify_mode(prompt: str) -> tuple[str, float]:
    """Classify user prompt into a mode.

    Returns:
        (mode, confidence) where mode is one of "code", "email", "config",
        "documentation", "chat" and confidence is 0.0-1.0.
    """
    if not prompt or not prompt.strip():
        return ("chat", 0.0)

    scores: dict[str, int] = {}
    for mode, patterns in _MODE_PATTERNS.items():
        count = sum(1 for p in patterns if p.search(prompt))
        if count > 0:
            scores[mode] = count

    if not scores:
        return ("chat", 0.0)

    best_mode = max(scores, key=lambda m: scores[m])
    best_count = scores[best_mode]
    total_patterns = len(_MODE_PATTERNS[best_mode])

    confidence = min(best_count / (total_patterns * 0.3), 1.0)

    return (best_mode, round(confidence, 4))