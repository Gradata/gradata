"""Context Compiler — extracts entities from user messages, queries the brain,
returns formatted context injection.
"""

import re
from typing import TYPE_CHECKING

from . import _paths as _p

if TYPE_CHECKING:
    from ._paths import BrainContext

# Task detection keywords
TASK_KEYWORDS = {
    "drafting": ["draft", "email", "write", "follow-up", "follow up", "reply", "send", "message"],
    "meeting_prep": ["demo", "call", "meeting", "prep", "present", "onboard"],
    "research": ["research", "qualify", "enrich", "find", "entity", "list", "item"],
    "critique": ["review", "critique", "check", "audit this"],
    "debug": ["debug", "fix", "error", "broken", "failing", "crash"],
}


def extract_entities(message: str, ctx: "BrainContext | None" = None) -> dict:
    result: dict[str, str | None] = {"prospect": None, "task_type": None, "topic": None}
    msg_lower = message.lower()
    prospect_map: dict[str, str] = {}
    _gpn_dir = ctx.prospects_dir if ctx else _p.PROSPECTS_DIR
    if _gpn_dir.exists():
        for _gpn_f in _gpn_dir.glob("*.md"):
            if _gpn_f.name.startswith("_"):
                continue
            _gpn_parts = re.split(r"(?:\s*[—–]\s*|\s*--\s*|\s+-\s+)", _gpn_f.stem, maxsplit=1)
            _gpn_full = _gpn_parts[0].strip()
            _gpn_co = _gpn_parts[1].strip() if len(_gpn_parts) > 1 else ""
            prospect_map[_gpn_full.lower()] = _gpn_full
            _gpn_np = _gpn_full.split()
            if len(_gpn_np) >= 2:
                prospect_map[_gpn_np[0].lower()] = _gpn_full
                prospect_map[_gpn_np[-1].lower()] = _gpn_full
            if _gpn_co:
                prospect_map[_gpn_co.lower()] = _gpn_full
    for key in sorted(prospect_map.keys(), key=len, reverse=True):
        if key in msg_lower and len(key) > 2:
            result["prospect"] = prospect_map[key]
            break
    for task_type, keywords in TASK_KEYWORDS.items():
        for kw in keywords:
            if kw in msg_lower:
                result["task_type"] = task_type
                break
        if result["task_type"]:
            break
    result["topic"] = message[:100]
    return result


def compile_context(
    message: str,
    prospect: str | None = None,
    task: str | None = None,
    ctx: "BrainContext | None" = None,
) -> str:
    entities = extract_entities(message, ctx=ctx)
    if prospect:
        entities["prospect"] = prospect
    if task:
        entities["task_type"] = task

    if not entities["prospect"] and not entities["task_type"]:
        try:
            from ._query import brain_search

            results = brain_search(message[:100], top_k=2, mode="keyword")
            if results and results[0].get("score", 0) > 0.3:
                lines = ["## Context"]
                for r in results[:2]:
                    src = r.get("source", "")
                    txt = r.get("text", "")[:100]
                    lines.append(f"- [{src}] {txt}")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    try:
        from ._context_packet import build_packet

        packet = build_packet(
            prospect=entities["prospect"],
            task_type=entities["task_type"],
            topic=entities["topic"],
        )
        if len(packet) > 3000:
            packet = packet[:3000] + "\n\n[...context truncated]"
        return packet
    except Exception as e:
        return f"[context compile error: {e}]"
