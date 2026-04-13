"""Manifest store for bundled generated-hook dispatch.

Each generated hooks directory (`GRADATA_HOOK_ROOT` for PreToolUse,
`GRADATA_HOOK_ROOT_POST` for PostToolUse) owns a `_manifest.json` of rule
entries + a single `_dispatcher.js`. The dispatcher evaluates every manifest
entry against one incoming tool payload in a single node process, replacing
N per-rule node spawns.

Each entry records exactly what the template needs:
    {
        "slug":          "never-use-em-dashes",
        "template":      "regex_replace",
        "template_arg":  "\u2014",
        "source_hash":   "abc123def456",
        "rule_text":     "Never use em dashes"
    }

We keep manifest reads and writes defensive: never raise on malformed data,
treat missing files as empty, and preserve entry order so blocked-rule output
is stable across sessions.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "_manifest.json"
DISPATCHER_FILENAME = "_dispatcher.js"
_DISPATCHER_TEMPLATE = (
    Path(__file__).parent / "templates" / DISPATCHER_FILENAME
)


def source_hash(text: str) -> str:
    """Same hash convention as rule_to_hook._source_hash — 12 hex chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _hook_root(kind: str = "pre") -> Path:
    """Resolve the generated-hook directory. Honors env overrides."""
    if kind == "post":
        override = os.environ.get("GRADATA_HOOK_ROOT_POST")
        return Path(override) if override else Path(".claude/hooks/post-tool/generated")
    override = os.environ.get("GRADATA_HOOK_ROOT")
    return Path(override) if override else Path(".claude/hooks/pre-tool/generated")


def manifest_path(kind: str = "pre") -> Path:
    return _hook_root(kind) / MANIFEST_FILENAME


def dispatcher_path(kind: str = "pre") -> Path:
    return _hook_root(kind) / DISPATCHER_FILENAME


def read_manifest(kind: str = "pre") -> list[dict[str, Any]]:
    """Return the manifest list (empty if missing or malformed)."""
    p = manifest_path(kind)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict) and e.get("slug")]


def write_manifest(entries: list[dict[str, Any]], kind: str = "pre") -> Path:
    """Atomically write the manifest. Creates the directory as needed."""
    p = manifest_path(kind)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, p)
    _ensure_dispatcher(kind)
    return p


def _ensure_dispatcher(kind: str = "pre") -> Path:
    """Copy the bundled dispatcher JS into the hook root if missing or stale."""
    dest = dispatcher_path(kind)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src_bytes = _DISPATCHER_TEMPLATE.read_bytes()
    except OSError:
        return dest  # best-effort; nothing more we can do
    if dest.exists():
        try:
            if dest.read_bytes() == src_bytes:
                return dest
        except OSError:
            pass
    dest.write_bytes(src_bytes)
    with contextlib.suppress(Exception):
        dest.chmod(0o755)
    return dest


