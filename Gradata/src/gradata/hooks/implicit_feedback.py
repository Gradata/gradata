"""UserPromptSubmit hook: detect implicit feedback signals in user messages."""

from __future__ import annotations

import logging
import re

from gradata.hooks._base import emit_hook_event, extract_message, run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "UserPromptSubmit",
    "profile": Profile.STRICT,
    "timeout": 5000,
}

# Pattern categories with compiled regexes.
# Shorthand forms ("r" for "are", "u" for "you", missing apostrophes in
# "dont"/"cant") are intentionally matched — real user corrections arrive
# in text-speak and dropping them produces silent false-negatives on the
# core "learn from any correction" promise.
NEGATION_PATTERNS = [
    re.compile(r"\bno[,.\s]", re.I),
    re.compile(r"\bnot like that\b", re.I),
    re.compile(r"\bwrong\b", re.I),
    re.compile(r"\bincorrect\b", re.I),
    re.compile(r"\bthat'?s not (right|correct|what)\b", re.I),
    re.compile(r"\bstop doing\b", re.I),
    re.compile(r"\bdon'?t\b", re.I),
    re.compile(r"\bdont\b", re.I),
    re.compile(r"\bcan'?t\b", re.I),
    re.compile(r"\bcant\b", re.I),
    re.compile(r"\bshouldn'?t\b", re.I),
    re.compile(r"\bshouldnt\b", re.I),
    re.compile(r"\bnever\b", re.I),
]

REMINDER_PATTERNS = [
    re.compile(r"\bI told you\b", re.I),
    re.compile(r"\bI said\b", re.I),
    re.compile(r"\bdon'?t forget\b", re.I),
    re.compile(r"\bdont forget\b", re.I),
    re.compile(r"\bmake sure\b", re.I),
    re.compile(r"\bremember (to|that)\b", re.I),
    re.compile(r"\bI already\b", re.I),
    re.compile(r"\bas I (said|mentioned)\b", re.I),
    re.compile(r"\bagain\.?\.?\b", re.I),
]

CHALLENGE_PATTERNS = [
    re.compile(r"\bare you sure\b", re.I),
    re.compile(r"\bthat doesn'?t seem right\b", re.I),
    re.compile(r"\bthat'?s not right\b", re.I),
    re.compile(r"\bI don'?t think (so|that)\b", re.I),
    re.compile(r"\bactually[,]?\s", re.I),
    re.compile(r"\bwhy (did|would|are|r) (you|u)\b", re.I),
    re.compile(r"\bwhy (not|r|are|is|does|would)\b", re.I),
    re.compile(r"\bwhy\s+\w+\.\.", re.I),
    re.compile(r"\bhow come\b", re.I),
    re.compile(r"\byou (didn'?t|didnt|missed|forgot|failed)\b", re.I),
]

APPROVAL_PATTERNS = [
    re.compile(r"\blooks? good\b", re.I),
    re.compile(r"\bperfect\b", re.I),
    re.compile(r"\bexactly( what)?\b", re.I),
    re.compile(r"\bthat'?s (right|correct|great|perfect)\b", re.I),
    re.compile(r"\byes[,.]?\s+(exactly|perfect|great|right|that)\b", re.I),
    re.compile(r"\bship it\b", re.I),
    re.compile(r"\bnailed it\b", re.I),
]

# GAP: the output omitted something the user expected. Parity with the removed
# JS implicit-feedback hook (hook-overlap audit 2026-04-21, Tier A item 5).
# NOTE: `forgot|missed` are owned by CHALLENGE_PATTERNS above; the gap variant
# uses `skipped|dropped|ignored` only so _detect_signals() can't emit both
# `gap` and `challenge` for the same phrase.
GAP_PATTERNS = [
    re.compile(r"\bwhat about\b", re.I),
    re.compile(r"\byou (skipped|dropped|ignored)\b", re.I),
    re.compile(r"\bdid (you|u) (check|verify|test|review)\b", re.I),
]

SIGNAL_MAP = {
    "negation": NEGATION_PATTERNS,
    "reminder": REMINDER_PATTERNS,
    "challenge": CHALLENGE_PATTERNS,
    "approval": APPROVAL_PATTERNS,
    "gap": GAP_PATTERNS,
}

# Any of these signals means the prior output was NOT tacitly accepted.
_NEGATIVE_SIGNAL_TYPES = {"negation", "reminder", "challenge", "gap"}

# Tacit-acceptance threshold: substantive follow-up messages without negative
# signals imply the prior output was OK. Short messages ("ok", "thanks", "go")
# are too ambiguous — they might be mid-sentence fragments or acknowledgements
# unrelated to the last output. Questions are NOT tacit acceptance either —
# they usually signal confusion or follow-up work.
_TACIT_MIN_LENGTH = 60
_QUESTION_PREFIXES = (
    "what",
    "why",
    "how",
    "when",
    "where",
    "who",
    "which",
    "can",
    "could",
    "should",
    "would",
    "will",
    "is",
    "are",
    "do",
    "does",
    "did",
)


def _looks_like_question(message: str) -> bool:
    """Heuristic: message is a question (not tacit acceptance)."""
    stripped = message.strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    first_word = stripped.split(None, 1)[0].lower().rstrip(",.!:;")
    return first_word in _QUESTION_PREFIXES


def _detect_signals(text: str) -> list[dict]:
    signals = []
    for signal_type, patterns in SIGNAL_MAP.items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 40)
                snippet = text[start:end].strip()
                signals.append(
                    {
                        "type": signal_type,
                        "match": match.group(),
                        "snippet": snippet,
                    }
                )
                break  # One match per category is enough
    return signals


def main(data: dict) -> dict | None:
    try:
        message = extract_message(data)
        if not message or len(message) < 5:
            return None

        signals = _detect_signals(message)
        signal_types = {s["type"] for s in signals}
        has_negative = bool(signal_types & _NEGATIVE_SIGNAL_TYPES)
        has_approval = "approval" in signal_types
        # Tacit acceptance: substantive follow-up with no negative signals. The
        # brain.correct() pipeline logs ~20x more CORRECTION than OUTPUT_ACCEPTED
        # because users rarely type "looks good" — silence is approval.
        tacit_accept = (
            not has_negative
            and not has_approval
            and len(message) >= _TACIT_MIN_LENGTH
            and not _looks_like_question(message)
        )

        if not signals and not tacit_accept:
            return None

        if signals:
            emit_hook_event(
                "IMPLICIT_FEEDBACK",
                "hook:implicit_feedback",
                {
                    "signals": [s["type"] for s in signals],
                    "snippets": [s["snippet"] for s in signals[:3]],
                    "message_preview": message[:200],
                },
            )
        if has_approval:
            emit_hook_event(
                "OUTPUT_ACCEPTED",
                "hook:implicit_feedback",
                {
                    "mode": "explicit",
                    "snippets": [s["snippet"] for s in signals if s["type"] == "approval"],
                    "message_preview": message[:200],
                },
            )
        elif tacit_accept:
            emit_hook_event(
                "OUTPUT_ACCEPTED",
                "hook:implicit_feedback",
                {"mode": "tacit", "message_preview": message[:200]},
            )

        if signals:
            signal_names = ", ".join(s["type"] for s in signals)
            return {"result": f"IMPLICIT FEEDBACK: [{signal_names}]"}
        return None
    except Exception as exc:
        _log.debug("implicit_feedback hook error: %s", exc)
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
