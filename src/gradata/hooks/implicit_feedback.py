"""UserPromptSubmit hook: detect implicit feedback signals in user messages."""
from __future__ import annotations

import os
import re
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "UserPromptSubmit",
    "profile": Profile.STRICT,
    "timeout": 5000,
}

# Pattern categories with compiled regexes
NEGATION_PATTERNS = [
    re.compile(r"\bno[,.\s]", re.I),
    re.compile(r"\bnot like that\b", re.I),
    re.compile(r"\bwrong\b", re.I),
    re.compile(r"\bincorrect\b", re.I),
    re.compile(r"\bthat'?s not (right|correct|what)\b", re.I),
    re.compile(r"\bstop doing\b", re.I),
]

REMINDER_PATTERNS = [
    re.compile(r"\bI told you\b", re.I),
    re.compile(r"\bI said\b", re.I),
    re.compile(r"\bdon'?t forget\b", re.I),
    re.compile(r"\bmake sure\b", re.I),
    re.compile(r"\bremember (to|that)\b", re.I),
    re.compile(r"\bI already\b", re.I),
    re.compile(r"\bas I (said|mentioned)\b", re.I),
]

CHALLENGE_PATTERNS = [
    re.compile(r"\bare you sure\b", re.I),
    re.compile(r"\bthat doesn'?t seem right\b", re.I),
    re.compile(r"\bthat'?s not right\b", re.I),
    re.compile(r"\bI don'?t think (so|that)\b", re.I),
    re.compile(r"\bactually[,]?\s", re.I),
    re.compile(r"\bwhy (did|would|are) you\b", re.I),
]

SIGNAL_MAP = {
    "negation": NEGATION_PATTERNS,
    "reminder": REMINDER_PATTERNS,
    "challenge": CHALLENGE_PATTERNS,
}


def _extract_message(data: dict) -> str | None:
    msg = data.get("message") or data.get("prompt") or data.get("content")
    if not msg or not isinstance(msg, str):
        return None
    return msg.strip()


def _detect_signals(text: str) -> list[dict]:
    signals = []
    for signal_type, patterns in SIGNAL_MAP.items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 40)
                snippet = text[start:end].strip()
                signals.append({
                    "type": signal_type,
                    "match": match.group(),
                    "snippet": snippet,
                })
                break  # One match per category is enough
    return signals


def main(data: dict) -> dict | None:
    try:
        message = _extract_message(data)
        if not message or len(message) < 5:
            return None

        signals = _detect_signals(message)
        if not signals:
            return None

        # Emit event if brain dir available
        brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
        if not brain_dir:
            default = Path.home() / ".gradata" / "brain"
            brain_dir = str(default) if default.exists() else None

        if brain_dir:
            try:
                from gradata._events import emit
                emit(
                    "IMPLICIT_FEEDBACK",
                    source="hook:implicit_feedback",
                    data={
                        "signals": [s["type"] for s in signals],
                        "snippets": [s["snippet"] for s in signals[:3]],
                        "message_preview": message[:200],
                    },
                    brain_dir=brain_dir,
                )
            except Exception:
                pass

        signal_names = ", ".join(s["type"] for s in signals)
        return {"result": f"IMPLICIT FEEDBACK: [{signal_names}]"}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
