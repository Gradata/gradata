"""
CARL Rule Compiler — AIOS Brain Portability Layer
==================================================
Reads CARL rules from .carl/ files and compiles them into
platform-specific formats for different AI agent platforms.

Brain layer (brain/) is universal. This compiler bridges
brain rules to runtime-specific instruction formats.

Usage:
    python runtime/carl-compiler.py --format claude
    python runtime/carl-compiler.py --format cursor
    python runtime/carl-compiler.py --format api
    python runtime/carl-compiler.py --format markdown
    python runtime/carl-compiler.py --all
    python runtime/carl-compiler.py --all --include-domain
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CARL_DIR = Path(__file__).resolve().parent.parent / ".carl"
DOMAIN_CARL_DIR = Path(__file__).resolve().parent.parent / "domain" / "carl"
OUTPUT_DIR = Path(__file__).resolve().parent / "compiled"

# Files to skip (not rule files)
SKIP_FILES = {"manifest", "sessions", "example-custom-domain"}

# Priority ordering for output
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2}
DEFAULT_PRIORITY = "NORMAL"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_carl_file(filepath: Path) -> list[dict]:
    """Parse a single CARL file and extract rules.

    CARL format:
        RULENAME=rule text
        RULENAME_PRIORITY=CRITICAL|HIGH|NORMAL

    Rules without an explicit _PRIORITY line default to NORMAL.
    Lines starting with # are comments. Blank lines are ignored.
    Manifest-style config lines (STATE, ALWAYS_ON, RECALL, EXCLUDE,
    READS, WRITES, REQUIRES, FILE, DOMAIN_FILE, MODE, DEVMODE) are skipped.
    """
    if not filepath.is_file():
        return []

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Collect all KEY=VALUE pairs (skip comments and blanks)
    pairs: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Z][A-Z0-9_]+)=(.+)$", stripped)
        if match:
            pairs[match.group(1)] = match.group(2)

    # Identify which keys are actual rules vs. priorities vs. config
    config_suffixes = (
        "_STATE", "_ALWAYS_ON", "_RECALL", "_EXCLUDE", "_FILE",
        "_DOMAIN_FILE", "_READS", "_WRITES", "_REQUIRES", "_MODE",
    )
    config_prefixes = ("DEVMODE",)

    priority_keys = {k for k in pairs if k.endswith("_PRIORITY")}

    rule_keys = []
    for key in pairs:
        if key in priority_keys:
            continue
        if any(key.endswith(s) for s in config_suffixes):
            continue
        if key in config_prefixes:
            continue
        rule_keys.append(key)

    # Build rule objects — include parent dir to distinguish .carl/ from domain/carl/
    parent_name = filepath.parent.name
    if parent_name == ".carl":
        source = f".carl/{filepath.name}"
    else:
        source = f"domain/carl/{filepath.name}"

    rules = []
    for key in rule_keys:
        priority_key = f"{key}_PRIORITY"
        priority = pairs.get(priority_key, DEFAULT_PRIORITY)
        rules.append({
            "name": key,
            "priority": priority,
            "text": pairs[key],
            "source": source,
        })

    return rules


def load_all_rules(include_domain: bool = False) -> list[dict]:
    """Load rules from all CARL files.

    Args:
        include_domain: If True, also load domain/carl/ files.
    """
    rules = []

    # Core .carl/ files
    if CARL_DIR.is_dir():
        for entry in sorted(CARL_DIR.iterdir()):
            if entry.name in SKIP_FILES:
                continue
            if entry.is_file():
                rules.extend(parse_carl_file(entry))

    # Domain-specific CARL files
    if include_domain and DOMAIN_CARL_DIR.is_dir():
        for entry in sorted(DOMAIN_CARL_DIR.iterdir()):
            if entry.is_file():
                rules.extend(parse_carl_file(entry))

    return rules


def sort_rules(rules: list[dict]) -> list[dict]:
    """Sort rules by priority (CRITICAL first), then by name."""
    return sorted(rules, key=lambda r: (
        PRIORITY_ORDER.get(r["priority"], 99),
        r["name"],
    ))


# ---------------------------------------------------------------------------
# Compilers
# ---------------------------------------------------------------------------

def compile_claude(rules: list[dict]) -> str:
    """Claude Code format (CLAUDE.md style)."""
    rules = sort_rules(rules)
    lines = [
        "## CARL Rules",
        f"<!-- Compiled {datetime.now().strftime('%Y-%m-%d %H:%M')} by carl-compiler.py -->",
        "",
    ]
    for r in rules:
        lines.append(f"* **{r['name']}** [{r['priority']}] — {r['text']}")
    lines.append("")
    return "\n".join(lines)


def compile_cursor(rules: list[dict]) -> str:
    """Cursor format (.cursorrules style) — flat markdown grouped by priority."""
    rules = sort_rules(rules)
    lines = [
        "# Rules",
        f"<!-- Compiled {datetime.now().strftime('%Y-%m-%d %H:%M')} by carl-compiler.py -->",
        "",
    ]

    grouped: dict[str, list[dict]] = {}
    for r in rules:
        grouped.setdefault(r["priority"], []).append(r)

    for priority in ["CRITICAL", "HIGH", "NORMAL"]:
        group = grouped.get(priority)
        if not group:
            continue
        lines.append(f"## {priority.title()}")
        lines.append("")
        for r in group:
            lines.append(f"- {r['text']}")
        lines.append("")

    return "\n".join(lines)


def compile_api(rules: list[dict]) -> str:
    """API/system prompt format (JSON)."""
    rules = sort_rules(rules)
    payload = {
        "compiled": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "compiler": "carl-compiler.py",
        "rule_count": len(rules),
        "rules": [
            {
                "name": r["name"],
                "priority": r["priority"],
                "text": r["text"],
                "source": r["source"],
            }
            for r in rules
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def compile_markdown(rules: list[dict]) -> str:
    """Generic markdown format — numbered list grouped by priority."""
    rules = sort_rules(rules)
    lines = [
        "# Agent Rules (compiled from CARL)",
        f"<!-- Compiled {datetime.now().strftime('%Y-%m-%d %H:%M')} by carl-compiler.py -->",
        "",
    ]

    grouped: dict[str, list[dict]] = {}
    for r in rules:
        grouped.setdefault(r["priority"], []).append(r)

    counter = 1
    priority_labels = {
        "CRITICAL": "CRITICAL (always active)",
        "HIGH": "HIGH (load at startup)",
        "NORMAL": "NORMAL (on demand)",
    }

    for priority in ["CRITICAL", "HIGH", "NORMAL"]:
        group = grouped.get(priority)
        if not group:
            continue
        lines.append(f"## {priority_labels.get(priority, priority)}")
        lines.append("")
        for r in group:
            lines.append(f"{counter}. {r['text']}")
            counter += 1
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

COMPILERS = {
    "claude": (compile_claude, "claude-rules.md"),
    "cursor": (compile_cursor, ".cursorrules"),
    "api": (compile_api, "rules.json"),
    "markdown": (compile_markdown, "rules.md"),
}


def write_output(format_name: str, rules: list[dict], quiet: bool = False) -> Path:
    """Compile and write a single format to disk."""
    compiler_fn, filename = COMPILERS[format_name]
    content = compiler_fn(rules)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outpath = OUTPUT_DIR / filename
    outpath.write_text(content, encoding="utf-8")

    if not quiet:
        print(f"  [{format_name}] {len(rules)} rules -> {outpath}")
    return outpath


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CARL Rule Compiler — compile AIOS rules for different AI platforms",
    )
    parser.add_argument(
        "--format",
        choices=list(COMPILERS.keys()),
        help="Target platform format",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Compile all formats",
    )
    parser.add_argument(
        "--include-domain",
        action="store_true",
        help="Include domain/carl/ rules (domain-specific)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output to stdout instead of writing files",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print rule statistics and exit",
    )

    args = parser.parse_args()

    if not args.format and not args.all and not args.stats:
        parser.print_help()
        return

    # Load rules
    rules = load_all_rules(include_domain=args.include_domain)

    if not rules:
        print("No rules found. Check that .carl/ directory exists.")
        return

    # Stats mode
    if args.stats:
        print(f"Total rules: {len(rules)}")
        by_priority: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in rules:
            by_priority[r["priority"]] = by_priority.get(r["priority"], 0) + 1
            by_source[r["source"]] = by_source.get(r["source"], 0) + 1
        print("\nBy priority:")
        for p in ["CRITICAL", "HIGH", "NORMAL"]:
            if p in by_priority:
                print(f"  {p}: {by_priority[p]}")
        print("\nBy source file:")
        for src, count in sorted(by_source.items()):
            print(f"  {src}: {count}")
        return

    # Compile
    formats = list(COMPILERS.keys()) if args.all else [args.format]

    print(f"Compiling {len(rules)} CARL rules...")
    if args.include_domain:
        print("  (including domain/carl/ rules)")

    for fmt in formats:
        if args.dry_run:
            compiler_fn, filename = COMPILERS[fmt]
            print(f"\n--- {fmt} ({filename}) ---")
            print(compiler_fn(rules))
        else:
            write_output(fmt, rules)

    if not args.dry_run:
        print("Done.")


if __name__ == "__main__":
    main()
