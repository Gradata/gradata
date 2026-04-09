"""UserPromptSubmit hook: detect implicit feedback signals in user messages."""
from __future__ import annotations

import logging
import re

from gradata.hooks._base import run_hook, resolve_brain_dir, extract_message
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

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
            except Exception as exc:
                _log.debug("implicit_feedback emit failed: %s", exc)

        # Correction-driven nudging: check if any category needs a rule
        if brain_dir:
            try:
                from gradata.brain import Brain
                brain = Brain(brain_dir)
                recent_corrections = brain.query_events(
                    event_type="CORRECTION", last_n_sessions=5, limit=200,
                )
                if recent_corrections:
                    from gradata.enhancements.self_healing import check_nudge_threshold
                    lessons = brain._load_lessons()
                    categories_seen = set()
                    for evt in recent_corrections:
                        cat = (evt.get("data", {}).get("category") or "").upper()
                        if cat and cat != "UNKNOWN":
                            categories_seen.add(cat)
                    for cat in categories_seen:
                        nudge = check_nudge_threshold(recent_corrections, lessons, cat)
                        if nudge["should_nudge"]:
                            brain.emit(
                                "NUDGE_CREATE_RULE",
                                "hook:implicit_feedback",
                                {
                                    "category": cat,
                                    "correction_count": nudge["correction_count"],
                                    "centroid_description": nudge.get("centroid_description", ""),
                                },
                                [f"category:{cat}", "self_healing"],
                            )
                            proposed = nudge.get("proposed_lesson")
                            if proposed:
                                from datetime import date as _date
                                from gradata._types import Lesson, LessonState
                                from gradata.enhancements.self_improvement import (
                                    format_lessons, parse_lessons, INITIAL_CONFIDENCE,
                                )
                                from gradata._db import write_lessons_safe
                                lessons_path = brain._find_lessons_path(create=True)
                                if lessons_path:
                                    existing = parse_lessons(
                                        lessons_path.read_text(encoding="utf-8")
                                    ) if lessons_path.is_file() else []
                                    new_lesson = Lesson(
                                        date=_date.today().isoformat(),
                                        state=LessonState.INSTINCT,
                                        confidence=INITIAL_CONFIDENCE,
                                        category=proposed["category"],
                                        description=proposed["description"],
                                        pending_approval=True,
                                    )
                                    existing.append(new_lesson)
                                    write_lessons_safe(lessons_path, format_lessons(existing))
            except Exception as exc:
                _log.debug("nudge check failed: %s", exc)

        signal_names = ", ".join(s["type"] for s in signals)
        return {"result": f"IMPLICIT FEEDBACK: [{signal_names}]"}
    except Exception as exc:
        _log.debug("implicit_feedback hook error: %s", exc)
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
