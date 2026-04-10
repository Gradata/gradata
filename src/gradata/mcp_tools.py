"""
Three-Tool MCP Surface for Gradata.
====================================
SDK LAYER: Layer 0 (patterns-safe). Pure functions, no file I/O at module load.

Inspired by SuperMemory's 3-tool MCP pattern (memory, recall, whoAmI).
Gradata equivalent: correct, recall, manifest.

These functions are the logical core behind the MCP server tools.
They can be called directly from Python or wired into any MCP transport.

Usage::

    from gradata.mcp_tools import correct, recall, manifest

    # Log a correction
    result = correct("AI draft text", "User-edited final", category="DRAFTING")

    # Get relevant rules for a task
    rules_xml = recall("write cold email to CTO", max_rules=5)

    # Get improvement proof
    proof = manifest()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gradata._types import ELIGIBLE_STATES, Lesson, LessonState
from gradata.enhancements.diff_engine import compute_diff

# ---------------------------------------------------------------------------
# Tool 1: correct -- Log a correction
# ---------------------------------------------------------------------------


def correct(
    draft: str,
    final: str,
    *,
    category: str | None = None,
    brain_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Log a correction: compute diff between draft and final, classify, store.

    This is the core procedural memory primitive. Every time a user edits an AI output,
    this function captures the delta and stores it as a lesson candidate.

    Args:
        draft: The original AI-generated text.
        final: The user-edited final version.
        category: Optional category override (e.g. "DRAFTING", "ACCURACY").
            If not provided, auto-detected from the diff content.
        brain_dir: Optional brain directory path. If not provided, uses
            the default from _paths.

    Returns:
        Dict with keys:
        - severity: str ("as-is", "minor", "moderate", "major", "discarded")
        - edit_distance: float (0.0 = identical, 1.0 = completely different)
        - compression_distance: float (NCD-based distance)
        - category: str (detected or provided category)
        - summary_stats: dict with lines_added, lines_removed, lines_changed
        - lesson_created: bool (True if stored as a new lesson)
    """
    if not draft and not final:
        return {
            "severity": "as-is",
            "edit_distance": 0.0,
            "compression_distance": 0.0,
            "category": category or "UNKNOWN",
            "summary_stats": {"lines_added": 0, "lines_removed": 0, "lines_changed": 0},
            "lesson_created": False,
        }

    diff = compute_diff(draft, final)

    # Auto-detect category from content if not provided
    if category is None:
        category = _auto_detect_category(draft, final, diff.severity)

    # Store as event if brain is available
    lesson_created = False
    try:
        if brain_dir is not None:
            from gradata.brain import Brain

            brain = Brain(brain_dir)
            brain.correct(draft, final)
            lesson_created = True
    except Exception:
        # Brain not available or not initialized -- still return diff results
        pass

    return {
        "severity": diff.severity,
        "edit_distance": diff.edit_distance,
        "compression_distance": diff.compression_distance,
        "category": category,
        "summary_stats": diff.summary_stats,
        "lesson_created": lesson_created,
    }


def _auto_detect_category(draft: str, final: str, severity: str) -> str:
    """Heuristic category detection from diff content.

    Categories match the Gradata lesson taxonomy:
    DRAFTING, ACCURACY, FORMATTING, PROCESS, TONE, COMPLIANCE, UNKNOWN.
    """
    combined = (draft + " " + final).lower()

    # Check for formatting signals
    format_signals = ["bold", "italic", "heading", "bullet", "indent",
                      "em dash", "colon", "comma", "spacing", "markdown"]
    if any(s in combined for s in format_signals):
        return "FORMATTING"

    # Check for accuracy signals
    accuracy_signals = ["wrong", "incorrect", "inaccurate", "outdated",
                        "error", "mistake", "not true", "false"]
    if any(s in combined for s in accuracy_signals):
        return "ACCURACY"

    # Check for tone signals
    tone_signals = ["tone", "formal", "casual", "aggressive", "softer",
                    "professional", "friendly", "polite"]
    if any(s in combined for s in tone_signals):
        return "TONE"

    # Check for process signals
    process_signals = ["step", "order", "first", "before", "after",
                       "verify", "check", "validate", "workflow"]
    if any(s in combined for s in process_signals):
        return "PROCESS"

    # Default based on severity
    if severity in ("major", "discarded"):
        return "DRAFTING"

    return "DRAFTING"


# ---------------------------------------------------------------------------
# Tool 2: recall -- Get relevant rules for current task
# ---------------------------------------------------------------------------


