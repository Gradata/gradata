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

from ..rules.rule_ranker import rank_rules
from ._base import resolve_brain_dir, run_hook
from ._profiles import Profile

try:
    from ..enhancements.self_improvement import parse_lessons
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
                from .._scoped_brain import filter_lessons_by_domain

                scoped = filter_lessons_by_domain(filtered, scope_domain)
                if scoped:
                    filtered = scoped
            except Exception:
                pass  # Fall back to unfiltered on any import/runtime error

        _iat_ti = data.get("tool_input", {})
        agent_type = _iat_ti.get("subagent_type", "")
        if not agent_type:
            _iat_desc = (_iat_ti.get("description", "") or _iat_ti.get("prompt", "")).lower()
            agent_type = next(
                (scope for scope, kws in SCOPE_KEYWORDS.items() if any(kw in _iat_desc for kw in kws)),
                "general",
            )
        keywords = list(SCOPE_KEYWORDS.get(agent_type.lower(), []))
        # Scope inference feeds the unified ranker as task_type + context_keywords.
        # BM25 picks up on category/description/tags overlap against these terms.
        rule_dicts = [{
            "id": getattr(_l, "description", ""),
            "description": getattr(_l, "description", ""),
            "category": getattr(_l, "category", ""),
            "confidence": float(getattr(_l, "confidence", 0.5)),
            "fire_count": int(getattr(_l, "fire_count", 0)),
            "last_session": 0,
            "alpha": float(getattr(_l, "alpha", 1.0)),
            "beta_param": float(getattr(_l, "beta_param", 1.0)),
            "_lesson": _l,
        } for _l in filtered]

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
