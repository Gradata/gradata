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
import logging
from pathlib import Path
from typing import Any

from gradata._config import current_brain_config
from gradata._scope import build_scope
from gradata._types import ELIGIBLE_STATES, Lesson, LessonState
from gradata.enhancements.diff_engine import compute_diff
from gradata.rules.rule_engine import AppliedRule, apply_rules, apply_rules_with_tree

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool 1: correct -- Log a correction
# ---------------------------------------------------------------------------


def correct(
    draft: str,
    final: str,
    *,
    category: str | None = None,
    brain_dir: str | Path | None = None,
    applies_to: str | None = None,
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
        applies_to: Optional free-form scope token (e.g. ``"client:acme"``,
            ``"task:emails"``) passed through to ``Brain.correct``. Persisted
            on the correction event and any lesson created from it. See
            ``Brain.correct`` for details.

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
            brain.correct(draft, final, applies_to=applies_to)
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


# Category signal words. Order matters — first match wins.
_CATEGORY_SIGNALS: list[tuple[str, tuple[str, ...]]] = [
    (
        "FORMATTING",
        (
            "bold",
            "italic",
            "heading",
            "bullet",
            "indent",
            "em dash",
            "colon",
            "comma",
            "spacing",
            "markdown",
        ),
    ),
    (
        "ACCURACY",
        ("wrong", "incorrect", "inaccurate", "outdated", "error", "mistake", "not true", "false"),
    ),
    (
        "TONE",
        ("tone", "formal", "casual", "aggressive", "softer", "professional", "friendly", "polite"),
    ),
    (
        "PROCESS",
        ("step", "order", "first", "before", "after", "verify", "check", "validate", "workflow"),
    ),
]


def _auto_detect_category(draft: str, final: str, severity: str) -> str:
    """Heuristic category detection from diff content.

    Categories match the Gradata lesson taxonomy:
    DRAFTING, ACCURACY, FORMATTING, PROCESS, TONE, COMPLIANCE, UNKNOWN.
    """
    del severity  # reserved for future heuristics
    combined = (draft + " " + final).lower()
    for category, signals in _CATEGORY_SIGNALS:
        if any(s in combined for s in signals):
            return category
    return "DRAFTING"


# ---------------------------------------------------------------------------
# Tool 2: recall -- Get relevant rules for current task
# ---------------------------------------------------------------------------


def recall(
    query: str,
    *,
    max_rules: int | None = None,
    ranker: str | None = None,
    include_all_sources: bool = False,
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
    cfg = current_brain_config()
    if max_rules is None:
        max_rules = 5
    if ranker is None:
        ranker = cfg.ranker
    return _recall_by_count(
        query,
        max_rules=max_rules,
        ranker=ranker,
        include_all_sources=include_all_sources,
        lessons_path=lessons_path,
        meta_rules_path=meta_rules_path,
    )


def _recall_by_count(
    query: str,
    *,
    max_rules: int,
    ranker: str,
    include_all_sources: bool,
    lessons_path: str | Path | None,
    meta_rules_path: str | Path | None,
) -> str:
    lessons = _load_lessons(lessons_path)
    meta_rules = _load_meta_rules(meta_rules_path, include_all_sources=include_all_sources)

    # Filter to eligible states only
    eligible = [lesson for lesson in lessons if lesson.state in ELIGIBLE_STATES]

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
    if ranker == "tree_only":
        scored = list(reversed(scored))
    elif ranker == "flat":
        scored.sort(key=lambda x: x[1])
    top = scored[:max_rules]

    if not top:
        return "<brain-rules/>"

    rules_text = "\n".join(line for _, line in top)
    return f"<brain-rules>\n{rules_text}\n</brain-rules>"


def gradata_recall(
    situation: str,
    *,
    max_tokens: int | None = None,
    ranker: str | None = None,
    include_all_sources: bool = False,
    lessons_path: str | Path | None = None,
    meta_rules_path: str | Path | None = None,
) -> str:
    """Retrieve ranked rules under a rough token budget.

    Token accounting intentionally uses the project-wide cheap estimate
    ``len(text) // 4``. The envelope is included in the budget so callers can
    pass the result directly into a prompt.
    """
    cfg = current_brain_config()
    if max_tokens is None:
        max_tokens = cfg.max_recall_tokens
    if ranker is None:
        ranker = cfg.ranker
    if max_tokens <= 0:
        return "<brain-rules/>"
    if ranker not in {"hybrid", "flat", "tree_only"}:
        ranker = "hybrid"

    lessons = _load_lessons(lessons_path)
    metas = _load_meta_rules(meta_rules_path, include_all_sources=include_all_sources)
    query_words = set(situation.lower().split())
    scope = build_scope({"task": situation, "task_type": situation})

    max_candidates = max(100, len(lessons) + len(metas))
    if ranker == "flat":
        applied = apply_rules(lessons, scope, max_rules=max_candidates, user_message=situation)
    else:
        applied = apply_rules_with_tree(
            lessons,
            scope,
            max_rules=max_candidates,
            ranker=ranker,
        )
    if ranker == "tree_only":
        applied = list(reversed(applied))
    lesson_lines = [_line_from_applied(rule) for rule in applied]

    meta_scored: list[tuple[float, str]] = []
    for mr in metas:
        principle = str(mr.get("principle", "")).strip()
        relevance = _relevance_score(query_words, principle, "")
        if relevance <= 0.0 and ranker != "tree_only":
            continue
        conf = float(mr.get("confidence", 0.8) or 0.8)
        line = f"[META:{conf:.2f}] {principle}"
        score = relevance * 0.6 + conf * 0.4
        meta_scored.append((score, line))
    meta_scored.sort(key=lambda x: x[0], reverse=True)
    if ranker == "tree_only":
        meta_scored = list(reversed(meta_scored))
    elif ranker == "flat":
        meta_scored.sort(key=lambda x: x[1])
    meta_lines = [line for _, line in meta_scored]

    return _format_budgeted_rules(lesson_lines, meta_lines, max_tokens)


def _line_from_applied(rule: AppliedRule) -> str:
    lesson = rule.lesson
    return f"[{lesson.state.value}:{lesson.confidence:.2f}] {lesson.category}: {lesson.description}"


def _rough_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _format_budgeted_rules(lesson_lines: list[str], meta_lines: list[str], max_tokens: int) -> str:
    if not lesson_lines and not meta_lines:
        return "<brain-rules/>"

    selected: list[str] = []
    envelope_tokens = _rough_tokens("<brain-rules>\n\n</brain-rules>")
    used = envelope_tokens

    reserved_meta = meta_lines[0] if meta_lines else None
    if reserved_meta is not None:
        cost = _rough_tokens(reserved_meta)
        if used + cost <= max_tokens:
            selected.append(reserved_meta)
            used += cost

    remaining_meta = meta_lines[1:] if reserved_meta is not None else meta_lines
    combined = lesson_lines + remaining_meta
    for line in combined:
        if line in selected:
            continue
        cost = _rough_tokens(line)
        if used + cost > max_tokens:
            continue
        selected.append(line)
        used += cost

    if not selected:
        return "<brain-rules/>"

    return "<brain-rules>\n" + "\n".join(selected) + "\n</brain-rules>"


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
        except (ImportError, AttributeError):
            return []

    if not path.exists():
        return []

    try:
        from gradata.enhancements.self_improvement import parse_lessons

        return parse_lessons(path.read_text(encoding="utf-8"))
    except (ImportError, OSError, ValueError):
        _log.warning("failed to load lessons from %s", path, exc_info=True)
        return []


def _load_meta_rules(
    meta_rules_path: str | Path | None = None,
    *,
    include_all_sources: bool = False,
) -> list[dict]:
    """Load meta-rules from JSON file."""
    if meta_rules_path is not None:
        path = Path(meta_rules_path)
    else:
        try:
            import gradata._paths as _p

            path = _p.BRAIN_DIR / "meta-rules.json"
        except (ImportError, AttributeError):
            return []

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _log.warning("failed to load meta-rules from %s", path, exc_info=True)
        return []
    if isinstance(data, list):
        return _filter_meta_dicts([m for m in data if isinstance(m, dict)], include_all_sources)
    if isinstance(data, dict):
        rules = data.get("meta_rules", [])
        if isinstance(rules, list):
            return _filter_meta_dicts(
                [m for m in rules if isinstance(m, dict)],
                include_all_sources,
            )
    return []


def _filter_meta_dicts(rules: list[dict], include_all_sources: bool) -> list[dict]:
    if include_all_sources:
        return rules
    try:
        from gradata.enhancements.meta_rules import INJECTABLE_META_SOURCES
    except ImportError:
        return rules
    filtered = []
    for rule in rules:
        source = str(rule.get("source", "deterministic"))
        if source in INJECTABLE_META_SOURCES:
            filtered.append(rule)
        else:
            _log.warning(
                "dropping meta-rule %s (source=%s) from injection",
                rule.get("id", "<unknown>"),
                source,
            )
    return filtered


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
    result["lessons_active"] = len(
        [
            lesson
            for lesson in lessons
            if lesson.state in (LessonState.INSTINCT, LessonState.PATTERN)
        ]
    )
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
            result["lessons_graduated"] = quality.get(
                "lessons_graduated", result["lessons_graduated"]
            )
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
