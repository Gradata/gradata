"""
Meta-Rule Emergence — compound learning through principle discovery.
====================================================================
SDK LAYER: Layer 1 (enhancements). Imports from patterns/ and _types.

When multiple individual corrections share an underlying pattern, a
meta-rule automatically emerges.  Meta-rules capture the PRINCIPLE
behind corrections, enabling the AI to generalise to new situations
it hasn't been corrected on yet.

Example:
    "Use colons not dashes" + "No em dashes in emails" + "No bold
    mid-paragraph" + "Tight prose"
    ->  META-RULE: "Oliver values minimal, clean formatting: no
        decorative punctuation, no inline emphasis, direct sentences"

Integration points:
    - ``discover_meta_rules()`` runs at session close (wrap-up)
    - ``refresh_meta_rules()`` runs at session start
    - The rule engine prefers meta-rules over individual rules
    - Each meta-rule counts as 1 toward the 10-rule cap but
      represents 3-5 underlying corrections

OPEN SOURCE: The discovery algorithm is open.  Meta-rule optimisation
(injection weighting, audience-aware selection) is proprietary cloud-side.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from gradata._types import Lesson, LessonState

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

_ELIGIBLE_STATES: frozenset[LessonState] = frozenset(
    {LessonState.RULE, LessonState.PATTERN}
)


@dataclass
class MetaRule:
    """An emergent principle synthesised from 3+ related corrections.

    Attributes:
        id: Deterministic hash of source lesson IDs (stable across runs).
        principle: The emergent principle in 1-2 sentences.
        source_categories: Which lesson categories contributed.
        source_lesson_ids: Opaque IDs of the contributing lessons.
        confidence: Average confidence of source rules.
        created_session: Session number when first discovered.
        last_validated_session: Last session where the meta-rule was
            confirmed still valid (no contradicting corrections).
        scope: Task/domain/audience constraints (JSON-serialisable).
        examples: 1-2 concrete examples illustrating the principle.
    """

    id: str
    principle: str
    source_categories: list[str]
    source_lesson_ids: list[str]
    confidence: float
    created_session: int
    last_validated_session: int
    scope: dict = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lesson_id(lesson: Lesson) -> str:
    """Derive a stable ID from a lesson's category + description."""
    raw = f"{lesson.category}:{lesson.description}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _meta_id(lesson_ids: list[str]) -> str:
    """Deterministic meta-rule ID from sorted source lesson IDs."""
    canonical = "|".join(sorted(lesson_ids))
    return "META-" + hashlib.sha256(canonical.encode()).hexdigest()[:10]


def _tokenise(text: str) -> set[str]:
    """Split text into lowercase word tokens, stripping punctuation."""
    return set(re.findall(r"[a-z]{3,}", text.lower()))


# Semantic theme clusters: words that indicate the same underlying theme.
# Each key is a theme label; values are words that signal that theme.
_THEME_CLUSTERS: dict[str, set[str]] = {
    "formatting": {
        "format", "formatting", "bold", "dash", "dashes", "colon",
        "colons", "emphasis", "punctuation", "bullet", "bullets",
        "paragraph", "prose", "style", "numbered", "list", "lists",
        "subject", "lines", "decorative", "inline",
    },
    "pricing": {
        "pricing", "price", "cost", "costs", "subscription", "monthly",
        "annual", "tier", "tiers", "starter", "standard", "budget",
        "value", "deal", "revenue", "paid", "free",
    },
    "accuracy": {
        "verify", "verified", "check", "confirm", "accurate", "accuracy",
        "never", "guess", "assume", "assumption", "verify", "validate",
        "validated", "source", "evidence", "facts", "factual",
    },
    "research_first": {
        "research", "linkedin", "apollo", "investigate", "before",
        "prior", "lookup", "enrich", "enrichment", "profile", "scrape",
    },
    "prospect_handling": {
        "prospect", "lead", "leads", "campaign", "demo", "followup",
        "follow", "outreach", "email", "emails", "draft", "drafting",
        "subject", "thread", "reply", "calendly",
    },
    "process_discipline": {
        "skip", "skipping", "never", "always", "mandatory", "gate",
        "gates", "checklist", "step", "steps", "wrap", "startup",
        "audit", "verify", "verification", "done", "ready", "complete",
    },
    "tool_usage": {
        "tool", "tools", "api", "apify", "scraper", "notebooklm",
        "pipedrive", "apollo", "gmail", "instantly", "opencli",
        "fireflies", "playwright",
    },
    "communication_tone": {
        "tone", "empathy", "condescending", "casual", "direct",
        "agency", "positioning", "framing", "pitch", "sell",
        "feature", "outcome", "pain", "acknowledge",
    },
    "data_integrity": {
        "filter", "owner", "oliver", "anna", "shared", "blended",
        "metrics", "measurement", "dedup", "duplicate", "integrity",
    },
    "ip_protection": {
        "public", "docs", "documentation", "expose", "mechanism",
        "competitor", "architecture", "internal", "proprietary",
        "open", "source",
    },
}


