"""
Context Compiler.
===================
Extracts entities from a user message, queries the brain,
returns formatted context injection.
"""

import re
from typing import TYPE_CHECKING

import gradata._paths as _p

if TYPE_CHECKING:
    from gradata._paths import BrainContext

# Task detection keywords
TASK_KEYWORDS = {
    "drafting": ["draft", "email", "write", "follow-up", "follow up", "reply", "send", "message"],
    "meeting_prep": ["demo", "call", "meeting", "prep", "present", "onboard"],
    "research": ["research", "qualify", "enrich", "find", "entity", "list", "item"],
    "critique": ["review", "critique", "check", "audit this"],
    "debug": ["debug", "fix", "error", "broken", "failing", "crash"],
}


def _get_prospect_names(ctx: "BrainContext | None" = None) -> dict[str, str]:
    names = {}
    prospects_dir = ctx.prospects_dir if ctx else _p.PROSPECTS_DIR
    if not prospects_dir.exists():
        return names
    for f in prospects_dir.glob("*.md"):
        if f.name.startswith("_"):
            continue
        stem = f.stem
        parts = re.split(r"(?:\s*[—–]\s*|\s*--\s*|\s+-\s+)", stem, maxsplit=1)
        full_name = parts[0].strip()
        company = parts[1].strip() if len(parts) > 1 else ""
        names[full_name.lower()] = full_name
        name_parts = full_name.split()
        if len(name_parts) >= 2:
            names[name_parts[0].lower()] = full_name
            names[name_parts[-1].lower()] = full_name
        if company:
            names[company.lower()] = full_name
    return names


def extract_entities(message: str, ctx: "BrainContext | None" = None) -> dict:
    result: dict[str, str | None] = {"prospect": None, "task_type": None, "topic": None}
    msg_lower = message.lower()
    prospect_map = _get_prospect_names(ctx=ctx)
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
    result["topic"] = message[:200]
    return result


def compile_context(message: str, prospect: str | None = None, task: str | None = None,
                    ctx: "BrainContext | None" = None) -> str:
    entities = extract_entities(message, ctx=ctx)
    if prospect:
        entities["prospect"] = prospect
    if task:
        entities["task_type"] = task

    if not entities["prospect"] and not entities["task_type"]:
        try:
            from gradata._query import brain_search
            results = brain_search(message[:100], top_k=3, mode="keyword")
            if results and results[0].get("score", 0) > 0.3:
                lines = ["## Brain Context (auto-retrieved)"]
                for r in results[:3]:
                    src = r.get("source", "")
                    txt = r.get("text", "")[:150]
                    lines.append(f"- [{src}] {txt}")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    try:
        from gradata._context_packet import build_packet
        packet = build_packet(
            prospect=entities["prospect"],
            task_type=entities["task_type"],
            topic=entities["topic"],
        )
        if len(packet) > 6000:
            packet = packet[:6000] + "\n\n[...context truncated to 1500 tokens]"
        return packet
    except Exception as e:
        return f"[context compile error: {e}]"