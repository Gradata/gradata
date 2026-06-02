"""Prompt-injection guard for UserPromptSubmit hook (jit_inject.py)."

Scans user drafts before BM25 scoring.  Catches:
  - Roleplay / fictional framing (grandmother exploit, EvilGPT, simulation)
  - "print instructions" / "repeat everything above" phrasings
  - ChatML (<|im_start|>) and Alpaca (### Instruction:) markers
  - base64 / ROT13 encoded injection payloads
  - Few-shot hijack / fake assistant dialogue
  - Virtualization / game framing
  - Goal hijack / developer impersonation
  - Indirect injection markers

Gated by env var ``GRADATA_INJECTION_GUARD`` (default ON for new installs,
OFF for upgrades to avoid breaking existing setups).

Architecture: returns ``(suspicious: bool, reason: str)`` from ``is_suspicious()``
and a cleaned string from ``sanitize()``.  The hook in ``jit_inject.py`` uses
``is_suspicious`` as a pre-filter; if the draft is hostile the hook returns
``None`` (no rules injected) rather than injecting attacker-crafted rules.
"""

from __future__ import annotations

import base64
import codecs
import logging
import os
import re
import unicodedata

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env flag
# ---------------------------------------------------------------------------

def _guard_enabled() -> bool:
    """Return True if ``GRADATA_INJECTION_GUARD`` is enabled.

    Default OFF for upgrades, ON for fresh installs.  We detect "fresh install"
    heuristically: if GRADATA_LEGACY_INSTALL is set, assume upgrade and default
    OFF.  Otherwise default ON.
    """
    raw = os.environ.get("GRADATA_INJECTION_GUARD", "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    # Default ON for new installs, OFF when GRADATA_LEGACY_INSTALL is truthy.
    legacy = os.environ.get("GRADATA_LEGACY_INSTALL", "").strip().lower()
    return legacy not in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Sanitize
# ---------------------------------------------------------------------------


def sanitize(text: str) -> str:
    """Normalize, strip BOM, collapse repeated whitespace.

    Returns cleaned text.  Never raises — worst case returns original.
    """
    if not text:
        return text
    try:
        # Strip BOM
        if text.startswith("\ufeff"):
            text = text[1:]
        if text.startswith("\ufffe"):
            text = text[1:]
        # Unicode NFKC normalize (defeats homoglyphs)
        text = unicodedata.normalize("NFKC", text)
        # Strip zero-width chars: U+200B (ZW space) → real space to preserve word
        # boundaries for downstream regex detection; remove U+200C/U+200D (joiners).
        text = text.replace("​", " ")
        text = re.sub("[‌‍]", "", text)
        # Collapse repeated whitespace (3+ spaces/tabs/newlines → single newline)
        text = re.sub(r"[ \t]{3,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    except Exception:
        _log.debug("sanitize failed, returning original text", exc_info=True)
        return text


# ---------------------------------------------------------------------------
# Suspicious pattern detection
# ---------------------------------------------------------------------------

# --- Roleplay / fictional framing ---
_RE_ROLEPLAY = re.compile(
    r"(?:let(?:'s|\s+us)\s+play\s+a\s+game|"
    r"let(?:'s|\s+us)\s+do\s+a\s+roleplay|"
    r"you\s+are\s+my\s+(?:deceased|late|dead)\s+|"
    r"pretend\s+you\s+have\s+no\s+restrictions|"
    r"imagine\s+you\s+are\s+running\s+inside\s+a\s+simulation|"
    r"in\s+a\s+fictional\s+story\s+i(?:'m|\s+am)\s+writing|"
    r"this\s+is\s+(?:fiction|fictional|a\s+game|a\s+simulation)\s+so)",
    re.IGNORECASE,
)

# --- Named persona bypass ---
_RE_PERSONA = re.compile(
    r"(?:you\s+are\s+(?:\"[^\"]+\"|'[^']+'|[A-Z][a-z]+GPT)\b|"
    r"as\s+(?:\"[^\"]+\"|'[^']+'|[A-Z][a-z]+GPT)\b)",
    re.IGNORECASE,
)

# --- System prompt / instruction leak ---
_RE_SYSTEM_LEAK = re.compile(
    r"(?:print\s+(?:the\s+)?instructions?\s+you\s+were\s+given|"
    r"repeat\s+everything\s+(?:above|before)\s+this|"
    r"output\s+your\s+context\s+window|"
    r"(?:dump|extract)\s+(?:the\s+)?(?:system\s+prompt|your\s+prompt))",
    re.IGNORECASE,
)

# --- ChatML / LLM marker injection ---
_RE_LLM_MARKERS = re.compile(
    r"<\|im_start\|>|<\|im_end\|>|"
    r"###\s*Instruction\s*:|"
    r"###\s*Response\s*:|"
    r"###\s*Input\s*:",
    re.IGNORECASE,
)

# --- Few-shot hijack ---
_RE_FEW_SHOT = re.compile(
    r"(?:Here\s+are\s+some\s+examples\s+of\s+how\s+you\s+should\s+respond|"
    r"User\s*:.*\n\s*Assistant\s*(?:\(unrestricted\))?\s*:.*\n\s*User\s*:.*\n\s*Assistant)",
    re.IGNORECASE,
)

# --- Goal hijack / developer impersonation ---
_RE_GOAL_HIJACK = re.compile(
    r"(?:your\s+real\s+task\s+(?:here\s+)?is\s+different|"
    r"your\s+real\s+mission\s+is|"
    r"i(?:'m|\s+am)\s+your\s+(?:actual\s+)?developer|"
    r"type\s+\"READY\"\s+to\s+confirm)",
    re.IGNORECASE,
)

# --- Indirect injection ---
_RE_INDIRECT = re.compile(
    r"\[IMPORTANT\b.*?(?:ignore|disregard|forget)\s+",
    re.IGNORECASE | re.DOTALL,
)

# --- Generic override / bypass ---
_RE_OVERRIDE = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|your)\s+instructions?|"
    r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions?|"
    r"you\s+are\s+now\s+(?:an?\s+)?(?:unrestricted|unfiltered|unconstrained)|"
    r"override\s+(?:previous|your\s+(?:instructions?|rules?))|"
    r"bypass\s+your\s+(?:instructions?|rules?|content\s+policy)|"
    r"(?:jailbreak|dan\s+mode|do\s+anything\s+now))",
    re.IGNORECASE,
)