def _detect_themes(text: str) -> dict[str, int]:
    """Return {theme: overlap_count} for a piece of text."""
    tokens = _tokenise(text)
    hits: dict[str, int] = {}
    for theme, keywords in _THEME_CLUSTERS.items():
        overlap = len(tokens & keywords)
        if overlap >= 2:
            hits[theme] = overlap
    return hits


def _synthesise_principle(lessons: list[Lesson], theme: str) -> str:
    """Generate a principle statement from a group of related lessons.

    Uses template-based synthesis: extract the common theme, summarise
    the specific behaviours, and frame as a user preference.
    """
    # Collect the action verbs and key constraints from descriptions
    behaviours: list[str] = []
    for lesson in lessons:
        desc = lesson.description
        # Grab the actionable part (after the arrow if present)
        if "→" in desc:
            desc = desc.split("→", 1)[1].strip()
        # Truncate long descriptions to the first sentence
        first_sentence = re.split(r"[.!]", desc)[0].strip()
        if first_sentence and len(first_sentence) < 120:
            behaviours.append(first_sentence)

    # If we got no behaviours from the arrow split, use raw descriptions
    if not behaviours:
        for lesson in lessons:
            first_sentence = re.split(r"[.!]", lesson.description)[0].strip()
            if first_sentence and len(first_sentence) < 120:
                behaviours.append(first_sentence)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for b in behaviours:
        key = b.lower()
        if key not in seen:
            seen.add(key)
            unique.append(b)

    # Theme-specific principle templates
    _TEMPLATES: dict[str, str] = {
        "formatting": "Clean, minimal formatting: {behaviours}",
        "pricing": "Pricing is verbal-only and precise: {behaviours}",
        "accuracy": "Verify before stating: {behaviours}",
        "research_first": "Research must complete before action: {behaviours}",
        "prospect_handling": "Prospect communications follow strict protocols: {behaviours}",
        "process_discipline": "Never skip process steps: {behaviours}",
        "tool_usage": "Use the right tool correctly: {behaviours}",
        "communication_tone": "Communication matches context and audience: {behaviours}",
        "data_integrity": "All data must be owner-filtered and deduplicated: {behaviours}",
        "ip_protection": "Public docs sell outcomes, never expose internals: {behaviours}",
    }

    template = _TEMPLATES.get(theme, "Learned principle: {behaviours}")

    # Join up to 4 behaviours into a semicolon-separated list
    summary = "; ".join(unique[:4])
    if len(unique) > 4:
        summary += f" (+{len(unique) - 4} more)"

    return template.format(behaviours=summary.lower() if summary else "multiple related corrections")


def _pick_examples(lessons: list[Lesson], max_examples: int = 2) -> list[str]:
    """Pick the most concrete example descriptions from a lesson group."""
    # Prefer lessons with arrows (explicit correction format)
    with_arrow = [l for l in lessons if "→" in l.description]
    source = with_arrow if with_arrow else lessons

    examples: list[str] = []
    for lesson in source[:max_examples]:
        desc = lesson.description
        if len(desc) > 150:
            desc = desc[:147] + "..."
        examples.append(f"[{lesson.category}] {desc}")
    return examples


# ---------------------------------------------------------------------------
# Core: Grouping
# ---------------------------------------------------------------------------

