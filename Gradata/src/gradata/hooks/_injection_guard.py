"""Prompt-injection sanitization layer for hook input.

Wired into jit_inject.py BEFORE BM25 scoring to prevent hostile drafts
from poisoning rule selection. Behind env flag GRADATA_INJECTION_GUARD=1
(default ON for new installs, OFF for upgrades).

Two functions:
  is_suspicious(text) → (bool, reason) — regex+heuristic detection
  sanitize(text)       → str               — unicode cleanup, BOM strip

Attacks covered:
  1. "ignore previous instructions" / jailbreak templates
  2. Role-swap markers (SYSTEM:, <<SYS>>, <|im_start|>)
  3. Length-cap: drafts > 100k chars are suspicious
  4. Unicode normalization defeats zero-width chars
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Suspicious pattern detection
# ---------------------------------------------------------------------------

# Patterns that are strong indicators of prompt injection.
# Ordered by specificity — earlier patterns are lower false-positive.
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Direct override commands
    (
        r"(?i)\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|context)\b",
        "ignore_previous_instructions",
    ),
    (
        r"(?i)\bforget\s+(all\s+)?(previous|prior|earlier|above)\s+(instructions?|rules?|context|messages?)\b",
        "forget_previous_instructions",
    ),
    (
        r"(?i)\bdisregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|context)\b",
        "disregard_instructions",
    ),
    # Role-swap / jailbreak markers
    (
        r"(?i)\byou\s+are\s+now\s+(?:DAN|a\s+jailbroken|no\s+longer|an?\s+unrestricted|free|role.?playing)",
        "jailbreak_role_swap",
    ),
    (
        r"(?i)\b(?:act|pretend|roleplay)\s+(?:as|to\s+be|like)\s+(?:an?\s+)?(?:DAN|jailbroken|evil|malicious|unethical|unrestricted|unfiltered)",
        "pretend_role_swap",
    ),
    # System prompt injection markers
    (
        r"(?i)(?:^|\n)\s*SYSTEM\s*:",
        "system_marker_colon",
    ),
    (
        r"<<SYS>>",
        "llama2_sys_marker",
    ),
    (
        r"<\|im_start\|>system",
        "chatml_system_marker",
    ),
    (
        r"<\|im_start\|>",
        "chatml_role_marker",
    ),
    # Override / bypass keywords
    (
        r"(?i)\boverride\s+(?:your\s+)?(?:safety\s+)?(?:guidelines?|rules?|restrictions?|filters?|programming)\b",
        "override_safety_guidelines",
    ),
    (
        r"(?i)\bbypass\s+(?:your\s+)?(?:safety\s+)?(?:filters?|restrictions?|guidelines?)\b",
        "bypass_safety_filters",
    ),
    (
        r"(?i)\bdo\s+not\s+follow\s+(?:your\s+)?(?:instructions?|guidelines?|rules?|programming)\b",
        "dont_follow_instructions",
    ),
    # Developer-mode / DAN variants
    (
        r"(?i)\b(?:developer|dev)\s*mode\b",
        "developer_mode",
    ),
    (
        r"(?i)\bDAN\s*mode\b",
        "dan_mode",
    ),
    # New / fresh context tricks
    (
        r"(?i)\bstart\s+(?:a\s+)?new\s+(?:conversation|chat|session)\s+and\s+(?:ignore|forget)",
        "new_context_attack",
    ),
    (
        r"(?i)\byou\s+(?:must|should|need\s+to)\s+(?:answer|respond|reply)\s+(?:without|ignoring|bypassing)",
        "must_answer_unsafely",
    ),
]

# Compile once
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern), name) for pattern, name in _INJECTION_PATTERNS
]

# Maximum draft length before it's considered a context-window saturation attack
_MAX_DRAFT_LENGTH = 100_000


def is_suspicious(text: str) -> tuple[bool, str]:
    """Check if text contains prompt-injection markers.

    Returns (is_suspicious, reason_string). Reason is empty string when not suspicious.
    """
    if not text:
        return False, ""

    # Length cap: prevent context-window saturation
    if len(text) > _MAX_DRAFT_LENGTH:
        return True, f"length_exceeds_cap:{len(text)}"

    # Check each pattern
    for pattern, name in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True, name

    return False, ""


# ---------------------------------------------------------------------------
# Sanitization (non-destructive cleanup)
# ---------------------------------------------------------------------------


def sanitize(text: str) -> str:
    """Clean text without destroying content.

    - Unicode NFKC normalization (defeats zero-width chars, homoglyphs)
    - Strip BOM
    - Collapse repeated whitespace (single pass, not recursive)
    - Strip leading/trailing whitespace

    Does NOT remove content — use is_suspicious() for detection;
    this function only normalizes for comparison safety.
    """
    if not text:
        return ""

    # Unicode normalization handles zero-width joiners, homoglyphs, etc.
    text = unicodedata.normalize("NFKC", text)

    # Strip zero-width characters that NFKC leaves alone
    text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]", "", text)

    # Strip BOM
    text = text.lstrip("\ufeff")

    # Collapse repeated whitespace (single pass, not recursive)
    text = re.sub(r"\s+", " ", text)

    return text.strip()
