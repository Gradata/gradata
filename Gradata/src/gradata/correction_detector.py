"""
Passive Correction Detection from Conversation Text.
=====================================================
SDK LAYER: Layer 0 (patterns-safe). Pure regex, no file I/O, no dependencies.

Inspired by SuperMemory's keyword detection pattern (detects "remember",
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
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Correction Signal Patterns
# ---------------------------------------------------------------------------

# Each tuple: (compiled regex, base confidence, signal type)
# Confidence is the base weight; multiple matches compound.

_EXPLICIT_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    # Direct negation of AI output
    (re.compile(r"no[,.]?\s*(not\s+)?(that|this|like that)", re.IGNORECASE), 0.85, "negation"),
    # Instruction to change
    (
        re.compile(r"(change|fix|update|replace)\s+(this|that|it)\s+to", re.IGNORECASE),
        0.90,
        "change_instruction",
    ),
    # Prohibition
    (
        re.compile(r"don'?t\s+(do|use|include|add|write|say|put|make)", re.IGNORECASE),
        0.92,
        "prohibition",
    ),
    # Wrong/incorrect labels
    (
        re.compile(r"\b(wrong|incorrect|inaccurate|not right|not correct)\b", re.IGNORECASE),
        0.88,
        "wrong_label",
    ),
    # Stop/never directives
    (
        re.compile(
            r"(stop|quit|never)\s+(doing|using|writing|adding|putting|making)", re.IGNORECASE
        ),
        0.90,
        "stop_directive",
    ),
    # Redo requests
    (
        re.compile(r"\b(redo|rewrite|start over|try again|do it again)\b", re.IGNORECASE),
        0.85,
        "redo_request",
    ),
    # Too much/little
    (
        re.compile(
            r"\btoo\s+(long|short|verbose|brief|formal|casual|aggressive|soft)\b", re.IGNORECASE
        ),
        0.80,
        "degree_correction",
    ),
    # Remove/delete requests
    (
        re.compile(r"\b(remove|delete|drop|cut|get rid of)\s+(the|this|that|all)", re.IGNORECASE),
        0.82,
        "removal",
    ),
]

_IMPLICIT_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    # Redirect with "actually", "instead", "rather"
    (re.compile(r"\b(actually|instead|rather)[,.]?\s", re.IGNORECASE), 0.65, "redirect"),
    # Should-be directives
    (
        re.compile(r"(should\s+be|needs\s+to\s+be|make\s+it|make\s+this)", re.IGNORECASE),
        0.70,
        "should_be",
    ),
    # Reference to prior instruction
    (
        re.compile(r"I\s+(said|told\s+you|asked\s+for|wanted|meant)", re.IGNORECASE),
        0.75,
        "prior_reference",
    ),
    # Preference expression
    (
        re.compile(r"I\s+(prefer|want|need|like)\s+(it\s+)?(to\s+be\s+)?", re.IGNORECASE),
        0.60,
        "preference",
    ),
    # But/however (often precedes a correction)
    (re.compile(r"\b(but|however)[,.]?\s+(the|this|that|it|you)", re.IGNORECASE), 0.55, "contrast"),
    # More/less directive
    (
        re.compile(
            r"\b(more|less)\s+(concise|detailed|specific|general|formal|casual)", re.IGNORECASE
        ),
        0.68,
        "degree_adjust",
    ),
]

# ---------------------------------------------------------------------------
# Structured Correction Types
# ---------------------------------------------------------------------------

# Keyword → StructuredCorrectionType mapping: list of (pattern, type) in priority order.
# First match wins.
_TYPE_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bhallucin|made\s+up|doesn'?t\s+exist\b", re.IGNORECASE), "hallucination"),
    (re.compile(r"\b(wrong|incorrect|inaccurate|false)\b", re.IGNORECASE), "factual_error"),
    (
        re.compile(
            r"\b(tone|warm|cold|formal|casual|friendly|harsh|aggressive|soft)\b", re.IGNORECASE
        ),
        "tone",
    ),
    # format before style — layout/heading/structure are format, not style
    (
        re.compile(r"\b(format|layout|structure|heading|indent|spacing|align)\b", re.IGNORECASE),
        "format",
    ),
    (re.compile(r"\b(style|dash(?:es)?|emoji|bold|italic|bullet|font)\b", re.IGNORECASE), "style"),
    (
        re.compile(r"\b(missing|forgot|omit|skip|left\s+out|didn'?t\s+include)\b", re.IGNORECASE),
        "omission",
    ),
    (
        re.compile(
            r"\b(approach|method|strategy|workflow|process|tactic|technique)\b", re.IGNORECASE
        ),
        "approach",
    ),
    (
        re.compile(r"\b(scope|domain|context|only\s+for|not\s+for|outside)\b", re.IGNORECASE),
        "scope",
    ),
]

# Domain keyword → domain name mapping.
_DOMAIN_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"\b(email|subject\s+line|inbox|reply|thread|sender|recipient)\b", re.IGNORECASE
        ),
        "email",
    ),
    (
        re.compile(
            r"\b(code|function|class|method|variable|import|test|pytest|lint)\b", re.IGNORECASE
        ),
        "code",
    ),
    # deploy before sales — "pipeline" and "workflow" are deploy terms; sales uses "campaign/prospect/lead/deal"
    (
        re.compile(
            r"\b(deploy|railway|docker|ci|cd|build|pipeline|workflow|action)\b", re.IGNORECASE
        ),
        "deploy",
    ),
    (re.compile(r"\b(sales|prospect|lead|deal|outreach|campaign|crm)\b", re.IGNORECASE), "sales"),
    (
        re.compile(r"\b(api|endpoint|route|request|response|rest|graphql|http)\b", re.IGNORECASE),
        "api",
    ),
    (
        re.compile(r"\b(database|db|sql|query|schema|table|migration|supabase)\b", re.IGNORECASE),
        "database",
    ),
    (re.compile(r"\b(doc|document|readme|spec|design|architecture|plan)\b", re.IGNORECASE), "docs"),
]


class StructuredCorrectionType(StrEnum):
    """Classification of what kind of correction was made."""

    FACTUAL_ERROR = "factual_error"
    STYLE = "style"
    TONE = "tone"
    APPROACH = "approach"
    OMISSION = "omission"
    HALLUCINATION = "hallucination"
    FORMAT = "format"
    SCOPE = "scope"
    UNKNOWN = "unknown"


@dataclass
class StructuredCorrection:
    """Structured decomposition of a user correction.

    Adapted from Hindsight's what/when/where/who/why fact extraction,
    but using regex + enum instead of LLM calls for local-first operation.

    Attributes:
        what_wrong: What the AI did wrong (first changed segment from diff).
        why: Why it was wrong (user's stated reasoning, or inferred).
        correction_type: Enum classification of the correction kind.
        domain: Which domain this applies to (email, code, sales, deploy, etc.).
        severity: trivial/minor/moderate/major/rewrite.
        related_rule_id: ID of an existing rule this correction reinforces.
    """

    what_wrong: str
    why: str
    correction_type: StructuredCorrectionType
    domain: str
    severity: str
    related_rule_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "what_wrong": self.what_wrong,
            "why": self.why,
            "correction_type": str(self.correction_type),
            "domain": self.domain,
            "severity": self.severity,
            "related_rule_id": self.related_rule_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredCorrection:
        """Deserialize from a plain dict."""
        return cls(
            what_wrong=data.get("what_wrong", ""),
            why=data.get("why", ""),
            correction_type=StructuredCorrectionType(data.get("correction_type", "unknown")),
            domain=data.get("domain", "general"),
            severity=data.get("severity", "minor"),
            related_rule_id=data.get("related_rule_id"),
        )


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
        if confidence >= 0.65.
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
    # Threshold raised from 0.50 to 0.65 (S81 security fix):
    # 0.50 was too loose — weak signals created noisy lessons that
    # never graduated and polluted the pipeline. 0.65 ensures only
    # clear corrections create lessons.
    is_correction = confidence >= 0.65

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
    for _action, target in dont_match:
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


# ---------------------------------------------------------------------------
# Structured Correction Extraction
# ---------------------------------------------------------------------------


def extract_structured_correction(
    draft: str,
    final: str,
    context: str = "",
) -> StructuredCorrection | None:
    """Decompose a correction into 5 structured fields using regex + enum.

    No LLM calls — works fully offline. Uses the existing detect_correction()
    logic to gate on whether a real correction exists.

    Args:
        draft: The AI's original output (before correction).
        final: The corrected version or the user's correction message.
        context: Optional surrounding context (conversation snippet, task
            description). Used to improve domain and why extraction.

    Returns:
        StructuredCorrection if a correction is detected, else None.
    """
    # Gate: only proceed if there is a detectable correction signal.
    combined_signal = final if final else context
    is_corr, _ = detect_correction(combined_signal)
    # Also accept if draft and final differ significantly (user edited draft).
    if not is_corr:
        if draft and final and not _is_edited_version(final, draft):
            # No correction signal found and texts aren't similar edits.
            # Still try if the caller provided both a non-empty draft and final
            # that differ — treat as a correction.
            if draft.strip() == final.strip():
                return None
            # else: fall through and treat differing texts as a correction
        else:
            # No correction signal and either: texts are similar edits, or
            # one/both of draft/final are empty. Nothing to extract.
            return None

    full_text = " ".join(filter(None, [context, final]))

    what_wrong = _extract_what_wrong(draft, final)
    why = _extract_why(context, final)
    correction_type = _classify_correction_type(full_text)
    domain = _classify_domain(full_text)
    severity = _classify_severity(draft, final)

    return StructuredCorrection(
        what_wrong=what_wrong,
        why=why,
        correction_type=correction_type,
        domain=domain,
        severity=severity,
        related_rule_id=None,
    )


def _extract_what_wrong(draft: str, final: str) -> str:
    """Extract what the AI did wrong by diffing draft vs final.

    Returns the first segment that changed, or a generic fallback derived
    from the final text if no diff is detectable.
    """
    if not draft or not final:
        return final[:120] if final else "unknown"

    draft_words = draft.split()
    final_words = final.split()

    # Find first word position where they diverge.
    min_len = min(len(draft_words), len(final_words))
    diverge_idx = min_len  # default: divergence is at the end
    for i in range(min_len):
        if draft_words[i].lower() != final_words[i].lower():
            diverge_idx = i
            break

    if diverge_idx == min_len and len(draft_words) == len(final_words):
        # Texts are identical — fallback to the full final text snippet.
        return final[:120]

    # Capture a window of ~8 words around the divergence point in the draft.
    start = max(0, diverge_idx - 2)
    end = min(len(draft_words), diverge_idx + 6)
    segment = " ".join(draft_words[start:end])
    return segment[:120] if segment else draft[:120]


def _extract_why(context: str, final: str) -> str:
    """Extract the user's reasoning for the correction.

    Prefers explicit because/since/as clauses; falls back to the
    first sentence of the context, then the final text.
    """
    search_text = f"{context} {final}".strip()

    # Look for "because ...", "since ...", "as ..." clauses.
    because_match = re.search(
        r"\b(because|since|as)\b[,\s]+(.{10,120}?)(?:[.!?]|$)",
        search_text,
        re.IGNORECASE,
    )
    if because_match:
        return because_match.group(2).strip()

    # Look for "the reason is ...", "that's why ..."
    reason_match = re.search(
        r"(the\s+reason\s+is|that'?s?\s+why)[,\s]+(.{10,100}?)(?:[.!?]|$)",
        search_text,
        re.IGNORECASE,
    )
    if reason_match:
        return reason_match.group(2).strip()

    # Fall back: first sentence of context, then final.
    if context:
        first_sentence = re.split(r"[.!?]", context)[0].strip()
        if len(first_sentence) >= 10:
            return first_sentence[:120]

    return final[:120] if final else "no reason provided"


def _classify_correction_type(text: str) -> StructuredCorrectionType:
    """Classify correction type by matching keyword patterns in order."""
    for pattern, type_value in _TYPE_KEYWORD_PATTERNS:
        if pattern.search(text):
            return StructuredCorrectionType(type_value)
    return StructuredCorrectionType.UNKNOWN


def _classify_domain(text: str) -> str:
    """Classify which domain the correction applies to."""
    for pattern, domain in _DOMAIN_KEYWORD_PATTERNS:
        if pattern.search(text):
            return domain
    return "general"


def _classify_severity(draft: str, final: str) -> str:
    """Estimate correction severity from the edit distance heuristic.

    Mirrors the severity buckets used in the learning pipeline:
    trivial / minor / moderate / major / rewrite.
    """
    if not draft or not final:
        return "minor"

    draft_words = set(draft.lower().split())
    final_words = set(final.lower().split())

    if not draft_words:
        return "minor"

    # Words removed from draft (what the AI had that was wrong).
    removed = draft_words - final_words
    ratio = len(removed) / max(len(draft_words), 1)

    if ratio >= 0.80:
        return "rewrite"
    if ratio >= 0.50:
        return "major"
    if ratio >= 0.25:
        return "moderate"
    if ratio >= 0.05:
        return "minor"
    return "trivial"
