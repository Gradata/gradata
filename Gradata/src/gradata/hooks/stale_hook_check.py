"""SessionStart hook: warn on generated hooks whose source text has changed.

Generated PreToolUse/PostToolUse hooks carry a `Source hash: <12chars>` line
in their header comment — sha256[:12] of the rule text at install time. If
the user edits the lesson text in lessons.md without running `gradata rule
remove` + `gradata rule add`, the hook silently keeps firing against the
old pattern. This check catches that drift at session start.

Never blocks: prints a warning, exits 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

from gradata._env import env_str

_HASH_LINE_RE = re.compile(r"^\s*\*\s*Source hash:\s*([0-9a-f]{12})", re.MULTILINE)
# Kept for legacy pattern detection only. All RULE-tier lesson shapes go
# through parse_lessons() below so legacy "[RULE] [hooked] CAT: desc" and
# categories with "/" are recognised consistently.
_LESSON_RE = re.compile(
    r"^\[[\d-]+\]\s+\[RULE:[\d.]+\]\s+(?:\[hooked\]\s+)?(?P<cat>[\w/\-]+):\s+(?P<desc>.+)$"
)


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "rule"


def _read_hash_from_hook(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = _HASH_LINE_RE.search(text)
    return m.group(1) if m else None


def _parse_lessons(brain_root: Path) -> tuple[dict[str, str], list[str]]:
    """Parse lessons.md via the canonical parser.

    Returns:
      (by_slug, hooked_texts) where:
        by_slug maps slug -> cleaned rule_text for ALL RULE-tier lessons.
        hooked_texts is the list of cleaned rule_texts for [hooked] lessons,
        in file order — used for fuzzy re-pairing when slugs have drifted.

    Uses parse_lessons() so legacy "[RULE:conf] [hooked] CATEGORY: desc" rows
    and categories containing slashes (e.g. "DRAFTING/FORMAT") are recognised
    the same way the main pipeline does. Also scans the raw file once for
    the line-level legacy "[hooked]" marker position that parse_lessons drops.
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

    # Pre-compute which cleaned descriptions were marked with the legacy
    # "[hooked]" token (between state-bracket and category) — parse_lessons
    # doesn't preserve this, so we scan lines directly.
    legacy_hooked_descs: set[str] = set()
    for line in content.splitlines():
        m = _LESSON_RE.match(line.strip())
        if not m:
            continue
        desc = m.group("desc").strip()
        # Detect if this row had the legacy token position.
        if re.search(r"\[RULE:[\d.]+\]\s+\[hooked\]\s+", line):
            clean = desc[len("[hooked] ") :] if desc.startswith("[hooked] ") else desc
            legacy_hooked_descs.add(clean)

    try:
        from gradata.enhancements.self_improvement import parse_lessons
    except Exception:
        parse_lessons = None  # type: ignore[assignment]

    if parse_lessons is not None:
        try:
            lessons = parse_lessons(content)
        except Exception:
            lessons = []
        for lesson in lessons:
            state = getattr(lesson, "state", None)
            state_value = getattr(state, "value", state)
            if str(state_value).upper() != "RULE":
                continue
            desc = (getattr(lesson, "description", "") or "").strip()
            modern_hooked = desc.startswith("[hooked] ")
            clean = desc[len("[hooked] ") :] if modern_hooked else desc
            by_slug[_slug(clean)] = clean
            if modern_hooked or clean in legacy_hooked_descs:
                hooked.append(clean)
        return by_slug, hooked

    # Fallback: parser unavailable — use the regex directly (preserves
    # legacy behaviour for minimal embeddings without the full SDK).
    for line in content.splitlines():
        m = _LESSON_RE.match(line.strip())
        if not m:
            continue
        desc = m.group("desc").strip()
        is_hooked = desc.startswith("[hooked] ") or re.search(
            r"\[RULE:[\d.]+\]\s+\[hooked\]\s+", line
        )
        clean = desc[len("[hooked] ") :] if desc.startswith("[hooked] ") else desc
        by_slug[_slug(clean)] = clean
        if is_hooked:
            hooked.append(clean)
    return by_slug, hooked


