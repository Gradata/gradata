"""Bridge: memory feedback files → brain lessons.md.

The memory system (MEMORY.md + feedback_*.md files) and the lesson system
(brain/lessons.md → graduation pipeline) are two parallel tracks that
never merge. This module closes the loop.

When a user corrects Claude Code, the correction gets saved as a memory
feedback file (e.g., feedback_always_plan_first.md). But that file never
enters the lessons.md graduation pipeline, so the correction never becomes
an enforced rule.

This bridge:
1. Scans feedback_*.md files from a memory directory
2. Parses their frontmatter and body
3. Creates Lesson entries in the brain's lessons.md
4. Sets confidence based on correction evidence in the text
5. Deduplicates against existing lessons

Usage:
    from gradata.enhancements.memory_bridge import bridge_memories_to_lessons
    result = bridge_memories_to_lessons(
        memory_dir=Path("path/to/memory"),
        lessons_path=Path("path/to/brain/lessons.md"),
    )
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

from gradata._types import Lesson, LessonState

logger = logging.getLogger("gradata")

# Category keywords → lesson category mapping
CATEGORY_MAP: dict[str, str] = {
    "plan": "PROCESS",
    "adversary": "PROCESS",
    "implement": "PROCESS",
    "workflow": "PROCESS",
    "audit": "PROCESS",
    "email": "DRAFTING",
    "draft": "DRAFTING",
    "prose": "DRAFTING",
    "em dash": "DRAFTING",
    "tone": "TONE",
    "style": "TONE",
    "voice": "TONE",
    "pricing": "PRICING",
    "price": "PRICING",
    "tier": "PRICING",
    "accuracy": "ACCURACY",
    "verify": "ACCURACY",
    "check": "ACCURACY",
    "data": "DATA_INTEGRITY",
    "enrich": "DATA_INTEGRITY",
    "lead": "LEADS",
    "prospect": "LEADS",
    "campaign": "LEADS",
    "demo": "DEMO_PREP",
    "calendar": "DEMO_PREP",
    "architecture": "ARCHITECTURE",
    "sdk": "ARCHITECTURE",
    "tool": "TOOL",
    "hook": "TOOL",
    "agent": "TOOL",
}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML-ish frontmatter from a memory file.

    Returns (metadata_dict, body_text).
    """
    meta: dict[str, str] = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip()
            body = parts[2].strip()

    return meta, body


def _extract_correction_count(body: str) -> int:
    """Estimate how many times this correction was made from text evidence."""
    count = 1

    # Look for explicit counts: "corrected 3x", "corrected 4+ times"
    patterns = [
        r"corrected?\s+(\d+)\s*[x×]",
        r"corrected?\s+(\d+)\+?\s*times?",
        r"(\d+)\s*times?\s+in\s+(?:one\s+)?session",
        r"corrected?\s+(?:this\s+)?(\d+)\+?\s*times?",
    ]
    for pat in patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            count = max(count, int(m.group(1)))

    # Look for session references: "S74, S75" = 2 sessions
    session_refs = re.findall(r"S\d+", body)
    if len(session_refs) > 1:
        count = max(count, len(set(session_refs)))

    return count


def _estimate_confidence(correction_count: int) -> float:
    """Map correction count to initial confidence.

    More corrections = higher initial confidence because the user has
    reinforced this correction multiple times. This skips the slow
    INSTINCT → PATTERN → RULE climb for well-established feedback.

    1 correction  → 0.40 (INSTINCT)
    2 corrections → 0.55 (INSTINCT, close to PATTERN)
    3 corrections → 0.65 (PATTERN)
    4 corrections → 0.80 (PATTERN, close to RULE)
    5+ corrections → 0.92 (RULE)
    """
    if correction_count >= 5:
        return 0.92
    if correction_count >= 4:
        return 0.80
    if correction_count >= 3:
        return 0.65
    if correction_count >= 2:
        return 0.55
    return 0.40


def _classify_category(name: str, body: str) -> str:
    """Infer lesson category from feedback file name and body text."""
    combined = (name + " " + body).lower()
    for keyword, category in CATEGORY_MAP.items():
        if keyword in combined:
            return category
    return "GENERAL"


def _state_for_confidence(confidence: float) -> LessonState:
    """Return the correct LessonState for a confidence value."""
    if confidence >= 0.90:
        return LessonState.RULE
    if confidence >= 0.60:
        return LessonState.PATTERN
    return LessonState.INSTINCT