def _group_by_category(lessons: list[Lesson]) -> dict[str, list[Lesson]]:
    """Group graduated lessons by their category."""
    groups: dict[str, list[Lesson]] = defaultdict(list)
    for lesson in lessons:
        if lesson.state in _ELIGIBLE_STATES:
            groups[lesson.category].append(lesson)
    return dict(groups)


def _group_by_theme(lessons: list[Lesson]) -> dict[str, list[Lesson]]:
    """Group lessons across categories by semantic theme overlap."""
    eligible = [l for l in lessons if l.state in _ELIGIBLE_STATES]
    theme_groups: dict[str, list[Lesson]] = defaultdict(list)

    for lesson in eligible:
        themes = _detect_themes(lesson.description)
        if themes:
            # Assign to the strongest theme
            best_theme = max(themes, key=themes.get)  # type: ignore[arg-type]
            theme_groups[best_theme].append(lesson)

    return dict(theme_groups)


# ---------------------------------------------------------------------------
# Core: Discovery
# ---------------------------------------------------------------------------

def discover_meta_rules(
    lessons: list[Lesson],
    min_group_size: int = 3,
    current_session: int = 0,
) -> list[MetaRule]:
    """Scan graduated lessons for emergent meta-rules.

    Two grouping strategies run in parallel:
        1. Group by category (same-category clusters)
        2. Group by semantic theme (cross-category clusters)

    Any group with ``min_group_size`` or more lessons becomes a
    candidate meta-rule.  Duplicate lessons across strategies are
    deduplicated by meta-rule ID (which is derived from source
    lesson IDs).

    Args:
        lessons: All lessons (active + archived). Only PATTERN and
            RULE state lessons are considered.
        min_group_size: Minimum group size to form a meta-rule.
        current_session: Current session number for timestamping.

    Returns:
        List of discovered :class:`MetaRule` objects, sorted by
        confidence descending.
    """
    seen_ids: set[str] = set()
    metas: list[MetaRule] = []

    # Strategy 1: category-based grouping
    for category, group in _group_by_category(lessons).items():
        if len(group) >= min_group_size:
            meta = merge_into_meta(group, theme_override=category.lower(), session=current_session)
            if meta.id not in seen_ids:
                seen_ids.add(meta.id)
                metas.append(meta)

    # Strategy 2: theme-based grouping (cross-category)
    for theme, group in _group_by_theme(lessons).items():
        if len(group) >= min_group_size:
            meta = merge_into_meta(group, theme_override=theme, session=current_session)
            if meta.id not in seen_ids:
                seen_ids.add(meta.id)
                metas.append(meta)

    metas.sort(key=lambda m: m.confidence, reverse=True)
    return metas


