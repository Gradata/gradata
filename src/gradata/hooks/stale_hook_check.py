"""SessionStart hook: warn on generated hooks whose source text has changed.

Generated PreToolUse/PostToolUse hooks carry a `Source hash: <12chars>` line
in their header comment — sha256[:12] of the rule text at install time. If
the user edits the lesson text in lessons.md without running `gradata rule
remove` + `gradata rule add`, the hook silently keeps firing against the
old pattern. This check catches that drift at session start.

Never blocks: prints a warning, exits 0.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from gradata.enhancements.rule_to_hook import _slug, _source_hash

_HASH_LINE_RE = re.compile(r"^\s*\*\s*Source hash:\s*([0-9a-f]{12})", re.MULTILINE)
_LESSON_RE = re.compile(
    r"^\[[\d-]+\]\s+\[RULE:[\d.]+\]\s+\w+:\s+(.+)$"
)


def _read_hash_from_hook(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = _HASH_LINE_RE.search(text)
    return m.group(1) if m else None


def _parse_lessons(brain_root: Path) -> tuple[dict[str, str], list[str]]:
    """Parse lessons.md.

    Returns:
      (by_slug, hooked_texts) where:
        by_slug maps slug -> cleaned rule_text for ALL RULE-tier lessons.
        hooked_texts is the list of cleaned rule_texts for [hooked] lessons,
        in file order — used for fuzzy re-pairing when slugs have drifted.
    """
    lessons_file = brain_root / "lessons.md"
    by_slug: dict[str, str] = {}
    hooked: list[str] = []
    if not lessons_file.exists():
        return by_slug, hooked
    try:
        content = lessons_file.read_text(encoding="utf-8")
    except Exception:
        return by_slug, hooked
    for line in content.splitlines():
        m = _LESSON_RE.match(line.strip())
        if not m:
            continue
        desc = m.group(1).strip()
        is_hooked = desc.startswith("[hooked] ")
        clean = desc[len("[hooked] "):] if is_hooked else desc
        by_slug[_slug(clean)] = clean
        if is_hooked:
            hooked.append(clean)
    return by_slug, hooked


def _brain_root() -> Path:
    override = os.environ.get("GRADATA_BRAIN")
    if override:
        return Path(override)
    return Path("brain")


def _hook_dirs() -> list[Path]:
    pre = os.environ.get("GRADATA_HOOK_ROOT") or ".claude/hooks/pre-tool/generated"
    post = os.environ.get("GRADATA_HOOK_ROOT_POST") or ".claude/hooks/post-tool/generated"
    return [Path(pre), Path(post)]


def main() -> int:
    # Read stdin payload (Claude Code sends SessionStart JSON); we ignore it.
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    brain_root = _brain_root()
    lessons_by_slug, hooked_texts = _parse_lessons(brain_root)

    # Slugs of lessons that are already matched by an exact-slug hook — these
    # should not be re-used for fuzzy orphan pairing.
    all_hook_slugs: set[str] = set()
    for d in _hook_dirs():
        if d.exists():
            for p in d.glob("*.js"):
                all_hook_slugs.add(p.stem)

    # Hooked lessons that don't have an exact-slug hook counterpart — these
    # are candidates for fuzzy pairing (rule text edited, slug drifted).
    orphan_hooked_texts = [t for t in hooked_texts if _slug(t) not in all_hook_slugs]

    stale: list[tuple[str, Path, str, str, str]] = []  # (slug, path, hook_hash, current_hash, fix_text)
    orphan_idx = 0
    for d in _hook_dirs():
        if not d.exists():
            continue
        for hook_path in sorted(d.glob("*.js")):
            slug = hook_path.stem
            hook_hash = _read_hash_from_hook(hook_path)
            if not hook_hash:
                continue
            current_text = lessons_by_slug.get(slug)
            if current_text is None:
                # No exact-slug match. Try to pair with an orphan [hooked]
                # lesson (rule text was edited, slug changed).
                if orphan_idx < len(orphan_hooked_texts):
                    current_text = orphan_hooked_texts[orphan_idx]
                    orphan_idx += 1
                else:
                    # No candidate pairing available; treat as orphan, skip.
                    continue
            current_hash = _source_hash(current_text)
            if current_hash != hook_hash:
                stale.append((slug, hook_path, hook_hash, current_hash, current_text))

    if stale:
        print("Gradata: stale rule-to-hook warnings")
        print("These hooks were installed from an older rule text. The lesson")
        print("description in lessons.md has changed, but the hook file hasn't")
        print("been regenerated.")
        print()
        for slug, path, old_hash, new_hash, current_text in stale:
            print(f"  - {slug}")
            print(f"      hook:    {path}")
            print(f"      hash:    {old_hash} (installed) -> {new_hash} (current)")
            print(f"      fix:     gradata rule remove {slug} && gradata rule add \"{current_text}\"")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
