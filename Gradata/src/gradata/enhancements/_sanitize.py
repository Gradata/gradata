"""Trust-boundary sanitization for lesson content.

Lesson text originates from user corrections and may contain attacker-crafted
payloads.  Before this text crosses into structured output surfaces it must be
escaped for the target context.

Supported contexts
------------------
``"xml"``
    Escape ``<``, ``>``, ``&``, ``"`` and ``'`` so that the text cannot
    terminate or inject XML tags.  Specifically prevents ``</brain-rules>``
    tag-termination attacks on the ``<brain-rules>`` injection block.

``"js"``
    Escape characters that break out of a JSON/JS string context: backslash,
    double-quote, single-quote, template-literal backtick, null byte, and
    ``</script>``-style tag breakouts.  Note: callers that already pass text
    through ``json.dumps()`` should use ``"js_template"`` instead which only
    strips the backtick / template-literal injection vectors not covered by
    ``json.dumps``.

``"js_template"``
    Lighter variant for text already processed by ``json.dumps()``.
    Escapes backticks and ``${`` (template-literal injections) and removes
    raw HTML-closing tags that could escape a ``<script>`` block.

``"llm_prompt"``
    Conservative neutralization of prompt-injection markers.  Detected
    markers are replaced with ``[FILTERED]`` rather than being silently
    dropped, so the loss of content is visible in logs / synthesized output.
    This is deliberately *conservative*: legitimate content that contains
    these patterns will be flagged and the marker replaced, but the rest of
    the sentence is preserved.

Design notes
------------
- All functions are *pure* and side-effect free.
- Raising on attacker input would allow DoS via lesson crafting; instead we
  sanitize and continue.
- The ``"llm_prompt"`` filter is intentionally narrow.  Broad blocklists
  produce high false-positive rates; the adversarial_blocklist module handles
  the *ingest* gate.  This function is the *output* gate: it neutralizes text
  that already passed ingest (e.g. rephrased injections, or text that arrived
  before the blocklist existed).
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

# Characters that break out of a JS double-quoted string and are NOT already
# handled by json.dumps().  json.dumps() handles \, ", \n, \r, \t, \0 — so
# the residual risk is backtick (template literal injection) and </script> tag.
_JS_BREAKOUT_RE = re.compile(
    r"`"  # template literal delimiter
    r"|<\s*/\s*script\s*>",  # </script> tag to break out of <script> blocks
    re.IGNORECASE,
)

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


def _escape_js_full(text: str) -> str:
    """Escape text for embedding in a JS double-quoted string literal."""
    escaped = text.translate(_JS_FULL_ESCAPE_TABLE)
    # Remove backticks and template-literal injection sequences
    escaped = _TEMPLATE_LITERAL_RE.sub("", escaped)
    # Remove </script> breakout
    escaped = re.sub(r"<\s*/\s*script\s*>", "", escaped, flags=re.IGNORECASE)
    return escaped


def _escape_js_template(text: str) -> str:
    """Light escaping for text already through json.dumps().

    json.dumps() handles backslash, double-quote, control characters.
    This layer removes backtick / template-literal injections and
    </script> breakouts which json.dumps() does not touch.
    """
    text = _TEMPLATE_LITERAL_RE.sub("", text)
    text = re.sub(r"<\s*/\s*script\s*>", "", text, flags=re.IGNORECASE)
    return text


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


def _neutralize_llm_prompt(text: str) -> str:
    """Replace detected prompt-injection markers with ``[FILTERED]``.

    Preserves the rest of the text so legitimate surrounding content is not
    lost.  Each replaced match is replaced in-place.
    """
    result = text
    for _name, pattern in _PROMPT_INJECTION_PATTERNS:
        result = pattern.sub(_FILTER_PLACEHOLDER, result)
    return result


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
        return _escape_js_full(text)
    if context == "js_template":
        return _escape_js_template(text)
    if context == "llm_prompt":
        return _neutralize_llm_prompt(text)

    # Unknown context: return as-is but log so we notice gaps.
    import logging

    logging.getLogger(__name__).warning(
        "sanitize_lesson_content: unknown context %r — returning text unchanged", context
    )
    return text
