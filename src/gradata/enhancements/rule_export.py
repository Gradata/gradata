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

import re
from pathlib import Path


_LESSON_RE = re.compile(
    r"^\[[\d-]+\]\s+\[RULE:[\d.]+\](?:\s+\[hooked\])?\s+(\w+):\s+(.+)$"
)


def _parse_rules(brain_root: Path) -> list[tuple[str, str]]:
    """Return [(category, description), ...] for every RULE-tier lesson."""
    lessons_file = brain_root / "lessons.md"
    if not lessons_file.exists():
        return []
    out = []
    for line in lessons_file.read_text(encoding="utf-8").splitlines():
        m = _LESSON_RE.match(line.strip())
        if not m:
            continue
        category, description = m.group(1), m.group(2).strip()
        # Strip any leading [hooked] from description (belt-and-suspenders)
        description = re.sub(r"^\[hooked\]\s*", "", description)
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


_FORMATTERS = {
    "cursor": _format_cursor,
    "agents": _format_agents,
    "aider": _format_aider,
}


def export_rules(brain_root: Path, *, target: str) -> str:
    """Return a formatted string of graduated rules for the given target."""
    if target not in _FORMATTERS:
        raise ValueError(
            f"unknown target: {target}. Supported: {list(_FORMATTERS)}"
        )
    rules = _parse_rules(Path(brain_root))
    return _FORMATTERS[target](rules)
