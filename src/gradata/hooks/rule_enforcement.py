"""PreToolUse hook: inject RULE-tier lessons as reminders before code edits.

Disabled by default as of 2026-04-17 — SessionStart inject_brain_rules
already places rules in primacy position for the whole session, so
re-injecting on every edit is duplicative. Set
``GRADATA_RULE_ENFORCEMENT=1`` to re-enable if ablation shows recency
reinforcement genuinely improves compliance on long sessions.

Scope-prefilter (LLM-agnostic): rules that declare an explicit scope in
``scope_json`` (``file_glob``, ``applies_to``, or ``domain``) are filtered
against the file_path being edited. Rules with no scope declaration are
always included (preserves prior behavior). When *every* rule is filtered
out, the hook returns ``None`` and saves the entire injection budget for
that edit.
"""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

try:
    from gradata.enhancements.self_improvement import is_hook_enforced, parse_lessons
except ImportError:
    parse_lessons = None
    is_hook_enforced = None  # type: ignore[assignment]

HOOK_META = {
    "event": "PreToolUse",
    "matcher": "Write|Edit|MultiEdit",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}

MAX_REMINDERS = int(os.environ.get("GRADATA_MAX_REMINDERS", "5"))

_CODE_EXTS = frozenset({
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".rs", ".go", ".java", ".kt", ".scala", ".rb", ".php", ".swift",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".cs", ".m", ".mm",
    ".sh", ".bash", ".zsh", ".fish", ".lua", ".vue", ".svelte",
    ".sql", ".dart", ".ex", ".exs", ".clj", ".cljs", ".hs", ".ml",
})
_PROSE_EXTS = frozenset({".md", ".mdx", ".rst", ".txt", ".org"})
_DATA_EXTS = frozenset({".json", ".yaml", ".yml", ".toml", ".csv", ".tsv", ".xml"})


def _file_domain(file_path: str) -> str:
    """Heuristically classify a file path: ``code`` | ``prose`` | ``data`` | ``""``."""
    if not file_path:
        return ""
    suffix = Path(file_path).suffix.lower()
    if suffix in _CODE_EXTS:
        return "code"
    if suffix in _PROSE_EXTS:
        return "prose"
    if suffix in _DATA_EXTS:
        return "data"
    return ""


def _rule_applies(lesson, file_path: str, file_domain: str) -> bool:
    """Return True iff this rule should fire for this file edit.

    Conservative semantics: any unparseable / undeclared scope means "applies".
    Only an *explicit* declaration that conflicts with the file is grounds to skip.
    """
    if not lesson.scope_json:
        return True
    try:
        scope = json.loads(lesson.scope_json)
    except (json.JSONDecodeError, TypeError):
        return True
    if not isinstance(scope, dict):
        return True

    # 1) Explicit file glob
    glob = scope.get("file_glob") or scope.get("path_glob")
    if glob and file_path:
        if isinstance(glob, str):
            return fnmatch.fnmatch(file_path, glob)
        if isinstance(glob, list):
            return any(fnmatch.fnmatch(file_path, g) for g in glob if isinstance(g, str))

    # 2) Explicit applies_to prefix (e.g. "code:" or "code:src/")
    applies_to = scope.get("applies_to")
    if applies_to and isinstance(applies_to, str) and ":" in applies_to:
        decl_domain = applies_to.split(":", 1)[0].strip()
        if file_domain and decl_domain and decl_domain != file_domain:
            return False

    # 3) Explicit domain — only filter when file_domain is known AND mismatched
    decl_domain = scope.get("domain")
    return not (decl_domain and file_domain and decl_domain != file_domain)


def main(data: dict) -> dict | None:
    # Default-off: SessionStart primacy injection is the anchor. Opt in via
    # GRADATA_RULE_ENFORCEMENT=1 to re-enable per-edit recency reinforcement.
    if os.environ.get("GRADATA_RULE_ENFORCEMENT", "0") != "1":
        return None

    if parse_lessons is None:
        return None

    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    lessons_path = Path(brain_dir) / "lessons.md"
    if not lessons_path.is_file():
        return None

    tool_input = data.get("tool_input", {}) or {}
    file_path = str(tool_input.get("file_path") or "")
    file_domain = _file_domain(file_path)

    text = lessons_path.read_text(encoding="utf-8")
    all_lessons = parse_lessons(text)
    rule_lessons = [lesson for lesson in all_lessons if lesson.state.name == "RULE"]

    # Dedup: skip rules enforced by a generated PreToolUse hook (deterministic).
    if is_hook_enforced is not None:
        rule_lessons = [lesson for lesson in rule_lessons if not is_hook_enforced(lesson)]
    else:
        rule_lessons = [
            lesson for lesson in rule_lessons
            if not lesson.description.lstrip().startswith("[hooked]")
        ]

    # Scope-prefilter: drop rules whose declared scope conflicts with this file.
    rule_lessons = [l for l in rule_lessons if _rule_applies(l, file_path, file_domain)]

    if not rule_lessons:
        return None

    rules = []
    for lesson in rule_lessons[:MAX_REMINDERS]:
        desc = lesson.description
        truncated = desc[:120] + "..." if len(desc) > 120 else desc
        rules.append(f"[RULE:{lesson.confidence:.2f}] {lesson.category}: {truncated}")

    block = "ACTIVE RULES (learned from corrections):\n" + "\n".join(f"  • {r}" for r in rules)
    return {"result": block}


if __name__ == "__main__":
    run_hook(main, HOOK_META)
