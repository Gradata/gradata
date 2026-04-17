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
from gradata.rules.rule_ranker import rank_rules

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


def _lesson_to_rule_dict(lesson) -> dict:
    """Adapter: Lesson -> rank_rules dict (carries alpha/beta for Thompson)."""
    return {
        "id": getattr(lesson, "description", ""),
        "description": getattr(lesson, "description", ""),
        "category": getattr(lesson, "category", ""),
        "confidence": float(getattr(lesson, "confidence", 0.5)),
        "fire_count": int(getattr(lesson, "fire_count", 0)),
        "last_session": 0,
        "alpha": float(getattr(lesson, "alpha", 1.0)),
        "beta_param": float(getattr(lesson, "beta_param", 1.0)),
        "_lesson": lesson,
    }


def _resolve_agent_brain_dir() -> str | None:
    """Resolve brain dir for the precontext hook.

    Checks BRAIN_DIR before GRADATA_BRAIN_DIR so that sub-agent test
    fixtures — which monkeypatch BRAIN_DIR — are not clobbered by an
    ambient GRADATA_BRAIN_DIR set in the parent shell environment.
    BRAIN_DIR is the canonical SDK env var (used across all other modules);
    GRADATA_BRAIN_DIR is a namespaced alias.  Neither should silently
    override the other when the caller has explicitly set one of them.
    """
    for var in ("BRAIN_DIR", "GRADATA_BRAIN_DIR"):
        val = os.environ.get(var, "").strip()
        if val and Path(val).exists():
            return val
    # Fall back to the shared resolver (handles ~/.gradata/brain default)
    return resolve_brain_dir()


def main(data: dict) -> dict | None:
    try:
        if parse_lessons is None:
            return None

        brain_dir = _resolve_agent_brain_dir()
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
        keywords = list(SCOPE_KEYWORDS.get(agent_type.lower(), []))
        # Scope inference feeds the unified ranker as task_type + context_keywords.
        # BM25 picks up on category/description/tags overlap against these terms.
        rule_dicts = [_lesson_to_rule_dict(lesson) for lesson in filtered]

        session_seed = data.get("session_number") or data.get("session_id")
        if isinstance(session_seed, str):
            try:
                session_seed = int(session_seed)
            except ValueError:
                session_seed = abs(hash(session_seed)) % (2**31)

        ranked = rank_rules(
            rule_dicts,
            current_session=int(data.get("session_number") or 0),
            task_type=agent_type,
            context_keywords=keywords or None,
            max_rules=MAX_RULES,
            session_seed=session_seed if isinstance(session_seed, int) else None,
        )
        top: list = []
        for rd in ranked:
            lesson = rd.get("_lesson")
            if lesson is not None:
                top.append(lesson)

        lines = []
        for r in top:
            lines.append(f"[{r.state.name}:{r.confidence:.2f}] {r.category}: {r.description}")

        block = "<agent-rules>\n" + "\n".join(lines) + "\n</agent-rules>"
        return {"result": block}
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