def _brain_root() -> Path:
    override = env_str("BRAIN_DIR") or env_str("GRADATA_BRAIN")
    if override:
        return Path(override)
    return Path.home() / ".gradata" / "brain"


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _extract_brain_dir_from_command(command: str) -> Path | None:
    """Return the BRAIN_DIR assignment from a Gradata hook command, if any.

    Do not run the whole command through ``shlex.split(posix=True)``: on
    Windows-style paths it treats backslashes as escapes and corrupts paths like
    ``C:\\Users\\...`` into ``C:Users...``. Extract the assignment first, then
    only unquote the value when the user explicitly quoted it.
    """
    if "gradata.hooks." not in command or "BRAIN_DIR=" not in command:
        return None
    match = re.search(r"(?:^|\s)BRAIN_DIR=(?P<value>'[^']*'|\"[^\"]*\"|\S+)", command)
    if not match:
        return None
    value = match.group("value").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            value = shlex.split(value, posix=True)[0]
        except (IndexError, ValueError):
            value = value[1:-1]
    if not value:
        return None
    return Path(value).expanduser()


def _missing_hook_brain_dirs(settings_path: Path | None = None) -> list[Path]:
    """Find Gradata hook BRAIN_DIR targets in Claude settings that no longer exist."""
    if settings_path is None and (
        env_str("GRADATA_HOOK_ROOT") or env_str("GRADATA_HOOK_ROOT_POST")
    ):
        # Test/dev hook roots are intentionally isolated; do not let a developer's
        # real ~/.claude/settings.json leak warnings into those runs.
        return []
    path = settings_path or _settings_path()
    settings = _read_settings(path)
    if not settings:
        return []
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return []
    missing: list[Path] = []
    seen: set[str] = set()
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                brain_dir = _extract_brain_dir_from_command(str(hook.get("command", "")))
                if brain_dir is None or brain_dir.exists():
                    continue
                key = brain_dir.as_posix()
                if key not in seen:
                    missing.append(brain_dir)
                    seen.add(key)
    return missing


def _read_settings(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return settings if isinstance(settings, dict) else None


def _remove_missing_hook_brain_dirs(settings_path: Path | None = None) -> list[Path]:
    """Remove Gradata hook commands whose BRAIN_DIR targets no longer exist."""
    path = settings_path or _settings_path()
    settings = _read_settings(path)
    if not settings:
        return []
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    removed: list[Path] = []
    seen: set[str] = set()
    for event in list(hooks):
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        kept_groups: list = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            group_hooks = group.get("hooks")
            if not isinstance(group_hooks, list):
                kept_groups.append(group)
                continue
            kept_hook_entries: list = []
            for hook in group_hooks:
                if not isinstance(hook, dict):
                    kept_hook_entries.append(hook)
                    continue
                brain_dir = _extract_brain_dir_from_command(str(hook.get("command", "")))
                if brain_dir is None or brain_dir.exists():
                    kept_hook_entries.append(hook)
                    continue
                key = brain_dir.as_posix()
                if key not in seen:
                    removed.append(brain_dir)
                    seen.add(key)
            if kept_hook_entries:
                new_group = dict(group)
                new_group["hooks"] = kept_hook_entries
                kept_groups.append(new_group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            hooks.pop(event, None)
    if removed:
        if hooks:
            settings["hooks"] = hooks
        else:
            settings.pop("hooks", None)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return removed


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

    stale: list[
        tuple[str, Path, str, str, str]
    ] = []  # (slug, path, hook_hash, current_hash, fix_text)
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
            # shlex.quote the user-controlled text so the printed command is
            # safe to copy/paste into a POSIX shell even if the rule text
            # contains quotes, backticks, or other shell metacharacters.
            safe_slug = shlex.quote(slug)
            safe_text = shlex.quote(current_text)
            print(f"      fix:     gradata rule remove {safe_slug} && gradata rule add {safe_text}")
            print()

    missing_brain_dirs = _missing_hook_brain_dirs()
    if missing_brain_dirs:
        print("Gradata: stale Claude settings hook warnings")
        print("These Gradata hooks point at brain directories that no longer exist.")
        print("Reinstall hooks so corrections are written to the active production brain.")
        print()
        for path in missing_brain_dirs:
            print(f"  - missing BRAIN_DIR: {path}")
        target_brain = env_str("GRADATA_BRAIN") or env_str("BRAIN_DIR") or "~/.gradata/brain"
        print(
            f"      fix:     gradata install --agent claude-code --brain {shlex.quote(target_brain)}"
        )
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
