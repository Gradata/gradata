"""PreToolUse hook: inject relevant brain rules into Agent subagent context."""
from __future__ import annotations

import os
import re
from pathlib import Path

from gradata.hooks._base import run_hook
from gradata.hooks._profiles import Profile

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Agent",
    "profile": Profile.STANDARD,
    "timeout": 8000,
}

MAX_RULES = 5
MIN_CONFIDENCE = 0.60
RULE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+\[(RULE|PATTERN):([0-9.]+)\]\s+(\w+):\s+(.+)$"
)

# Keyword -> scope mapping for agent type inference
SCOPE_KEYWORDS = {
    "sales": ["sales", "prospect", "pipeline", "deal", "lead", "outreach", "email"],
    "code": ["code", "implement", "build", "fix", "debug", "test", "refactor"],
    "research": ["research", "analyze", "investigate", "compare", "study"],
    "writing": ["write", "draft", "document", "blog", "article", "copy"],
}


def _resolve_brain_dir() -> Path | None:
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if brain_dir:
        p = Path(brain_dir)
        return p if p.exists() else None
    default = Path.home() / ".gradata" / "brain"
    return default if default.exists() else None


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


def _parse_rules(text: str) -> list[dict]:
    rules = []
    for line in text.splitlines():
        m = RULE_RE.match(line.strip())
        if not m:
            continue
        _, state, conf_str, category, description = m.groups()
        conf = float(conf_str)
        if conf < MIN_CONFIDENCE:
            continue
        rules.append({
            "state": state,
            "confidence": conf,
            "category": category,
            "description": description.strip(),
        })
    return rules


def _relevance_score(rule: dict, agent_type: str) -> float:
    score = rule["confidence"]
    if rule["state"] == "RULE":
        score += 0.2
    cat_lower = rule["category"].lower()
    if agent_type.lower() in cat_lower:
        score += 0.3
    keywords = SCOPE_KEYWORDS.get(agent_type.lower(), [])
    desc_lower = rule["description"].lower()
    if any(kw in desc_lower for kw in keywords):
        score += 0.1
    return score


def main(data: dict) -> dict | None:
    try:
        brain_dir = _resolve_brain_dir()
        if not brain_dir:
            return None

        lessons_path = brain_dir / "lessons.md"
        if not lessons_path.is_file():
            return None

        text = lessons_path.read_text(encoding="utf-8")
        rules = _parse_rules(text)
        if not rules:
            return None

        agent_type = _infer_agent_type(data)
        scored = sorted(rules, key=lambda r: _relevance_score(r, agent_type), reverse=True)
        top = scored[:MAX_RULES]

        lines = []
        for r in top:
            lines.append(f"[{r['state']}:{r['confidence']:.2f}] {r['category']}: {r['description']}")

        block = "<agent-rules>\n" + "\n".join(lines) + "\n</agent-rules>"
        return {"result": block}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
