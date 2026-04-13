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


def _parse_rules(brain_root: Path) -> list[tuple[str, str]]:
    """Return [(category, description), ...] for every RULE-tier lesson.

    Delegates to the canonical lessons.md parser in self_improvement.py.
    """
    import re as _re

    from gradata.enhancements.self_improvement import parse_lessons
    lessons_file = brain_root / "lessons.md"
    if not lessons_file.exists():
        return []
    # The [hooked] marker can appear between the state bracket and the
    # category. The canonical parser doesn't know about this marker, so we
    # strip it before parsing (it's internal metadata, not part of the rule).
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
    """
    if not rules:
        return "# No graduated rules yet\n"
    yaml_lines = ["# Graduated rules from Gradata", "message:"]
    for _, desc in rules:
        # Escape double quotes for YAML safety
        safe = desc.replace('"', '\\"')
        yaml_lines.append(f'  - "{safe}"')
    return "\n".join(yaml_lines) + "\n"


def _format_codex(rules: list[tuple[str, str]]) -> str:
    """Emit rules for the OpenAI Codex CLI.

    Codex CLI reads project-level ``AGENTS.md`` conventions. We scope the
    export to ``.codex/AGENTS.md`` (per DEFAULT_PATHS below) so it
    doesn't collide with an existing top-level AGENTS.md when a user
    runs multiple agent tools in the same repo.
    """
    if not rules:
        return "# Codex AGENTS.md\n\nNo graduated rules yet.\n"
    by_cat: dict[str, list[str]] = {}
    for cat, desc in rules:
        by_cat.setdefault(cat, []).append(desc)
    lines = [
        "# Codex AGENTS.md",
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


def _format_cline(rules: list[tuple[str, str]]) -> str:
    """Emit rules for Cline (.clinerules — single markdown file).

    Cline's ``.clinerules`` file at the repo root is consumed as custom
    instructions appended to the system prompt. Plain markdown with
    headings + bullets is the idiomatic format.
    """
    if not rules:
        return "# Cline Rules\n\nNo graduated rules yet.\n"
    by_cat: dict[str, list[str]] = {}
    for cat, desc in rules:
        by_cat.setdefault(cat, []).append(desc)
    lines = [
        "# Cline Rules",
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


def _format_continue(rules: list[tuple[str, str]]) -> str:
    """Emit rules for Continue.dev (.continue/rules/*.md).

    Continue's rules directory contains one or more markdown files whose
    contents are appended to the system prompt. We emit a single file
    (``gradata-rules.md``) grouped by category.
    """
    if not rules:
        return "# Continue.dev Rules\n\nNo graduated rules yet.\n"
    by_cat: dict[str, list[str]] = {}
    for cat, desc in rules:
        by_cat.setdefault(cat, []).append(desc)
    lines = [
        "# Continue.dev Rules",
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


_FORMATTERS = {
    "cursor": _format_cursor,
    "agents": _format_agents,
    "aider": _format_aider,
    "codex": _format_codex,
    "cline": _format_cline,
    "continue": _format_continue,
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


def export_rules(brain_root: Path, *, target: str) -> str:
    """Return a formatted string of graduated rules for the given target."""
    if target not in _FORMATTERS:
        raise ValueError(
            f"unknown target: {target}. Supported: {list(_FORMATTERS)}"
        )
    rules = _parse_rules(Path(brain_root))
    return _FORMATTERS[target](rules)