def recall(
    query: str,
    *,
    max_rules: int = 5,
    lessons_path: str | Path | None = None,
    meta_rules_path: str | Path | None = None,
) -> str:
    """Retrieve graduated rules relevant to the current task, formatted as XML.

    Searches both individual lessons (PATTERN/RULE state) and meta-rules
    for relevance to the query. Returns ranked results as XML suitable
    for system prompt injection.

    Args:
        query: Description of the current task or context.
        max_rules: Maximum number of rules to return (default 5).
        lessons_path: Path to lessons.md file. If None, tries default paths.
        meta_rules_path: Path to meta-rules.json. If None, tries default paths.

    Returns:
        XML string of ranked rules, e.g.:
        <brain-rules>
        [RULE:0.95] DRAFTING: Never use 'revolutionize' in cold emails
        [PATTERN:0.72] PROCESS: Verify prospect identity before drafting
        </brain-rules>

        Returns empty <brain-rules/> if no relevant rules found.
    """
    lessons = _load_lessons(lessons_path)
    meta_rules = _load_meta_rules(meta_rules_path)

    # Filter to eligible states only
    eligible = [
        lesson for lesson in lessons
        if lesson.state in ELIGIBLE_STATES
    ]

    # Score each lesson by relevance to query
    scored: list[tuple[float, str]] = []

    query_words = set(query.lower().split())

    for lesson in eligible:
        relevance = _relevance_score(query_words, lesson.description, lesson.category)
        if relevance > 0.0:
            line = f"[{lesson.state.value}:{lesson.confidence:.2f}] {lesson.category}: {lesson.description}"
            # Combine relevance with confidence for final ranking
            score = relevance * 0.6 + lesson.confidence * 0.4
            scored.append((score, line))

    # Add meta-rules (they count as 1 each but represent multiple lessons)
    for mr in meta_rules:
        relevance = _relevance_score(query_words, mr.get("principle", ""), "")
        if relevance > 0.0:
            conf = mr.get("confidence", 0.8)
            line = f"[META:{conf:.2f}] {mr.get('principle', '')}"
            score = relevance * 0.6 + conf * 0.4
            scored.append((score, line))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_rules]

    if not top:
        return "<brain-rules/>"

    rules_text = "\n".join(line for _, line in top)
    return f"<brain-rules>\n{rules_text}\n</brain-rules>"


def _relevance_score(query_words: set[str], description: str, category: str) -> float:
    """Compute keyword-based relevance between query and a rule description.

    Returns a float in [0.0, 1.0]. Higher = more relevant.
    """
    desc_words = set(description.lower().split())
    cat_words = set(category.lower().split()) if category else set()
    all_rule_words = desc_words | cat_words

    if not query_words or not all_rule_words:
        return 0.0

    overlap = query_words & all_rule_words
    if not overlap:
        return 0.0

    # Jaccard-like score weighted toward query coverage
    query_coverage = len(overlap) / len(query_words)
    rule_coverage = len(overlap) / len(all_rule_words)

    return query_coverage * 0.7 + rule_coverage * 0.3


def _load_lessons(lessons_path: str | Path | None = None) -> list[Lesson]:
    """Load lessons from a lessons.md file.

    Parses the standard Gradata lessons format:
    [YYYY-MM-DD] [STATE:confidence] CATEGORY: description
    """
    if lessons_path is not None:
        path = Path(lessons_path)
    else:
        # Try default paths
        try:
            import gradata._paths as _p
            path = _p.LESSONS_FILE
        except Exception:
            return []

    if not path.exists():
        return []

    try:
        from gradata.enhancements.self_improvement import parse_lessons
        return parse_lessons(path.read_text(encoding="utf-8"))
    except (ImportError, Exception):
        return []


def _load_meta_rules(meta_rules_path: str | Path | None = None) -> list[dict]:
    """Load meta-rules from JSON file."""
    if meta_rules_path is not None:
        path = Path(meta_rules_path)
    else:
        try:
            import gradata._paths as _p
            path = _p.BRAIN_DIR / "meta-rules.json"
        except Exception:
            return []

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "meta_rules" in data:
            return data["meta_rules"]
        return []
    except (json.JSONDecodeError, Exception):
        return []


# ---------------------------------------------------------------------------
# Tool 3: manifest -- Show improvement proof
# ---------------------------------------------------------------------------


