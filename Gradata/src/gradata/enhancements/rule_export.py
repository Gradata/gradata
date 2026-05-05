"""Export graduated RULE-tier lessons to platform-specific rule files.

Supported targets:
- cursor    -> .cursorrules (freeform markdown rule-per-line)
- agents    -> AGENTS.md (markdown with headings + bullet rules)
- aider     -> .aider.conf.yml (YAML with custom system prompt rules)
- codex     -> .codex/AGENTS.md (Codex CLI rules, same AGENTS schema)
- cline     -> .clinerules (Cline rules file — single markdown)
- continue  -> .continue/rules/gradata-rules.md (Continue.dev rules)

Usage (library):
    from gradata.enhancements.rule_export import export_rules
    text = export_rules(brain_root, target="cursor")

Usage (CLI):
    gradata export --target cursor --output .cursorrules
"""

from __future__ import annotations

from pathlib import Path


def _parse_rules(brain_root: Path, *, lessons_path: Path | None = None) -> list[tuple[str, str]]:
    """Return [(category, description), ...] for every RULE-tier lesson.

    Delegates to the canonical lessons.md parser in self_improvement.py.

    If ``lessons_path`` is provided, it's used directly (letting callers plug in
    the canonical ``brain._find_lessons_path()`` result). Otherwise falls back
    to ``brain_root / "lessons.md"`` for back-compat with the library signature.
    """
    import re as _re

    from gradata.enhancements.self_improvement import parse_lessons

    lessons_file = lessons_path if lessons_path is not None else brain_root / "lessons.md"
    if not lessons_file.exists():
        return []
    # Legacy lessons.md files may carry a "[hooked]" marker between the
    # state bracket and the category. The canonical parser doesn't know about
    # it, so strip it before parsing (it's internal state, not rule text).
    # New code records the same state in ``lesson.metadata.how_enforced``.
    raw = lessons_file.read_text(encoding="utf-8")
    raw = _re.sub(r"(\[\w+:[\d.]+\])\s+\[hooked\]\s+", r"\1 ", raw)
    lessons = parse_lessons(raw)
    out: list[tuple[str, str]] = []
    for lesson in lessons:
        # Only RULE-tier
        state = getattr(lesson, "state", None)
        state_value = getattr(state, "value", state)
        if str(state_value).upper() != "RULE":
            continue
        category = getattr(lesson, "category", "") or ""
        description = getattr(lesson, "description", "") or ""
        description = _re.sub(r"^\[hooked\]\s*", "", description.strip())
        out.append((category, description))
    return out


def _format_cursor(rules: list[tuple[str, str]]) -> str:
    if not rules:
        return "# No graduated rules yet\n"
    lines = ["# Rules (graduated from Gradata)", ""]
    for _, desc in rules:
        lines.append(f"- {desc}")
    return "\n".join(lines) + "\n"


def _format_grouped_markdown(title: str, rules: list[tuple[str, str]]) -> str:
    """Render rules as a markdown doc with a title, intro, and ``## CATEGORY``
    sections of bullet points. Shared body for AGENTS.md / Codex / Cline /
    Continue.dev exports — they all consume the same schema (markdown
    appended to a system prompt), only the H1 title and output path differ.
    """
    if not rules:
        return f"# {title}\n\nNo graduated rules yet.\n"
    by_cat: dict[str, list[str]] = {}
    for cat, desc in rules:
        by_cat.setdefault(cat, []).append(desc)
    lines = [
        f"# {title}",
        "",
        "Graduated rules learned from corrections. Follow these in every response.",
        "",
    ]
    for cat in sorted(by_cat):
        lines.append(f"## {cat}")
        lines.append("")
        for desc in by_cat[cat]:
            lines.append(f"- {desc}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _format_aider(rules: list[tuple[str, str]]) -> str:
    """Emit a YAML block intended for `.aider.conf.yml`.

    Aider supports a `message` key that prepends instructions to every prompt.
    For v1 we emit a list of message strings — valid YAML, copy-pasteable.

    We serialize each description via ``json.dumps`` so backslashes, newlines,
    and other control characters in rule text produce a safely-quoted YAML
    double-quoted scalar (YAML's double-quoted form is a superset of JSON
    strings for these escapes).
    """
    if not rules:
        return "# No graduated rules yet\n"
    import json as _json

    yaml_lines = ["# Graduated rules from Gradata", "message:"]
    for _, desc in rules:
        # YAML 1.2 double-quoted scalars accept the same escape grammar as
        # JSON strings, so `json.dumps` gives us a valid scalar for any
        # description (handles quotes, backslashes, control chars, unicode).
        yaml_lines.append(f"  - {_json.dumps(desc, ensure_ascii=False)}")
    return "\n".join(yaml_lines) + "\n"


# Grouped-markdown targets share _format_grouped_markdown; each picks its
# own H1 title. Codex scopes to .codex/AGENTS.md to avoid collisions with
# a top-level AGENTS.md when multiple agent tools share a repo.
_GROUPED_MARKDOWN_TITLES = {
    "agents": "AGENTS.md",
    "codex": "Codex AGENTS.md",
    "cline": "Cline Rules",
    "continue": "Continue.dev Rules",
}


def _make_grouped_formatter(title: str):
    def _fmt(rules: list[tuple[str, str]]) -> str:
        return _format_grouped_markdown(title, rules)

    return _fmt


_FORMATTERS = {
    "cursor": _format_cursor,
    "aider": _format_aider,
    **{k: _make_grouped_formatter(v) for k, v in _GROUPED_MARKDOWN_TITLES.items()},
}


# Default relative output paths per target — used by the CLI when --output
# is not supplied, and documented for users who want the conventional path.
DEFAULT_PATHS: dict[str, str] = {
    "cursor": ".cursorrules",
    "agents": "AGENTS.md",
    "aider": ".aider.conf.yml",
    "codex": ".codex/AGENTS.md",
    "cline": ".clinerules",
    "continue": ".continue/rules/gradata-rules.md",
}


def export_rules(brain_root: Path, *, target: str, lessons_path: Path | None = None) -> str:
    """Return a formatted string of graduated rules for the given target.

    ``lessons_path`` overrides the default ``brain_root / "lessons.md"`` lookup,
    letting CLI callers pass the canonical ``brain._find_lessons_path()``
    result so the exporter doesn't bake the storage layout in.
    """
    if target not in _FORMATTERS:
        raise ValueError(f"unknown target: {target}. Supported: {list(_FORMATTERS)}")
    rules = _parse_rules(Path(brain_root), lessons_path=lessons_path)
    return _FORMATTERS[target](rules)