def upsert_entry(
    *,
    slug: str,
    template: str,
    template_arg: str | None,
    rule_text: str,
    kind: str = "pre",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert or replace a manifest entry for this slug. Returns the entry."""
    entries = read_manifest(kind)
    new_entry: dict[str, Any] = {
        "slug": slug,
        "template": template,
        "template_arg": template_arg,
        "source_hash": source_hash(rule_text),
        "rule_text": rule_text,
    }
    if extra:
        new_entry.update(extra)
    out: list[dict[str, Any]] = []
    replaced = False
    for entry in entries:
        if entry.get("slug") == slug:
            out.append(new_entry)
            replaced = True
        else:
            out.append(entry)
    if not replaced:
        out.append(new_entry)
    write_manifest(out, kind)
    return new_entry


def remove_entry(slug: str, kind: str = "pre") -> bool:
    """Drop any manifest entry matching this slug. Returns True if removed."""
    entries = read_manifest(kind)
    keep = [e for e in entries if e.get("slug") != slug]
    if len(keep) == len(entries):
        return False
    write_manifest(keep, kind)
    return True


def find_entry(slug: str, kind: str = "pre") -> dict[str, Any] | None:
    for entry in read_manifest(kind):
        if entry.get("slug") == slug:
            return entry
    return None


def refresh_dispatcher(kind: str = "pre") -> Path:
    """Explicitly (re)deploy the dispatcher JS alongside the manifest."""
    return _ensure_dispatcher(kind)


def clear_dispatcher(kind: str = "pre") -> None:
    """Remove the dispatcher + manifest (used by uninstall/teardown tests)."""
    for p in (manifest_path(kind), dispatcher_path(kind)):
        with contextlib.suppress(FileNotFoundError):
            p.unlink()


def dispatcher_installed(kind: str = "pre") -> bool:
    return dispatcher_path(kind).exists() and manifest_path(kind).exists()


# ---------------------------------------------------------------------------
# Migration: rebuild a manifest from existing legacy per-file hooks.
# ---------------------------------------------------------------------------


def migrate_from_legacy_files(kind: str = "pre", *, delete_legacy: bool = False) -> dict[str, Any]:
    """Scan the hook root for generated .js files and reconstruct a manifest.

    Called by `gradata hooks migrate`. Idempotent: running twice yields the
    same manifest. Returns a summary dict describing what happened.

    If `delete_legacy=True`, removes the per-rule .js files after the manifest
    has been written (leaving only `_dispatcher.js` + `_manifest.json`).
    """
    import re

    root = _hook_root(kind)
    if not root.exists():
        return {"migrated": 0, "skipped": 0, "removed_legacy": 0, "root": str(root)}

    existing_slugs = {e.get("slug") for e in read_manifest(kind) if e.get("slug")}

    # Parse the header comment + pattern literal out of each legacy file.
    template_re = re.compile(r"^\s*\*\s*Template:\s*([A-Za-z0-9_]+)", re.MULTILINE)
    rule_re = re.compile(r"^\s*\*\s*Rule:\s*(.+)$", re.MULTILINE)
    hash_re = re.compile(r"^\s*\*\s*Source hash:\s*([0-9a-f]{12})", re.MULTILINE)
    limit_re = re.compile(r"const\s+limit\s*=\s*(\d+)\s*;")
    pattern_re = re.compile(r"const\s+pattern\s*=\s*new\s+RegExp\((.+?)\);\s*$", re.MULTILINE)

    migrated = 0
    skipped = 0
    legacy_files: list[Path] = []

    for js in sorted(root.glob("*.js")):
        if js.name in {DISPATCHER_FILENAME}:
            continue
        try:
            src = js.read_text(encoding="utf-8")
        except OSError:
            skipped += 1
            continue
        slug = js.stem
        if slug in existing_slugs:
            legacy_files.append(js)
            skipped += 1
            continue

        tmpl_m = template_re.search(src)
        rule_m = rule_re.search(src)
        if not tmpl_m or not rule_m:
            skipped += 1
            continue

        template = tmpl_m.group(1)
        rule_text = rule_m.group(1).strip()
        expected_hash = hash_re.search(src)
        expected_hash_val = expected_hash.group(1) if expected_hash else None

        template_arg: str | None = None
        if template == "file_size_check":
            lm = limit_re.search(src)
            if lm:
                template_arg = lm.group(1)
        else:
            pm = pattern_re.search(src)
            if pm:
                literal = pm.group(1).strip()
                # Pattern literal is the argument to `new RegExp(...)`,
                # which was produced via json.dumps — JSON strings are valid
                # JS string literals, so parse back to the underlying text.
                try:
                    template_arg = json.loads(literal)
                except json.JSONDecodeError:
                    template_arg = None

        entry_extra: dict[str, Any] = {}
        if expected_hash_val:
            entry_extra["legacy_source_hash"] = expected_hash_val

        upsert_entry(
            slug=slug,
            template=template,
            template_arg=template_arg,
            rule_text=rule_text,
            kind=kind,
            extra=entry_extra,
        )
        existing_slugs.add(slug)
        legacy_files.append(js)
        migrated += 1

    removed_legacy = 0
    if delete_legacy:
        for f in legacy_files:
            try:
                f.unlink()
                removed_legacy += 1
            except OSError:
                pass

    return {
        "migrated": migrated,
        "skipped": skipped,
        "removed_legacy": removed_legacy,
        "root": str(root),
    }


def rollback_dispatcher(kind: str = "pre") -> None:
    """Emergency rollback: remove manifest + dispatcher and leave legacy files."""
    clear_dispatcher(kind)


__all__ = [
    "DISPATCHER_FILENAME",
    "MANIFEST_FILENAME",
    "clear_dispatcher",
    "dispatcher_installed",
    "dispatcher_path",
    "find_entry",
    "manifest_path",
    "migrate_from_legacy_files",
    "read_manifest",
    "refresh_dispatcher",
    "remove_entry",
    "rollback_dispatcher",
    "source_hash",
    "upsert_entry",
    "write_manifest",
]
