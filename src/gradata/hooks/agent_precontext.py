"""PreToolUse hook: inject relevant brain rules into Agent subagent context.

Sub-agents inherit scope from the parent brain through two channels:

1. ``tool_input.scope_domain`` — explicit domain the parent passed to the
   subagent (highest priority).
2. ``os.environ["GRADATA_SCOPE_DOMAIN"]`` — propagated when the parent is
   running under a scoped brain view.

Falls back to keyword inference when no explicit scope is set.
"""
from __future__ import annotations

import os
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

try:
    from gradata.enhancements.self_improvement import parse_lessons
except ImportError:
    parse_lessons = None

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Agent",
    "profile": Profile.STANDARD,
    "timeout": 8000,
}

MAX_RULES = 5
MIN_CONFIDENCE = 0.60

# Keyword -> scope mapping for agent type inference
SCOPE_KEYWORDS = {
    "sales": ["sales", "prospect", "pipeline", "deal", "lead", "outreach", "email"],
    "code": ["code", "implement", "build", "fix", "debug", "test", "refactor"],
    "research": ["research", "analyze", "investigate", "compare", "study"],
    "writing": ["write", "draft", "document", "blog", "article", "copy"],
}


def _resolve_scope_domain(data: dict) -> str:
    """Resolve the scope domain for this sub-agent invocation.

    Priority: explicit ``tool_input.scope_domain`` > env var > "".
    Empty string means "no scope filter" (caller falls back to keyword match).
    """
    tool_input = data.get("tool_input", {}) or {}
    explicit = str(tool_input.get("scope_domain", "") or "").strip()
    if explicit:
        return explicit
    env = os.environ.get("GRADATA_SCOPE_DOMAIN", "").strip()
    return env


def _infer_agent_type(data: dict) -> str:
    tool_input = data.get("tool_input", {})
    agent_type = tool_input.get("subagent_type", "")
    if agent_type:
        return agent_type

    desc = tool_input.get("description", "") or tool_input.get("prompt", "")
    desc_lower = desc.lower()
    for scope, keywords in SCOPE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return scope
    return "general"


def _relevance_score(lesson, agent_type: str) -> float:
    score = lesson.confidence
    if lesson.state.name == "RULE":
        score += 0.2
    cat_lower = lesson.category.lower()
    if agent_type.lower() in cat_lower:
        score += 0.3
    keywords = SCOPE_KEYWORDS.get(agent_type.lower(), [])
    desc_lower = lesson.description.lower()
    if any(kw in desc_lower for kw in keywords):
        score += 0.1
    return score


def main(data: dict) -> dict | None:
    try:
        if parse_lessons is None:
            return None

        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return None

        lessons_path = Path(brain_dir) / "lessons.md"
        if not lessons_path.is_file():
            return None

        text = lessons_path.read_text(encoding="utf-8")
        all_lessons = parse_lessons(text)
        filtered = [lesson for lesson in all_lessons if lesson.state.name in ("RULE", "PATTERN") and lesson.confidence >= MIN_CONFIDENCE]
        if not filtered:
            return None

        # Sub-agent scope inheritance: filter by parent-declared domain first
        scope_domain = _resolve_scope_domain(data)
        if scope_domain:
            try:
                from gradata._scoped_brain import filter_lessons_by_domain

                scoped = filter_lessons_by_domain(filtered, scope_domain)
                if scoped:
                    filtered = scoped
            except Exception:
                pass  # Fall back to unfiltered on any import/runtime error

        agent_type = _infer_agent_type(data)
        scored = sorted(filtered, key=lambda r: _relevance_score(r, agent_type), reverse=True)
        top = scored[:MAX_RULES]

        lines = []
        for r in top:
            lines.append(f"[{r.state.name}:{r.confidence:.2f}] {r.category}: {r.description}")

        block = "<agent-rules>\n" + "\n".join(lines) + "\n</agent-rules>"
        return {"result": block}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
