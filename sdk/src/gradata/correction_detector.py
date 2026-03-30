"""
Passive Correction Detection from Conversation Text.
=====================================================
SDK LAYER: Layer 0 (patterns-safe). Pure regex, no file I/O, no dependencies.

Stolen from SuperMemory's keyword detection pattern (detects "remember",
"architecture", "bug" to auto-save). Gradata equivalent: detect correction
signals in user messages to auto-capture learning events.

Usage::

    from gradata.correction_detector import detect_correction, extract_correction_context

    is_corr, confidence = detect_correction("No, don't use em dashes in emails")
    # (True, 0.92)

    context = extract_correction_context(
        "No, make it shorter and remove the bold",
        assistant_draft="Subject: **Revolutionize** Your Business..."
    )
    # {"is_correction": True, "confidence": 0.88, "signals": [...], "implied_changes": [...]}
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Correction Signal Patterns
# ---------------------------------------------------------------------------

# Each tuple: (compiled regex, base confidence, signal type)
# Confidence is the base weight; multiple matches compound.

_EXPLICIT_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    # Direct negation of AI output
    (re.compile(r"no[,.]?\s*(not\s+)?(that|this|like that)", re.IGNORECASE), 0.85, "negation"),
    # Instruction to change
    (re.compile(r"(change|fix|update|replace)\s+(this|that|it)\s+to", re.IGNORECASE), 0.90, "change_instruction"),
    # Prohibition
    (re.compile(r"don'?t\s+(do|use|include|add|write|say|put|make)", re.IGNORECASE), 0.92, "prohibition"),
    # Wrong/incorrect labels
    (re.compile(r"\b(wrong|incorrect|inaccurate|not right|not correct)\b", re.IGNORECASE), 0.88, "wrong_label"),
    # Stop/never directives
    (re.compile(r"(stop|quit|never)\s+(doing|using|writing|adding|putting|making)", re.IGNORECASE), 0.90, "stop_directive"),
    # Redo requests
    (re.compile(r"\b(redo|rewrite|start over|try again|do it again)\b", re.IGNORECASE), 0.85, "redo_request"),
    # Too much/little
    (re.compile(r"\btoo\s+(long|short|verbose|brief|formal|casual|aggressive|soft)\b", re.IGNORECASE), 0.80, "degree_correction"),
    # Remove/delete requests
    (re.compile(r"\b(remove|delete|drop|cut|get rid of)\s+(the|this|that|all)", re.IGNORECASE), 0.82, "removal"),
]

_IMPLICIT_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    # Redirect with "actually", "instead", "rather"
    (re.compile(r"\b(actually|instead|rather)[,.]?\s", re.IGNORECASE), 0.65, "redirect"),
    # Should-be directives
    (re.compile(r"(should\s+be|needs\s+to\s+be|make\s+it|make\s+this)", re.IGNORECASE), 0.70, "should_be"),
    # Reference to prior instruction
    (re.compile(r"I\s+(said|told\s+you|asked\s+for|wanted|meant)", re.IGNORECASE), 0.75, "prior_reference"),
    # Preference expression
    (re.compile(r"I\s+(prefer|want|need|like)\s+(it\s+)?(to\s+be\s+)?", re.IGNORECASE), 0.60, "preference"),
    # But/however (often precedes a correction)
    (re.compile(r"\b(but|however)[,.]?\s+(the|this|that|it|you)", re.IGNORECASE), 0.55, "contrast"),
    # More/less directive
    (re.compile(r"\b(more|less)\s+(concise|detailed|specific|general|formal|casual)", re.IGNORECASE), 0.68, "degree_adjust"),
]

# Combined for convenience
CORRECTION_SIGNALS = [
    # Explicit corrections
    r"no[,.]?\s*(not\s+)?(that|this|like that)",
    r"(change|fix|update|replace)\s+(this|that|it)\s+to",
    r"don't\s+(do|use|include|add|write|say)",
    r"(wrong|incorrect|inaccurate|not right)",
    r"(stop|quit|never)\s+(doing|using|writing|adding)",
    # Implicit corrections
    r"(actually|instead|rather)[,.]?\s",
    r"(should\s+be|needs\s+to\s+be|make\s+it)",
    r"I\s+(said|told\s+you|asked\s+for|wanted)",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_correction(text: str) -> tuple[bool, float]:
    """Detect whether a text contains correction signals.

    Scans the input text against explicit and implicit correction patterns.
    Multiple matching patterns compound the confidence (diminishing returns).

    Args:
        text: User message text to analyze.

    Returns:
        Tuple of (is_correction: bool, confidence: float).
        confidence is in [0.0, 1.0]. A message is considered a correction
        if confidence >= 0.50.
    """
    if not text or not text.strip():
        return (False, 0.0)

    matches: list[tuple[float, str]] = []

    # Check explicit patterns (higher weight)
    for pattern, base_conf, signal_type in _EXPLICIT_PATTERNS:
        if pattern.search(text):
            matches.append((base_conf, signal_type))

    # Check implicit patterns (lower weight)
    for pattern, base_conf, signal_type in _IMPLICIT_PATTERNS:
        if pattern.search(text):
            matches.append((base_conf, signal_type))

    if not matches:
        return (False, 0.0)

    # Compound confidence: highest match + diminishing bonus for additional matches
    matches.sort(key=lambda x: x[0], reverse=True)
    confidence = matches[0][0]

    for i, (conf, _) in enumerate(matches[1:], 1):
        # Each additional match adds a diminishing bonus
        bonus = conf * (0.3 / i)
        confidence = min(1.0, confidence + bonus)

    confidence = round(confidence, 2)
    is_correction = confidence >= 0.50

    return (is_correction, confidence)


@dataclass
class CorrectionContext:
    """Rich context about a detected correction.

    Attributes:
        is_correction: Whether the text is a correction.
        confidence: Detection confidence [0.0, 1.0].
        signals: List of signal types that matched.
        signal_details: List of (signal_type, matched_text, confidence) tuples.
        implied_changes: What the user wants changed (extracted from text).
    """
    is_correction: bool
    confidence: float
    signals: list[str]
    signal_details: list[tuple[str, str, float]]
    implied_changes: list[str]


def extract_correction_context(
    text: str,
    *,
    assistant_draft: str | None = None,
) -> CorrectionContext:
    """Extract rich correction context from a user message.

    Goes beyond simple detection to extract what the user wants changed.
    Useful for the learning proxy to understand the nature of the correction.

    Args:
        text: User message text.
        assistant_draft: The previous assistant message (optional).
            If provided, enables draft-comparison detection.

    Returns:
        CorrectionContext with detailed signal information.
    """
    if not text or not text.strip():
        return CorrectionContext(
            is_correction=False,
            confidence=0.0,
            signals=[],
            signal_details=[],
            implied_changes=[],
        )

    signal_details: list[tuple[str, str, float]] = []

    # Check all patterns and capture match text
    for pattern, base_conf, signal_type in _EXPLICIT_PATTERNS + _IMPLICIT_PATTERNS:
        match = pattern.search(text)
        if match:
            signal_details.append((signal_type, match.group(0), base_conf))

    if not signal_details:
        return CorrectionContext(
            is_correction=False,
            confidence=0.0,
            signals=[],
            signal_details=[],
            implied_changes=[],
        )

    # Compute confidence (same algorithm as detect_correction)
    sorted_details = sorted(signal_details, key=lambda x: x[2], reverse=True)
    confidence = sorted_details[0][2]
    for i, (_, _, conf) in enumerate(sorted_details[1:], 1):
        bonus = conf * (0.3 / i)
        confidence = min(1.0, confidence + bonus)
    confidence = round(confidence, 2)

    # Extract implied changes
    implied_changes = _extract_implied_changes(text)

    # If we have the assistant's draft, check for high-similarity edits
    if assistant_draft and _is_edited_version(text, assistant_draft):
        confidence = min(1.0, confidence + 0.1)
        implied_changes.append("user_edited_draft")

    return CorrectionContext(
        is_correction=confidence >= 0.50,
        confidence=confidence,
        signals=[s[0] for s in sorted_details],
        signal_details=sorted_details,
        implied_changes=implied_changes,
    )


def _extract_implied_changes(text: str) -> list[str]:
    """Extract what the user wants changed from correction text.

    Returns a list of human-readable change descriptions.
    """
    changes: list[str] = []

    # "don't use X" -> "remove X"
    dont_match = re.findall(
        r"don'?t\s+(use|include|add|write|say|put)\s+(.+?)(?:[.,;]|$)",
        text,
        re.IGNORECASE,
    )
    for action, target in dont_match:
        changes.append(f"remove: {target.strip()}")

    # "change X to Y" -> "replace X with Y"
    change_match = re.findall(
        r"(change|replace|update)\s+(.+?)\s+to\s+(.+?)(?:[.,;]|$)",
        text,
        re.IGNORECASE,
    )
    for _, old, new in change_match:
        changes.append(f"replace: '{old.strip()}' -> '{new.strip()}'")

    # "make it X" -> "adjust: X"
    make_match = re.findall(
        r"make\s+(?:it|this)\s+(.+?)(?:[.,;]|$)",
        text,
        re.IGNORECASE,
    )
    for adjustment in make_match:
        changes.append(f"adjust: {adjustment.strip()}")

    # "too X" -> "reduce X" / "increase opposite"
    too_match = re.findall(
        r"too\s+(long|short|verbose|brief|formal|casual|aggressive|soft)",
        text,
        re.IGNORECASE,
    )
    for quality in too_match:
        changes.append(f"degree: too {quality.strip()}")

    return changes


def _is_edited_version(user_text: str, assistant_text: str) -> bool:
    """Check if user_text looks like an edited version of assistant_text.

    Uses a simple length and overlap heuristic. If the user's message
    is similar in length and shares significant content with the
    assistant's previous message, it's likely an edit.
    """
    if len(user_text) < 20 or len(assistant_text) < 20:
        return False

    # Length ratio check
    ratio = len(user_text) / len(assistant_text)
    if ratio < 0.3 or ratio > 3.0:
        return False

    # Word overlap check
    user_words = set(user_text.lower().split())
    assistant_words = set(assistant_text.lower().split())
    if not assistant_words:
        return False

    overlap = len(user_words & assistant_words) / len(assistant_words)
    return overlap > 0.5