def manifest(
    *,
    brain_dir: str | Path | None = None,
    lessons_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return improvement proof: correction rate, extinct categories, compound score.

    This is the "fitness tracker" for the AI brain. It shows measurable
    improvement over time.

    Args:
        brain_dir: Optional brain directory. If None, uses default.
        lessons_path: Optional lessons.md path. If None, uses default.

    Returns:
        Dict with keys:
        - correction_rate: float | None (corrections per output, last 10 sessions)
        - categories_extinct: list[str] (categories with 0 corrections recently)
        - compound_score: float (0-10 overall brain health)
        - rules_count: int (total graduated rules)
        - meta_rules_count: int (emerged meta-rules)
        - sessions_trained: int (total training sessions)
        - maturity_phase: str (INFANT/ADOLESCENT/MATURE/STABLE)
        - lessons_active: int (non-graduated lessons)
        - lessons_graduated: int (archived lessons)
    """
    result: dict[str, Any] = {
        "correction_rate": None,
        "categories_extinct": [],
        "compound_score": 0.0,
        "rules_count": 0,
        "meta_rules_count": 0,
        "sessions_trained": 0,
        "maturity_phase": "INFANT",
        "lessons_active": 0,
        "lessons_graduated": 0,
    }

    # Load lessons for rule counting
    lessons = _load_lessons(lessons_path)
    meta_rules = _load_meta_rules()

    rules = [lesson for lesson in lessons if lesson.state == LessonState.RULE]
    patterns = [lesson for lesson in lessons if lesson.state == LessonState.PATTERN]
    result["rules_count"] = len(rules) + len(patterns)
    result["meta_rules_count"] = len(meta_rules)
    result["lessons_active"] = len([lesson for lesson in lessons if lesson.state in (LessonState.INSTINCT, LessonState.PATTERN)])
    result["lessons_graduated"] = len(rules)

    # Try to get full manifest from brain (supplement, don't override file-based counts)
    try:
        from gradata._brain_manifest import generate_manifest
        full_manifest = generate_manifest()
        quality = full_manifest.get("quality", {})
        metadata = full_manifest.get("metadata", {})

        result["correction_rate"] = quality.get("correction_rate")
        result["sessions_trained"] = metadata.get("sessions_trained", 0)
        result["maturity_phase"] = metadata.get("maturity_phase", "INFANT")
        # Only use brain-derived counts if no explicit lessons_path was provided
        if not lessons_path:
            result["lessons_active"] = quality.get("lessons_active", result["lessons_active"])
            result["lessons_graduated"] = quality.get("lessons_graduated", result["lessons_graduated"])
    except Exception:
        pass

    # Detect extinct categories (categories with RULE state but no recent corrections)
    category_states: dict[str, list[str]] = {}
    for lesson in lessons:
        cat = lesson.category
        if cat not in category_states:
            category_states[cat] = []
        category_states[cat].append(lesson.state.value)

    for cat, states in category_states.items():
        # A category is "extinct" if all its lessons are RULE or ARCHIVED
        # (no more corrections needed in this area)
        if all(s in ("RULE", "ARCHIVED") for s in states) and len(states) >= 2:
            result["categories_extinct"].append(cat)

    # Compound score: weighted combination of improvement signals
    score = 0.0
    if result["rules_count"] > 0:
        score += min(3.0, result["rules_count"] * 0.3)  # Up to 3 points for rules
    if result["meta_rules_count"] > 0:
        score += min(2.0, result["meta_rules_count"] * 0.5)  # Up to 2 for meta-rules
    if result["categories_extinct"]:
        score += min(2.0, len(result["categories_extinct"]) * 0.5)  # Up to 2 for extinct
    cr = result["correction_rate"]
    if cr is not None and cr < 0.2:
        score += 2.0  # 2 points for low correction rate
    elif cr is not None and cr < 0.4:
        score += 1.0
    if result["sessions_trained"] >= 20:
        score += 1.0  # 1 point for training maturity
    result["compound_score"] = round(min(10.0, score), 1)

    return result


def export_skill(
    *,
    output_dir: str | Path | None = None,
    min_state: str = "PATTERN",
    skill_name: str = "",
    brain_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Export graduated rules as an OpenSpace-compatible skill directory.

    Creates a full skill directory with SKILL.md, .skill_id, and
    provenance.json that can be uploaded to OpenSpace's skill cloud
    or consumed by any OpenSpace-compatible agent.

    Args:
        output_dir: Where to create the skill directory. Defaults to
            brain_dir/skills/.
        min_state: Minimum lesson tier ("PATTERN" or "RULE").
        skill_name: Skill name. Auto-generated from domain if empty.
        brain_dir: Optional brain directory. If None, uses default.

    Returns:
        Dict with skill_dir, skill_id, rules_count, and SKILL.md preview.
    """
    from gradata._paths import BRAIN_DIR
    from gradata.brain import Brain

    bd = Path(brain_dir) if brain_dir else BRAIN_DIR
    if not bd or not bd.exists():
        return {"error": "No brain directory found. Run Brain.init() first."}

    brain = Brain(bd)
    try:
        skill_dir = brain.export_skill(
            output_dir=str(output_dir) if output_dir else None,
            min_state=min_state,
            skill_name=skill_name,
        )
    except ValueError as e:
        return {"error": str(e)}

    skill_id = (skill_dir / ".skill_id").read_text(encoding="utf-8")
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    return {
        "skill_dir": str(skill_dir),
        "skill_id": skill_id,
        "skill_md_preview": skill_md[:500],
        "files": [f.name for f in skill_dir.iterdir()],
    }
