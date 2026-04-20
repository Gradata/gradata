"""Migrate legacy lessons that lack ``scope_json.domain``.

Council verdict 4/4 STRICT (Phase 2 scoped brains): the category-as-domain
fallback has been removed from ``gradata._scoped_brain`` and
``gradata.rules.rule_context``. Legacy lessons that relied on the fallback
will no longer surface under ``brain.scope(<domain>)`` until their
``scope_json.domain`` is populated.

This script inspects a brain's ``lessons.md`` and, for each lesson whose
``scope_json`` is empty OR missing a ``domain`` key:

- if the lesson's ``category`` matches exactly one configured domain from
  ``domains.yaml`` (or the inferred set of distinct categories in the file),
  it rewrites ``scope_json`` to set ``domain = category.lower()``;
- if the category is ambiguous (``MIXED``, ``OTHER``, ``GENERAL``, or
  matches more than one configured domain), the lesson is flagged for
  manual review and left untouched;
- lessons whose ``scope_json.domain`` is already set are skipped.

Usage::

    # dry run (default)
    python scripts/migrate_legacy_scopes.py --brain ./brain

    # write changes
    python scripts/migrate_legacy_scopes.py --brain ./brain --apply

    # explicit domains list
    python scripts/migrate_legacy_scopes.py --brain ./brain \\
        --domains-file domains.yaml --apply

No external deps beyond the SDK. ``domains.yaml`` support is optional; if
PyYAML is not available the script falls back to inferring the domain set
from the distinct ``category`` values present in the file.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

# Make the SDK importable when the script is run from a checkout without
# the package installed in editable mode.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from gradata.enhancements.self_improvement import (
    format_lessons,
    parse_lessons,
)

if TYPE_CHECKING:
    from gradata._types import Lesson

logger = logging.getLogger("migrate_legacy_scopes")

AMBIGUOUS_CATEGORIES: frozenset[str] = frozenset(
    {"mixed", "other", "general", "misc", "unknown", ""}
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class MigrationResult:
    migrated: int = 0
    flagged: int = 0
    skipped: int = 0
    flagged_entries: list[tuple[str, str]] = None  # (category, description_snippet)

    def __post_init__(self) -> None:
        if self.flagged_entries is None:
            self.flagged_entries = []

    def as_dict(self) -> dict:
        return {
            "migrated": self.migrated,
            "flagged": self.flagged,
            "skipped": self.skipped,
            "flagged_entries": list(self.flagged_entries),
        }


# ---------------------------------------------------------------------------
# Core planning logic (pure function, unit-tested)
# ---------------------------------------------------------------------------


def load_domain_set(
    lessons: Iterable[Lesson],
    domains_file: Path | None = None,
) -> set[str]:
    """Return the set of lower-cased valid domains.

    If ``domains_file`` exists and PyYAML is available, the file is parsed
    (expected to be a YAML list under key ``domains`` or a top-level list).
    Otherwise the domain set is inferred from distinct, unambiguous
    ``category`` values observed across ``lessons``.
    """
    if domains_file and domains_file.is_file():
        try:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(domains_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "domains" in data:
                data = data["domains"]
            if isinstance(data, list):
                return {str(d).strip().lower() for d in data if str(d).strip()}
        except ImportError:
            logger.warning(
                "PyYAML not installed; falling back to inferred domain set."
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not parse %s: %s", domains_file, exc)

    inferred: set[str] = set()
    for l in lessons:
        cat = (l.category or "").strip().lower()
        if cat and cat not in AMBIGUOUS_CATEGORIES:
            inferred.add(cat)
    return inferred


def _has_domain(lesson: Lesson) -> bool:
    """True if the lesson already has scope_json.domain set."""
    if not lesson.scope_json:
        return False
    try:
        data = json.loads(lesson.scope_json)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict):
        return False
    return bool(str(data.get("domain", "")).strip())


def plan_migration(
    lessons: list[Lesson],
    domains: set[str],
) -> tuple[list[Lesson], MigrationResult]:
    """Return (new_lessons, result). Pure — does not touch disk.

    New lessons list preserves order. Each lesson is either unchanged or
    has a new ``scope_json`` with ``domain`` populated.
    """
    result = MigrationResult()
    out: list[Lesson] = []

    for l in lessons:
        if _has_domain(l):
            result.skipped += 1
            out.append(l)
            continue

        cat = (l.category or "").strip().lower()
        if cat in AMBIGUOUS_CATEGORIES or cat not in domains:
            result.flagged += 1
            result.flagged_entries.append((l.category or "", (l.description or "")[:80]))
            out.append(l)
            continue

        # Unambiguous match: merge existing scope_json if any, add domain
        merged: dict = {}
        if l.scope_json:
            try:
                parsed = json.loads(l.scope_json)
                if isinstance(parsed, dict):
                    merged.update(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        merged["domain"] = cat

        # dataclasses are mutable by default; update in place via replacement
        from dataclasses import replace

        out.append(replace(l, scope_json=json.dumps(merged, sort_keys=True)))
        result.migrated += 1

    return out, result


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _find_lessons_path(brain_dir: Path) -> Path:
    """Locate lessons.md inside a brain directory."""
    candidates = [brain_dir / "lessons.md", brain_dir / "brain" / "lessons.md"]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        f"No lessons.md found in {brain_dir} (tried: {[str(c) for c in candidates]})"
    )


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy lessons that lack scope_json.domain."
    )
    parser.add_argument(
        "--brain",
        type=Path,
        default=Path("./brain"),
        help="Path to the brain directory (contains lessons.md). Default: ./brain",
    )
    parser.add_argument(
        "--domains-file",
        type=Path,
        default=None,
        help="Optional YAML file listing valid domains. Falls back to inference.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to lessons.md. Without this flag the script is a dry run.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        lessons_path = _find_lessons_path(args.brain)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2

    raw = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(raw)
    domains = load_domain_set(lessons, args.domains_file)

    if not domains:
        logger.warning(
            "No domains resolved (empty domains.yaml and no unambiguous categories). "
            "All legacy lessons will be flagged."
        )

    new_lessons, result = plan_migration(lessons, domains)

    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("=== migrate_legacy_scopes [%s] ===", mode)
    logger.info("brain: %s", args.brain)
    logger.info("lessons.md: %s", lessons_path)
    logger.info("domains: %s", sorted(domains) or "<empty>")
    logger.info("total lessons: %d", len(lessons))
    logger.info("  migrated: %d", result.migrated)
    logger.info("  flagged for manual review: %d", result.flagged)
    logger.info("  skipped (already had domain): %d", result.skipped)

    if result.flagged_entries and args.verbose:
        logger.debug("flagged entries:")
        for cat, snippet in result.flagged_entries[:20]:
            logger.debug("  [%s] %s", cat, snippet)

    if args.apply and result.migrated > 0:
        from gradata._db import write_lessons_safe

        write_lessons_safe(lessons_path, format_lessons(new_lessons))
        logger.info("wrote %d migrated lessons to %s", result.migrated, lessons_path)
    elif not args.apply:
        logger.info("(dry-run) re-run with --apply to write changes")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