def parse_feedback_file(path: Path) -> dict | None:
    """Parse a single memory feedback file into bridge-ready data.

    Returns None if the file is not a feedback type or can't be parsed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    meta, body = _parse_frontmatter(text)

    if meta.get("type") != "feedback":
        return None

    name = meta.get("name", path.stem)
    description = meta.get("description", "")

    # Extract the rule itself (first non-empty line of body, or description)
    rule_text = ""
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("**"):
            rule_text = line
            break
    if not rule_text:
        rule_text = description

    correction_count = _extract_correction_count(body)
    confidence = _estimate_confidence(correction_count)
    category = _classify_category(name, body)
    state = _state_for_confidence(confidence)

    return {
        "name": name,
        "description": rule_text,
        "category": category,
        "confidence": confidence,
        "state": state,
        "correction_count": correction_count,
        "source_file": path.name,
    }


def _merge_related_feedback(
    parsed_items: list[dict],
) -> list[dict]:
    """Merge feedback files that describe the same correction.

    Two files are "related" if they share the same category AND their
    file names share a common stem (e.g., feedback_always_plan_first.md
    and feedback_plan_adversary_mandatory.md both contain "plan").

    When merged, correction counts are summed and confidence recalculated.
    The first file's description is kept as the canonical rule text.
    """
    # Group by category
    by_category: dict[str, list[dict]] = {}
    for item in parsed_items:
        by_category.setdefault(item["category"], []).append(item)

    merged: list[dict] = []

    for _cat, items in by_category.items():
        if len(items) <= 1:
            merged.extend(items)
            continue

        # Within a category, find clusters by shared keywords in file names
        used = set()
        for i, a in enumerate(items):
            if i in used:
                continue

            cluster = [a]
            a_words = set(a["source_file"].replace("feedback_", "").replace(".md", "").split("_"))

            for j, b in enumerate(items):
                if j <= i or j in used:
                    continue
                b_words = set(b["source_file"].replace("feedback_", "").replace(".md", "").split("_"))
                # If they share meaningful words, they're likely about the same thing
                stop_words = {"the", "a", "an", "and", "or", "no", "not", "is", "use", "only", "before", "after", "first", "always", "never", "all", "new", "from", "into", "full"}
                overlap = (a_words & b_words) - stop_words
                if len(overlap) >= 1:
                    cluster.append(b)
                    used.add(j)

            used.add(i)

            if len(cluster) == 1:
                merged.append(cluster[0])
            else:
                # Merge: sum corrections, recalculate confidence, keep first description
                total_corrections = sum(c["correction_count"] for c in cluster)
                confidence = _estimate_confidence(total_corrections)
                state = _state_for_confidence(confidence)
                sources = " + ".join(c["source_file"] for c in cluster)

                winner = dict(cluster[0])
                winner["correction_count"] = total_corrections
                winner["confidence"] = confidence
                winner["state"] = state
                winner["source_file"] = sources
                merged.append(winner)

                logger.info(
                    "Merged %d feedback files: %s (total %d corrections -> %.2f confidence)",
                    len(cluster),
                    sources,
                    total_corrections,
                    confidence,
                )

    return merged


def bridge_memories_to_lessons(
    memory_dir: Path,
    lessons_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    """Scan feedback memory files and merge into lessons.md.

    Args:
        memory_dir: Directory containing feedback_*.md files.
        lessons_path: Path to the brain's lessons.md file.
        dry_run: If True, don't write -- just return what would change.

    Returns:
        Dict with counts: scanned, skipped, created, updated, already_exists.
    """
    from gradata.enhancements.self_improvement import (
        format_lessons,
        parse_lessons,
    )

    result = {
        "scanned": 0,
        "skipped": 0,
        "created": 0,
        "updated": 0,
        "already_exists": 0,
        "merged": 0,
        "lessons": [],
    }

    # Load existing lessons
    existing_text = ""
    if lessons_path.is_file():
        existing_text = lessons_path.read_text(encoding="utf-8")
    existing_lessons = parse_lessons(existing_text) if existing_text else []

    # Build dedup index: (category, first 40 chars of description)
    existing_keys: set[tuple[str, str]] = set()
    for lesson in existing_lessons:
        existing_keys.add((lesson.category, lesson.description[:40]))

    # Phase 1: Parse all feedback files
    parsed_items: list[dict] = []
    feedback_files = sorted(memory_dir.glob("feedback_*.md"))

    for fpath in feedback_files:
        result["scanned"] += 1
        parsed = parse_feedback_file(fpath)
        if parsed is None:
            result["skipped"] += 1
            continue
        parsed_items.append(parsed)

    # Phase 2: Merge related feedback files (same correction, multiple files)
    before_merge = len(parsed_items)
    parsed_items = _merge_related_feedback(parsed_items)
    result["merged"] = before_merge - len(parsed_items)

    # Phase 3: Create lessons, deduplicating against existing
    for parsed in parsed_items:
        key = (parsed["category"], parsed["description"][:40])

        if key in existing_keys:
            result["already_exists"] += 1
            continue

        new_lesson = Lesson(
            date=date.today().isoformat(),
            state=parsed["state"],
            confidence=parsed["confidence"],
            category=parsed["category"],
            description=parsed["description"],
            fire_count=parsed["correction_count"],
            scope_json="",  # universal scope
        )

        existing_lessons.append(new_lesson)
        existing_keys.add(key)
        result["created"] += 1
        result["lessons"].append({
            "category": parsed["category"],
            "state": parsed["state"].value,
            "confidence": parsed["confidence"],
            "description": parsed["description"][:80],
            "source": parsed["source_file"],
        })

        logger.info(
            "Bridged: [%s:%.2f] %s: %s (from %s)",
            parsed["state"].value,
            parsed["confidence"],
            parsed["category"],
            parsed["description"][:60],
            parsed["source_file"],
        )

    # Write back (with file lock for concurrency)
    if not dry_run and result["created"] > 0:
        lessons_path.parent.mkdir(parents=True, exist_ok=True)
        from gradata._db import write_lessons_safe
        write_lessons_safe(lessons_path, format_lessons(existing_lessons))
        logger.info(
            "Memory bridge: %d feedback files -> %d new lessons in %s",
            result["scanned"],
            result["created"],
            lessons_path,
        )

    return result
