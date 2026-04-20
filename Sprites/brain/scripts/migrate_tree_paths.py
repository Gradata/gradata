"""
Migrate existing brain lessons to hierarchical tree paths.
============================================================
Reads lessons.md, computes tree path for each lesson from
category + scope, writes updated lessons.md with Path: lines.

Usage:
    python migrate_tree_paths.py [brain_dir]

    Defaults to C:/Users/olive/SpritesWork/brain if no arg given.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def build_path(category: str, domain: str, task_type: str) -> str:
    """Build tree path from category/domain/task_type."""
    segments = []
    if category:
        segments.append(category.upper())
    if domain:
        segments.append(domain.lower())
    if task_type:
        segments.append(task_type.lower())
    return "/".join(segments)


def migrate_lessons_file(lessons_path: Path) -> dict:
    """Add Path: lines to lessons that don't have them.

    Returns: {"total": N, "migrated": N, "already_had_path": N, "no_scope": N}
    """
    if not lessons_path.exists():
        return {"total": 0, "migrated": 0, "already_had_path": 0, "no_scope": 0}

    text = lessons_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    stats = {"total": 0, "migrated": 0, "already_had_path": 0, "no_scope": 0}

    # Regex for lesson header: [DATE] [STATE:CONF] CATEGORY: description
    lesson_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\]\s+\[(\w+):?([\d.]*)\]\s+(\w+):\s+(.*)")

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = lesson_re.match(line)
        if not m:
            new_lines.append(line)
            i += 1
            continue

        stats["total"] += 1
        category = m.group(4).upper()

        # Collect metadata lines
        meta_lines = [line]
        j = i + 1
        has_path = False
        has_scope = False
        scope_json = ""

        while j < len(lines) and lines[j].startswith("  "):
            meta_line = lines[j]
            meta_lines.append(meta_line)
            if meta_line.strip().startswith("Path:"):
                has_path = True
            if meta_line.strip().startswith("Scope:"):
                has_scope = True
                scope_json = meta_line.strip()[len("Scope:") :].strip()
            j += 1

        if has_path:
            stats["already_had_path"] += 1
            new_lines.extend(meta_lines)
        else:
            # Build path from category + scope
            domain = ""
            task_type = ""
            if scope_json:
                try:
                    scope = json.loads(scope_json)
                    domain = scope.get("domain", "")
                    task_type = scope.get("task_type", "")
                except (json.JSONDecodeError, TypeError):
                    pass

            path = build_path(category, domain, task_type)

            if path:
                # Insert Path: line after the header
                new_lines.append(meta_lines[0])  # header
                new_lines.append(f"  Path: {path}")
                new_lines.extend(meta_lines[1:])  # rest of metadata
                stats["migrated"] += 1
            else:
                stats["no_scope"] += 1
                new_lines.extend(meta_lines)

        i = j

    # Write back
    lessons_path.write_text("\n".join(new_lines), encoding="utf-8")
    return stats


def main():
    brain_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("C:/Users/olive/SpritesWork/brain")
    lessons_path = brain_dir / "lessons.md"

    if not lessons_path.exists():
        print(f"No lessons.md found at {lessons_path}")
        return

    print(f"Migrating {lessons_path}...")
    stats = migrate_lessons_file(lessons_path)
    print(f"Done: {stats}")
    print(f"  Total lessons: {stats['total']}")
    print(f"  Migrated (path added): {stats['migrated']}")
    print(f"  Already had path: {stats['already_had_path']}")
    print(f"  No scope (category-only path): {stats['no_scope']}")


if __name__ == "__main__":
    main()
