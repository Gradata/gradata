"""Export graduated RULE-tier lessons to platform-specific rule files.

Supported targets:
- cursor    -> .cursorrules (freeform markdown rule-per-line)
- agents    -> AGENTS.md (markdown with headings + bullet rules)
- aider     -> .aider.conf.yml (YAML with custom system prompt rules)

Usage (library):
    from gradata.enhancements.rule_export import export_rules
    text = export_rules(brain_root, target="cursor")

Usage (CLI):
    gradata export --target cursor --output .cursorrules
"""
from __future__ import annotations

from pathlib import Path


def _parse_rules(
    brain_root: Path, *, lessons_path: Path | None = None
) -> list[tuple[str, str]]:
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


def _format_agents(rules: list[tuple[str, str]]) -> str:
    if not rules:
        return "# AGENTS.md\n\nNo graduated rules yet.\n"
    # Group by category for readability
    by_cat: dict[str, list[str]] = {}
    for cat, desc in rules:
        by_cat.setdefault(cat, []).append(desc)
    lines = [
        "# AGENTS.md",
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
    import json as _json

    if not rules:
        return "# No graduated rules yet\n"
    yaml_lines = ["# Graduated rules from Gradata", "message:"]
    for _, desc in rules:
        yaml_lines.append(f"  - {_json.dumps(desc)}")
    return "\n".join(yaml_lines) + "\n"


_FORMATTERS = {
    "cursor": _format_cursor,
    "agents": _format_agents,
    "aider": _format_aider,
}


def export_rules(
    brain_root: Path, *, target: str, lessons_path: Path | None = None
) -> str:
    """Return a formatted string of graduated rules for the given target.

    ``lessons_path`` overrides the default ``brain_root / "lessons.md"`` lookup,
    letting CLI callers pass the canonical ``brain._find_lessons_path()``
    result so the exporter doesn't bake the storage layout in.
    """
    if target not in _FORMATTERS:
        raise ValueError(f"unknown target: {target}. Supported: {list(_FORMATTERS)}")
    rules = _parse_rules(Path(brain_root), lessons_path=lessons_path)
    return _FORMATTERS[target](rules)
