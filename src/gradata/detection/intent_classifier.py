"""Dual-layer intent classifier — regex heuristics determine *why* the user
corrected the output, not just *what* changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Regex heuristics (layer 1)
# ---------------------------------------------------------------------------

_FACTUAL_RE = [
    re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b"),  # dates
    re.compile(r"\b\d+(\.\d+)?%"),  # percentages
    re.compile(r"\$\d+"),  # dollar amounts
    re.compile(r"\bhttps?://\S+"),  # URLs
    re.compile(r"\b\d{3,}\b"),  # large numbers (3+ digits)
]

_COMPLIANCE_RE = [
    re.compile(r"\bGDPR\b", re.I),
    re.compile(r"\bSOC\s*2\b", re.I),
    re.compile(r"\bcomplian(ce|t)\b", re.I),
    re.compile(r"\bregulat(ion|ory)\b", re.I),
    re.compile(r"\blegal(ly)?\b", re.I),
    re.compile(r"\bprivacy\b", re.I),
    re.compile(r"\bdisclaimer\b", re.I),
]

_HEDGE_WORDS = re.compile(r"\b(perhaps|maybe|might|could be|it seems|arguably|somewhat)\b", re.I)

_LIST_RE = re.compile(r"^[\s]*[-*\d]+[.)]\s", re.MULTILINE)

_CONCISE_RE = [
    re.compile(r"\btoo (long|verbose|wordy)\b", re.I),
    re.compile(r"\bshorten\b", re.I),
    re.compile(r"\bbrevity\b", re.I),
    re.compile(r"\bconcise\b", re.I),
    re.compile(r"\btrim\b", re.I),
]

_COMPLETE_RE = [
    re.compile(r"\bmissing\b", re.I),
    re.compile(r"\bincomplete\b", re.I),
    re.compile(r"\badd (more|the|a)\b", re.I),
    re.compile(r"\bdon'?t forget\b", re.I),
    re.compile(r"\binclude\b", re.I),
]

_TONE_RE = [
    re.compile(r"\btoo (formal|casual|aggressive|harsh|soft)\b", re.I),
    re.compile(r"\btone\b", re.I),
    re.compile(r"\bfriendl(y|ier)\b", re.I),
    re.compile(r"\bprofessional\b", re.I),
    re.compile(r"\bwarm(er)?\b", re.I),
]


@dataclass
class CorrectionIntent:
    """Result of intent classification."""

    intent: str
    confidence: float
    evidence: str


def classify_intent(
    correction_text: str,
    original_text: str = "",
) -> CorrectionIntent:
    """Classify correction intent using regex heuristics.

    Args:
        correction_text: The correction description or user message.
        original_text: The original output that was corrected (optional).

    Returns:
        CorrectionIntent with intent label, confidence, and evidence.
    """
    combined = f"{correction_text} {original_text}"

    # Check each intent category in priority order
    for pat in _FACTUAL_RE:
        m = pat.search(correction_text)
        if m:
            return CorrectionIntent(
                intent="factual_correction",
                confidence=0.85,
                evidence=m.group(),
            )

    for pat in _COMPLIANCE_RE:
        m = pat.search(combined)
        if m:
            return CorrectionIntent(
                intent="compliance",
                confidence=0.80,
                evidence=m.group(),
            )

    for pat in _TONE_RE:
        m = pat.search(combined)
        if m:
            return CorrectionIntent(
                intent="tone_shift",
                confidence=0.75,
                evidence=m.group(),
            )

    for pat in _CONCISE_RE:
        m = pat.search(combined)
        if m:
            return CorrectionIntent(
                intent="conciseness",
                confidence=0.75,
                evidence=m.group(),
            )

    for pat in _COMPLETE_RE:
        m = pat.search(combined)
        if m:
            return CorrectionIntent(
                intent="completeness",
                confidence=0.70,
                evidence=m.group(),
            )

    if _HEDGE_WORDS.search(correction_text):
        return CorrectionIntent(
            intent="clarity",
            confidence=0.60,
            evidence=_HEDGE_WORDS.search(correction_text).group(),  # type: ignore[union-attr]
        )

    if _LIST_RE.search(correction_text):
        return CorrectionIntent(
            intent="formatting",
            confidence=0.60,
            evidence="list/bullet formatting detected",
        )

    # Fallback: if correction is short and doesn't match anything, likely preference
    if len(correction_text.split()) <= 10 and correction_text.strip():
        return CorrectionIntent(
            intent="preference",
            confidence=0.40,
            evidence="short correction without specific pattern",
        )

    return CorrectionIntent(
        intent="unknown",
        confidence=0.20,
        evidence="no pattern matched",
    )
