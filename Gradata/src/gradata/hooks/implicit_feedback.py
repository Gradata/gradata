"""UserPromptSubmit hook: detect implicit feedback signals in user messages."""

from __future__ import annotations

import logging
import re

from gradata.hooks._base import extract_message, resolve_brain_dir, run_hook
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

SIGNAL_MAP = {
    "negation": NEGATION_PATTERNS,
    "reminder": REMINDER_PATTERNS,
    "challenge": CHALLENGE_PATTERNS,
    "approval": APPROVAL_PATTERNS,
}


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
        if not signals:
            return None

        # Emit event if brain dir available
        brain_dir = resolve_brain_dir()

        if brain_dir:
            try:
                from gradata._events import emit
                from gradata._paths import BrainContext

                ctx = BrainContext.from_brain_dir(brain_dir)
                emit(
                    "IMPLICIT_FEEDBACK",
                    source="hook:implicit_feedback",
                    data={
                        "signals": [s["type"] for s in signals],
                        "snippets": [s["snippet"] for s in signals[:3]],
                        "message_preview": message[:200],
                    },
                    ctx=ctx,
                )
                # Emit OUTPUT_ACCEPTED for approval signals
                if any(s["type"] == "approval" for s in signals):
                    emit(
                        "OUTPUT_ACCEPTED",
                        source="hook:implicit_feedback",
                        data={
                            "snippets": [s["snippet"] for s in signals if s["type"] == "approval"],
                            "message_preview": message[:200],
                        },
                        ctx=ctx,
                    )
            except Exception as exc:
                _log.debug("implicit_feedback emit failed: %s", exc)

        return None
    except Exception as exc:
        _log.debug("implicit_feedback hook error: %s", exc)
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
