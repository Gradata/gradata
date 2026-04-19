"""Trust-boundary sanitization for lesson content. Contexts: ``xml``
(escape ``<>&"'`` to prevent ``</brain-rules>`` breakout), ``js`` (full
JSON/JS escaping + ``</script>``), ``js_template`` (lighter variant for
json.dumps output — backtick/``${}``), ``llm_prompt`` (``[FILTERED]``
replacement of injection markers). Pure; sanitize-and-continue to avoid DoS.
"""

from __future__ import annotations

import re
from typing import Literal

# ---------------------------------------------------------------------------
# Context type alias
# ---------------------------------------------------------------------------

SanitizeContext = Literal["xml", "js", "js_template", "llm_prompt"]

# ---------------------------------------------------------------------------
# XML escaping
# ---------------------------------------------------------------------------

_XML_ESCAPE_TABLE = str.maketrans(
    {
        "&": "&amp;",  # Must be first to avoid double-escaping
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
)


def _escape_xml(text: str) -> str:
    """Escape text so it is safe to embed inside an XML element body or attribute."""
    return text.translate(_XML_ESCAPE_TABLE)


# ---------------------------------------------------------------------------
# JS / JSON string escaping
# ---------------------------------------------------------------------------

# Full JS escaping for text NOT already through json.dumps()
_JS_FULL_ESCAPE_TABLE = str.maketrans(
    {
        "\\": "\\\\",
        '"': '\\"',
        "'": "\\'",
        "\n": " ",
        "\r": " ",
        "\0": "",
    }
)

_TEMPLATE_LITERAL_RE = re.compile(r"`|\$\{")


# ---------------------------------------------------------------------------
# LLM prompt neutralization
# ---------------------------------------------------------------------------

# Patterns that indicate prompt-injection attempts.
# These are output-gate patterns: they catch rephrased variants that the
# ingest-gate adversarial_blocklist may not have seen.
#
# Design: named groups so we can log *which* pattern triggered.
_PROMPT_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Classic openers
    (
        "ignore_previous",
        re.compile(
            r"\b(?:ignore|disregard|forget)\s+(?:previous|prior|all\s+previous|the\s+above|everything\s+above)"
            r"\s+(?:instructions?|rules?|prompts?|context)?",
            re.IGNORECASE,
        ),
    ),
    # Role hijack
    (
        "role_hijack",
        re.compile(
            r"\b(?:you\s+are\s+now|from\s+now\s+on\s+you\s+are|act\s+as\s+(?:if\s+you\s+(?:are|were)|a\b)|"
            r"pretend\s+you\s+are|new\s+role\s*:|new\s+instructions?\s*:)",
            re.IGNORECASE,
        ),
    ),
    # System prompt manipulation
    (
        "system_prompt",
        re.compile(
            r"\b(?:system\s+prompt|reveal\s+your\s+(?:prompt|instructions?)|"
            r"show\s+your\s+(?:instructions?|prompt)|print\s+your\s+system)",
            re.IGNORECASE,
        ),
    ),
    # Override / bypass
    (
        "override",
        re.compile(
            r"\b(?:override\s+(?:previous|your)|bypass\s+your|jailbreak|dan\s+mode|"
            r"developer\s+mode\s+enabled|do\s+anything\s+now)",
            re.IGNORECASE,
        ),
    ),
    # Instruction injection markers common in indirect prompt injection
    (
        "instruction_marker",
        re.compile(
            r"(?:^|\n)\s*(?:SYSTEM|HUMAN|ASSISTANT|USER|INSTRUCTION)\s*:\s*",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
)

_FILTER_PLACEHOLDER = "[FILTERED]"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_lesson_content(text: str, context: SanitizeContext) -> str:
    """Sanitize lesson *text* for embedding in the given output *context*.

    Parameters
    ----------
    text:
        Raw lesson description or rule text, potentially attacker-influenced.
    context:
        One of ``"xml"``, ``"js"``, ``"js_template"``, or ``"llm_prompt"``.

    Returns
    -------
    str
        The sanitized string, safe to embed in the target context.
        Never raises — on unexpected input the original text is returned
        after best-effort escaping.
    """
    if not text:
        return text

    if context == "xml":
        return _escape_xml(text)
    if context == "js":
        _ejs = _TEMPLATE_LITERAL_RE.sub("", text.translate(_JS_FULL_ESCAPE_TABLE))
        return re.sub(r"<\s*/\s*script\s*>", "", _ejs, flags=re.IGNORECASE)
    if context == "js_template":
        text = _TEMPLATE_LITERAL_RE.sub("", text)
        return re.sub(r"<\s*/\s*script\s*>", "", text, flags=re.IGNORECASE)
    if context == "llm_prompt":
        for _name, pattern in _PROMPT_INJECTION_PATTERNS:
            text = pattern.sub(_FILTER_PLACEHOLDER, text)
        return text

    # Unknown context: return as-is but log so we notice gaps.
    import logging

    logging.getLogger(__name__).warning(
        "sanitize_lesson_content: unknown context %r — returning text unchanged", context
    )
    return text
