"""PreToolUse hook: inject relevant brain rules into Agent subagent context."""
from __future__ import annotations

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