def merge_into_meta(
    rules: list[Lesson],
    theme_override: str = "",
    session: int = 0,
) -> MetaRule:
    """Synthesise a group of related rules into one meta-rule.

    Args:
        rules: The grouped lessons (all should be PATTERN or RULE).
        theme_override: If provided, use this as the theme label
            instead of auto-detecting.
        session: Current session number.

    Returns:
        A :class:`MetaRule` instance.
    """
    lesson_ids = [_lesson_id(l) for l in rules]
    meta_id = _meta_id(lesson_ids)

    # Detect theme if not overridden
    if theme_override:
        theme = theme_override
    else:
        # Combine all descriptions and pick the dominant theme
        combined = " ".join(l.description for l in rules)
        themes = _detect_themes(combined)
        theme = max(themes, key=themes.get) if themes else "general"  # type: ignore[arg-type]

    principle = _synthesise_principle(rules, theme)
    categories = sorted(set(l.category for l in rules))
    avg_confidence = round(sum(l.confidence for l in rules) / len(rules), 2) if rules else 0.0

    # Infer scope from majority of source rules
    scope: dict = {}
    if all("email" in l.description.lower() or "draft" in l.description.lower() for l in rules):
        scope["task_type"] = "email_draft"
    if all("demo" in l.description.lower() for l in rules):
        scope["task_type"] = "demo_prep"

    examples = _pick_examples(rules)

    return MetaRule(
        id=meta_id,
        principle=principle,
        source_categories=categories,
        source_lesson_ids=lesson_ids,
        confidence=avg_confidence,
        created_session=session,
        last_validated_session=session,
        scope=scope,
        examples=examples,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_meta_rule(
    meta: MetaRule,
    recent_corrections: list[dict],
) -> bool:
    """Check if a meta-rule is still valid (no contradicting corrections).

    A meta-rule is invalidated when a recent correction directly
    contradicts its principle.  Detection uses keyword overlap between
    the correction description and the meta-rule principle.

    Args:
        meta: The meta-rule to validate.
        recent_corrections: List of dicts with at least a
            ``"description"`` key.

    Returns:
        ``True`` if the meta-rule is still valid, ``False`` if a
        contradiction was detected.
    """
    if not recent_corrections:
        return True

    principle_tokens = _tokenise(meta.principle)

    # Contradiction signals: if a correction shares significant overlap
    # with the principle AND contains negation/reversal language
    _REVERSAL_WORDS = {"actually", "instead", "wrong", "incorrect", "stop", "dont", "not"}

    for correction in recent_corrections:
        desc = correction.get("description", "")
        desc_tokens = _tokenise(desc)

        overlap = len(principle_tokens & desc_tokens)
        has_reversal = bool(desc_tokens & _REVERSAL_WORDS)

        # High overlap + reversal language = likely contradiction
        if overlap >= 4 and has_reversal:
            return False

    return True


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_meta_rules_for_prompt(metas: list[MetaRule]) -> str:
    """Format meta-rules for injection into LLM context.

    Each meta-rule is rendered as a numbered principle with its
    confidence score and source count.  This replaces the individual
    rule injection when meta-rules are available.

    Args:
        metas: Meta-rules to format, pre-sorted by priority.

    Returns:
        Formatted string block, or ``""`` if *metas* is empty.
    """
    if not metas:
        return ""

    lines = ["## Brain Meta-Rules (compound principles)"]
    for i, meta in enumerate(metas, start=1):
        cats = ", ".join(meta.source_categories)
        n = len(meta.source_lesson_ids)
        lines.append(
            f"{i}. [META:{meta.confidence:.2f}|{n} rules] "
            f"{meta.principle}"
        )
        if meta.examples:
            for ex in meta.examples:
                lines.append(f"   - {ex}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

def refresh_meta_rules(
    lessons: list[Lesson],
    existing_metas: list[MetaRule],
    recent_corrections: list[dict] | None = None,
    current_session: int = 0,
    min_group_size: int = 3,
) -> list[MetaRule]:
    """Re-discover meta-rules, keeping valid existing ones.

    Pipeline:
        1. Validate each existing meta-rule against recent corrections.
        2. Drop invalidated meta-rules.
        3. Re-run discovery on the full lesson set.
        4. Merge: keep existing valid meta-rules (preserving their
           ``created_session``), add newly discovered ones.

    Args:
        lessons: All lessons (active + archived).
        existing_metas: Previously discovered meta-rules.
        recent_corrections: Corrections from the latest session(s).
        current_session: Current session number.
        min_group_size: Minimum group size for meta-rule discovery.

    Returns:
        Updated list of :class:`MetaRule` objects.
    """
    corrections = recent_corrections or []

    # Step 1-2: validate existing
    valid_existing: dict[str, MetaRule] = {}
    for meta in existing_metas:
        if validate_meta_rule(meta, corrections):
            meta.last_validated_session = current_session
            valid_existing[meta.id] = meta

    # Step 3: re-discover
    discovered = discover_meta_rules(lessons, min_group_size, current_session)

    # Step 4: merge (existing take priority to preserve created_session)
    merged: dict[str, MetaRule] = {}
    for meta in discovered:
        if meta.id in valid_existing:
            merged[meta.id] = valid_existing[meta.id]
        else:
            merged[meta.id] = meta

    # Also keep existing valid ones that weren't re-discovered
    # (source lessons may have been archived but meta-rule is still valid)
    for mid, meta in valid_existing.items():
        if mid not in merged:
            merged[mid] = meta

    result = sorted(merged.values(), key=lambda m: m.confidence, reverse=True)
    return result


# ---------------------------------------------------------------------------
# SQLite Storage
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meta_rules (
    id TEXT PRIMARY KEY,
    principle TEXT NOT NULL,
    source_categories TEXT,
    source_lesson_ids TEXT,
    confidence REAL,
    created_session INTEGER,
    last_validated_session INTEGER,
    scope TEXT,
    examples TEXT
);
"""


def ensure_table(db_path: str | Path) -> None:
    """Create the meta_rules table if it does not exist.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def save_meta_rules(db_path: str | Path, metas: list[MetaRule]) -> int:
    """Persist meta-rules to system.db, replacing all existing rows.

    Args:
        db_path: Path to the SQLite database file.
        metas: Meta-rules to save.

    Returns:
        Number of meta-rules saved.
    """
    ensure_table(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM meta_rules")
        for meta in metas:
            conn.execute(
                """INSERT INTO meta_rules
                   (id, principle, source_categories, source_lesson_ids,
                    confidence, created_session, last_validated_session,
                    scope, examples)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meta.id,
                    meta.principle,
                    json.dumps(meta.source_categories),
                    json.dumps(meta.source_lesson_ids),
                    meta.confidence,
                    meta.created_session,
                    meta.last_validated_session,
                    json.dumps(meta.scope),
                    json.dumps(meta.examples),
                ),
            )
        conn.commit()
        return len(metas)
    finally:
        conn.close()


def load_meta_rules(db_path: str | Path) -> list[MetaRule]:
    """Load meta-rules from system.db.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        List of :class:`MetaRule` objects, sorted by confidence
        descending.  Empty list if the table does not exist.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='meta_rules'"
        )
        if not cursor.fetchone():
            return []

        rows = conn.execute(
            """SELECT id, principle, source_categories, source_lesson_ids,
                      confidence, created_session, last_validated_session,
                      scope, examples
               FROM meta_rules
               ORDER BY confidence DESC"""
        ).fetchall()

        metas: list[MetaRule] = []
        for row in rows:
            metas.append(MetaRule(
                id=row[0],
                principle=row[1],
                source_categories=json.loads(row[2]) if row[2] else [],
                source_lesson_ids=json.loads(row[3]) if row[3] else [],
                confidence=row[4] or 0.0,
                created_session=row[5] or 0,
                last_validated_session=row[6] or 0,
                scope=json.loads(row[7]) if row[7] else {},
                examples=json.loads(row[8]) if row[8] else [],
            ))
        return metas
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Lesson Parsing (for testing with real data)
# ---------------------------------------------------------------------------

_LESSON_LINE_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\]\s+"
    r"\[(\w+):?([\d.]*)\]\s+"
    r"(\w[\w_/]*?):\s+"
    r"(.+)"
)


def parse_lessons_from_markdown(text: str) -> list[Lesson]:
    """Parse lessons from the markdown format used in lessons.md.

    Handles the format:
        [DATE] [STATE:CONFIDENCE] CATEGORY: description

    Args:
        text: Raw markdown text containing lesson entries.

    Returns:
        List of parsed :class:`Lesson` objects.
    """
    lessons: list[Lesson] = []
    for line in text.splitlines():
        line = line.strip()
        m = _LESSON_LINE_RE.match(line)
        if not m:
            continue

        date_str, state_str, conf_str, category, description = m.groups()

        # Map state string to enum
        state_map = {
            "INSTINCT": LessonState.INSTINCT,
            "PATTERN": LessonState.PATTERN,
            "RULE": LessonState.RULE,
            "UNTESTABLE": LessonState.UNTESTABLE,
        }
        state = state_map.get(state_str.upper(), LessonState.INSTINCT)

        confidence = float(conf_str) if conf_str else 0.50
        if state == LessonState.RULE and confidence < 0.90:
            confidence = 0.90

        # Extract root cause if present
        root_cause = ""
        if "Root cause:" in description:
            parts = description.split("Root cause:", 1)
            description = parts[0].strip()
            root_cause = parts[1].strip()

        lessons.append(Lesson(
            date=date_str,
            state=state,
            confidence=confidence,
            category=category.upper(),
            description=description,
            root_cause=root_cause,
        ))

    return lessons