# --- Base64 / ROT13 detection ---
_B64_PATTERN = re.compile(
    r"(?:decode\s+this\s+base64|base64\s+(?:string|encoded)|base64\s+decode)",
    re.IGNORECASE,
)
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
_ROT13_PATTERN = re.compile(
    r"(?:translate\s+this\s+from\s+rot13|rot13\s+decode|rot13\s+this)",
    re.IGNORECASE,
)

# --- Combined injection pattern for re-scanning decoded content ---
# Broad catch-all for injection markers in decoded text.
_RE_DECODED_INJECTION = re.compile(
    r"(?i)(?:"
    r"i[gq]mn?or[eo]\s+(?:prev[io]ous|prior|all)\s+ins[\w]*?tructions?|"
    r"disregard\s+(?:previous|ins[\w]*?tructions?)|"
    r"system\s+prompt|"
    r"you\s+are\s+now\s+(?:an?\s+)?(?:unrestricted|unfiltered|unrenstricted)|"
    r"do\s+anything\s+now|"
    r"jailbreak|"
    r"bypass\s+your\s+(?:ins[\w]*?tructions?|rules?|content\s+policy)"
    r")"
)


def _decode_base64(text: str) -> str | None:
    """Try to extract and decode a base64 string from *text*.  Returns decoded or None."""
    m = _B64_PATTERN.search(text)
    if not m:
        return None
    # Search for the actual base64 blob after the instruction keyword
    after_instruction = text[m.start():]
    b64_blob = _B64_BLOB.search(after_instruction)
    if not b64_blob:
        return None
    b64_str = b64_blob.group(0)
    missing = len(b64_str) % 4
    if missing:
        b64_str += "=" * (4 - missing)
    try:
        return base64.b64decode(b64_str, validate=True).decode("utf-8", errors="replace")
    except Exception:
        return None


def _decode_rot13(text: str) -> str | None:
    """Try to find and decode a ROT13 blob. Returns decoded or None."""
    m = _ROT13_PATTERN.search(text)
    if not m:
        return None
    # Extract everything after the instruction — ROT13 payloads span multiple
    # sentences, not just the first one.
    after = text[m.end():]
    # Strip leading separator chars (colon, space, period)
    after = after.lstrip(": .\t\n")
    if not after or len(after) < 4:
        return None
    try:
        return codecs.decode(after, "rot_13")
    except Exception:
        return None


def _check_decoded(text: str) -> tuple[bool, str]:
    """Check if decoded base64/ROT13 content contains injection patterns."""
    b64 = _decode_base64(text)
    if b64 and _RE_DECODED_INJECTION.search(b64):
        return True, "base64-decoded content contains injection markers"
    rot = _decode_rot13(text)
    if rot and _RE_DECODED_INJECTION.search(rot):
        return True, "ROT13-decoded content contains injection markers"
    return False, ""


def is_suspicious(text: str) -> tuple[bool, str]:
    """Check *text* for prompt-injection patterns.

    Returns ``(suspicious: bool, reason: str)``.  *reason* is empty when
    *suspicious* is ``False``.

    The function is designed to have low false-positive rate on legitimate
    content while catching the 13 gap classes identified in the council review
    of GRA-1295 (see ``tests/security/fixtures/manifest.json``).
    """
    if not _guard_enabled():
        return False, ""

    if not text or not text.strip():
        return False, ""

    # Quick pre-check: if text is very short and doesn't contain known markers,
    # skip expensive processing.
    if len(text) < 20:
        return False, ""

    # Phase 1: Unicode-normalized regex patterns
    checks: list[tuple[str, re.Pattern[str]]] = [
        ("roleplay/fictional framing", _RE_ROLEPLAY),
        ("named persona bypass", _RE_PERSONA),
        ("system prompt leak", _RE_SYSTEM_LEAK),
        ("LLM marker injection", _RE_LLM_MARKERS),
        ("few-shot hijack", _RE_FEW_SHOT),
        ("goal hijack / developer impersonation", _RE_GOAL_HIJACK),
        ("indirect injection marker", _RE_INDIRECT),
        ("override/bypass", _RE_OVERRIDE),
    ]

    for label, pattern in checks:
        m = pattern.search(text)
        if m:
            _log.debug("injection guard: %s matched %r", label, m.group(0)[:80])
            return True, f"suspicious: {label}"

    # Phase 2: Decode and re-scan (base64, ROT13)
    suspicious, reason = _check_decoded(text)
    if suspicious:
        return True, reason

    return False, ""
