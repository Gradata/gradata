"""Rule Pipeline Orchestrator — 3-phase rule pipeline adapted from Hindsight retain.

SDK LAYER: Layer 1 (enhancements). Imports from self_improvement and shared types.

Extracted from self_improvement.py to keep that module focused on the core
graduation logic (confidence scoring, FSRS, graduation state machine).
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .._types import Lesson, LessonState

_log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a full rule pipeline run."""

    graduated: list[str] = field(default_factory=list)
    demoted: list[str] = field(default_factory=list)
    meta_rules_created: list[str] = field(default_factory=list)
    hooks_promoted: list[str] = field(default_factory=list)
    disposition_updates: dict[str, dict] = field(default_factory=dict)
    freshness_updates: int = 0
    errors: list[str] = field(default_factory=list)
    skills_generated: list[str] = field(default_factory=list)
    skills_updated: int = 0
    self_observation_candidates: int = 0
    patterns_lifted: int = 0


def _patterns_to_graduated_lessons(
    db_path: Path,
    current_session: int,
    min_sessions: int = 2,
    min_score: float = 3.0,
) -> list[Lesson]:
    """Lift graduated correction_patterns into synthetic RULE-state lessons.

    Before this wiring the 437-row correction_patterns table was orphaned --
    query_graduation_candidates had no production caller, so meta-rule
    synthesis never saw the real user corrections. This bridges the gap:
    clusters that already hit (sessions >= min_sessions, weight >= min_score)
    are lifted directly to RULE state for synthesis.
    """
    try:
        from ..enhancements.meta_rules_storage import (  # type: ignore[import]
            query_graduation_candidates,
        )
    except ImportError:
        return []
    if not db_path.is_file():
        return []

    try:
        candidates = query_graduation_candidates(
            db_path, min_sessions=min_sessions, min_score=min_score,
        )
    except Exception as exc:
        _log.debug("_patterns_to_graduated_lessons: query failed: %s", exc)
        return []

    lessons: list[Lesson] = []
    seen: set[tuple[str, str]] = set()
    for row in candidates:
        raw = row.get("representative_text") or ""
        # Drop evaluator-generated noise -- not real user corrections
        if raw.startswith("[AUTO]"):
            continue
        desc = raw.strip()
        for _npd_pfx in ("User corrected: ", "[AUTO] "):
            if desc.startswith(_npd_pfx):
                desc = desc[len(_npd_pfx):]
        if not desc:
            continue
        category = (row.get("category") or "GENERAL").upper()
        dedup_key = (category, desc)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        first_seen = str(row.get("first_seen") or "")[:10] or "2026-01-01"
        lessons.append(Lesson(
            date=first_seen,
            state=LessonState.RULE,
            confidence=0.92,
            category=category,
            description=desc,
            fire_count=int(row.get("distinct_sessions") or 2),
        ))
    return lessons


def _generate_skill_file(
    lesson: Lesson,
    output_dir: Path,
) -> Path | None:
    """Generate a SKILL.md file from a graduated rule.

    Only generates for rules meeting quality gate:
    - State == RULE
    - Confidence >= 0.90
    - fire_count >= 3

    Args:
        lesson: The lesson to convert into a skill file.
        output_dir: Root directory under which per-skill subdirs are created.

    Returns:
        Path to the written SKILL.md, or None if the lesson doesn't qualify.
    """
    if not hasattr(lesson, "state") or lesson.state.name != "RULE":
        return None
    if lesson.confidence < 0.90 or getattr(lesson, "fire_count", 0) < 3:
        return None

    # Survival events = correction_event_ids that survived (proxy: fire_count)
    survival_count = len(getattr(lesson, "correction_event_ids", []) or [])

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        f"{lesson.category}-{lesson.description[:40]}".lower(),
    ).strip("-")
    skill_dir = output_dir / slug
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_path = skill_dir / "SKILL.md"

    # Skip regeneration if skill exists and confidence hasn't changed significantly
    if skill_path.is_file():
        existing_text = skill_path.read_text(encoding="utf-8")
        conf_match = re.search(r"confidence:\s*([\d.]+)", existing_text)
        if conf_match:
            old_conf = float(conf_match.group(1))
            if abs(lesson.confidence - old_conf) < 0.05:
                return None  # No significant change — skip regeneration
        else:
            return None  # Can't parse old confidence — skip (don't assume infinite delta)

    from datetime import UTC, datetime

    updated_at = datetime.now(UTC).isoformat()

    content = f"""---
name: {lesson.description[:60]}
description: Auto-graduated from correction-driven learning (confidence {lesson.confidence:.2f}, fired {getattr(lesson, 'fire_count', 0)} times)
source: gradata-behavioral-engine
confidence: {lesson.confidence}
category: {lesson.category}
graduated_at_session: {getattr(lesson, 'created_session', 0)}
updated_at: {updated_at}
---

# {lesson.description}

**Category**: {lesson.category}
**Confidence**: {lesson.confidence:.2f}
**Times Applied**: {getattr(lesson, 'fire_count', 0)}

## Directive

{lesson.description}

## Context

This rule was learned from {survival_count} user corrections and graduated through INSTINCT -> PATTERN -> RULE stages with ablation validation.

## When to Apply

Apply this directive when working on tasks related to: {lesson.category}
"""

    skill_path.write_text(content, encoding="utf-8")
    return skill_path


def review_generated_skill(skill_path: Path) -> dict:
    """Review a generated skill file for quality issues.

    Returns dict with:
    - valid: bool
    - issues: list[str] - problems found
    - suggestions: list[str] - improvements
    - path: str - absolute path of the reviewed file
    """
    import re as _re

    text = skill_path.read_text(encoding="utf-8")
    issues: list[str] = []
    suggestions: list[str] = []

    # Check frontmatter exists
    if not text.startswith("---"):
        issues.append("Missing frontmatter")

    # Check minimum content length
    if len(text) < 100:
        issues.append("Skill too short (< 100 chars)")

    # Check for placeholder text
    if "(requires" in text.lower() or "todo" in text.lower():
        issues.append("Contains placeholder text")

    # Check confidence is reasonable
    conf_match = _re.search(r"confidence:\s*([\d.]+)", text)
    if conf_match:
        conf = float(conf_match.group(1))
        if conf < 0.90:
            issues.append(f"Low confidence ({conf:.2f}) - below RULE threshold")

    # Check description isn't too vague
    desc_match = _re.search(r"description:\s*(.+)", text)
    if desc_match:
        desc = desc_match.group(1).strip()
        if len(desc) < 20:
            suggestions.append("Description is very short - consider expanding")
        if desc.startswith("Auto-graduated"):
            suggestions.append("Description is generic - consider adding specific context")

    # Check directive section exists and has content
    if "## Directive" not in text:
        issues.append("Missing Directive section")
    elif text.split("## Directive")[1].split("##")[0].strip() == "":
        issues.append("Directive section is empty")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
        "path": str(skill_path),
    }


def run_rule_pipeline(
    lessons_path: Path,
    db_path: Path,
    current_session: int,
    corrections: list[dict] | None = None,
) -> PipelineResult:
    """Coordinated 3-phase rule pipeline.

    Adapted from Hindsight's 3-phase retain orchestrator:
    - Phase 1 (read): Load state, compute freshness, rank rules
    - Phase 2 (atomic): Graduate rules, create meta-rules, update confidence
    - Phase 3 (best-effort): Hook promotion, disposition updates, events

    Args:
        lessons_path: Path to lessons.md file.
        db_path: Path to system.db.
        current_session: Current session number.
        corrections: Recent corrections from this session.

    Returns:
        PipelineResult with all changes made.
    """
    from ..enhancements.self_improvement import (
        MIN_APPLICATIONS_FOR_PATTERN,
        MIN_APPLICATIONS_FOR_RULE,
        PATTERN_THRESHOLD,
        RULE_THRESHOLD,
        format_lessons,
        parse_lessons,
    )

    result = PipelineResult()
    corrections = corrections or []

    # ── Phase 1: Read (non-destructive) ──────────────────────────────────────
    # Load all state needed for decision-making. No writes.
    try:
        text = lessons_path.read_text(encoding="utf-8")
        all_lessons = parse_lessons(text)
    except Exception as exc:
        result.errors.append(f"Phase 1: failed to load lessons: {exc}")
        return result

    # Compute freshness for all graduated rules
    try:
        from ..enhancements.freshness import (  # type: ignore[import]
            Trend,
            compute_trend,
        )

        for lesson in all_lessons:
            if lesson.state.name in ("RULE", "PATTERN"):
                correction_sessions = [
                    {"session": current_session - i, "severity": "minor"}
                    for i in range(getattr(lesson, "fire_count", 0))
                ]
                trend = compute_trend(correction_sessions, current_session)
                if trend == Trend.STALE:
                    sessions_stale = getattr(lesson, "sessions_since_fire", 0)
                    if sessions_stale > 30:
                        decay = -0.01 * (sessions_stale - 29)
                        lesson.confidence = max(0.0, lesson.confidence + decay)
                        result.freshness_updates += 1
    except ImportError:
        pass  # freshness module not available

    # Rank rules using retrieval fusion if available
    try:
        from ..enhancements.retrieval_fusion import (  # type: ignore[import]
            ScoredRule,
            apply_correction_boost,
            reciprocal_rank_fusion,
        )

        scored_by_confidence = [
            ScoredRule(
                rule_id=getattr(l, "description", "")[:40],
                text=l.description,
                score=l.confidence,
                source="confidence",
                metadata={
                    "from_correction": bool(getattr(l, "correction_event_ids", None)),
                    "recency_score": 0.8 if l.state.name == "RULE" else 0.5,
                    "severity_score": 0.5,
                },
            )
            for l in all_lessons
            if l.state.name in ("RULE", "PATTERN") and l.confidence >= 0.60
        ]
        if scored_by_confidence:
            merged = reciprocal_rank_fusion([scored_by_confidence])
            apply_correction_boost(merged)
            _log.debug("Phase 1: ranked %d rules via fusion", len(merged))
    except ImportError:
        pass  # retrieval_fusion not available

    # ── Phase 1.5: Self-observation (consume SELF_REVIEW_VIOLATION events) ──
    # Must run after Phase 1 so all_lessons is already populated for dedup.
    try:
        from .._db import get_connection
        if db_path.is_file():
            conn = get_connection(db_path)
            rows = conn.execute(
                "SELECT data FROM events WHERE type = 'SELF_REVIEW_VIOLATION' "
                "AND session = ? ORDER BY id DESC LIMIT 20",
                (current_session,),
            ).fetchall()
            conn.close()

            import json as _json
            for row in rows:
                try:
                    vdata = _json.loads(row[0]) if isinstance(row[0], str) else row[0]
                except (TypeError, _json.JSONDecodeError):
                    continue
                rule_desc = vdata.get("rule", "")
                cat = vdata.get("category", "UNKNOWN").upper()
                if not rule_desc:
                    continue
                desc = f"Violated: {rule_desc}"
                already_exists = any(
                    l.category == cat and l.description == desc
                    for l in all_lessons
                )
                if already_exists:
                    continue
                from datetime import date as _date

                from .._types import Lesson as _Lesson
                candidate = _Lesson(
                    date=_date.today().isoformat(),
                    state=LessonState.INSTINCT,
                    confidence=0.40,
                    category=cat,
                    description=desc,
                    pending_approval=True,
                    agent_type="self_observation",
                )
                all_lessons.append(candidate)
                result.self_observation_candidates += 1
    except (ImportError, Exception) as exc:
        result.errors.append(f"Phase 0: self-observation: {exc}")

    # ── Phase 1.6: Lift graduated correction_patterns into all_lessons ───────
    # Bridges the orphaned correction_patterns table (437 user corrections)
    # into synthesis. Without this, RULE-state lessons come only from
    # lessons.md which can be empty on fresh brains.
    try:
        pattern_lessons = _patterns_to_graduated_lessons(db_path, current_session)
        if pattern_lessons:
            existing_keys = {(l.category, l.description) for l in all_lessons}
            for pl in pattern_lessons:
                if (pl.category, pl.description) not in existing_keys:
                    all_lessons.append(pl)
                    result.patterns_lifted += 1
    except Exception as exc:
        result.errors.append(f"Phase 1.6: pattern lift: {exc}")

    # ── Phase 2: Atomic writes ────────────────────────────────────────────────
    # Graduate rules, update confidence, create meta-rules.
    for lesson in all_lessons:
        if (
            lesson.state.name == "INSTINCT"
            and lesson.confidence >= PATTERN_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
        ):
            lesson.state = LessonState.PATTERN
            result.graduated.append(f"{lesson.category}:{lesson.description[:30]}")
        elif (
            lesson.state.name == "PATTERN"
            and lesson.confidence >= RULE_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
        ):
            lesson.state = LessonState.RULE
            result.graduated.append(f"{lesson.category}:{lesson.description[:30]}")

    # Synthesize meta-rules from graduated rules
    try:
        from ..enhancements.meta_rules import (
            synthesize_meta_rules_agentic,  # type: ignore[import]
        )
        from ..enhancements.meta_rules_storage import (  # type: ignore[import]
            load_meta_rules,
            save_meta_rules,
        )

        existing_metas = []
        if db_path.is_file():
            existing_metas = load_meta_rules(db_path)

        new_metas = synthesize_meta_rules_agentic(
            lessons=all_lessons,
            existing_metas=existing_metas,
            current_session=current_session,
        )
        if new_metas and db_path.is_file():
            save_meta_rules(db_path, existing_metas + new_metas)
            result.meta_rules_created = [m.id for m in new_metas]
    except (ImportError, Exception) as exc:
        result.errors.append(f"Phase 2: meta-rule synthesis: {exc}")

    # Write lessons back
    try:
        lessons_path.write_text(format_lessons(all_lessons), encoding="utf-8")
    except Exception as exc:
        result.errors.append(f"Phase 2: failed to write lessons: {exc}")

    # ── Phase 3: Best-effort (non-critical) ───────────────────────────────────
    # Hook promotion, disposition updates, event emission.
    # Failures here are logged but don't abort the pipeline.

    # Hook promotion for newly graduated RULE-state lessons
    try:
        from ..enhancements.rule_to_hook import classify_rule, promote  # type: ignore[import]

        for lesson in all_lessons:
            if lesson.state.name == "RULE" and lesson.confidence >= RULE_THRESHOLD:
                candidate = classify_rule(lesson.description, lesson.confidence)
                if candidate.determinism.value != "not_deterministic":
                    try:
                        gen_result = promote(
                            lesson.description,
                            lesson.confidence,
                            lesson=lesson,
                            source="pipeline",
                        )
                        if getattr(gen_result, "installed", False):
                            result.hooks_promoted.append(lesson.description[:40])
                    except Exception as exc:
                        result.errors.append(f"Phase 3: hook promotion: {exc}")
    except ImportError:
        pass

    # Disposition updates from this session's corrections
    try:
        from ..enhancements.behavioral_engine import (
            DispositionTracker,  # type: ignore[import]
        )

        tracker = DispositionTracker()
        disp_path = lessons_path.parent / "disposition.json"
        if disp_path.is_file():
            import json as _json
            tracker = DispositionTracker.from_dict(
                _json.loads(disp_path.read_text(encoding="utf-8"))
            )
        for correction in corrections:
            category = correction.get("category", "")
            severity = correction.get("severity", "minor")
            domain = correction.get("domain", "global")
            disp = tracker.update_from_correction(domain, category, severity)
            if domain not in result.disposition_updates:
                result.disposition_updates[domain] = {
                    "skepticism": disp.skepticism,
                    "literalism": disp.literalism,
                    "empathy": disp.empathy,
                }
        if result.disposition_updates:
            try:
                import json as _json
                disp_path.write_text(
                    _json.dumps(tracker.to_dict(), indent=2), encoding="utf-8",
                )
            except Exception as exc:
                result.errors.append(f"Phase 3: disposition write: {exc}")
    except ImportError:
        pass

    # Skill generation for high-confidence rules (best-effort, env-gated)
    if os.environ.get("GRADATA_ENABLE_SKILL_EXPORT"):
        try:
            skills_dir = lessons_path.parent.parent / ".claude" / "skills" / "generated"
            for lesson in all_lessons:
                # Detect whether skill file pre-existed to distinguish new vs updated
                slug = re.sub(
                    r"[^a-z0-9]+",
                    "-",
                    f"{lesson.category}-{lesson.description[:40]}".lower(),
                ).strip("-")
                skill_existed = (skills_dir / slug / "SKILL.md").is_file()
                skill_path = _generate_skill_file(lesson, skills_dir)
                if skill_path:
                    review = review_generated_skill(skill_path)
                    if not review["valid"]:
                        skill_path.unlink(missing_ok=True)
                        result.errors.append(f"Phase 3: skill rejected: {review['issues']}")
                    else:
                        result.skills_generated.append(str(skill_path))
                        if skill_existed:
                            result.skills_updated += 1
        except Exception as exc:
            result.errors.append(f"Phase 3: skill generation: {exc}")

    # Rule verification for this session's corrections (best-effort, env-gated)
    if os.environ.get("GRADATA_RULE_VERIFIER") and corrections and db_path.is_file():
        try:
            applied_rules = [{"category": l.category, "description": l.description} for l in all_lessons]
            for correction in corrections:
                output = correction.get("draft", "")
                if not output:
                    continue
                verifications = verify_rules(output, applied_rules)
                if verifications:
                    log_verification(session=current_session, results=verifications, db_path=db_path)
        except Exception as exc:
            result.errors.append(f"Phase 3: rule verification: {exc}")

    _log.info(
        "Pipeline complete: %d graduated, %d meta-rules, %d hooks, %d freshness updates, %d skills, %d errors",
        len(result.graduated),
        len(result.meta_rules_created),
        len(result.hooks_promoted),
        result.freshness_updates,
        len(result.skills_generated),
        len(result.errors),
    )
    return result


def build_knowledge_graph(lessons_path: Path, db_path: Path) -> dict:
    """Assemble existing lessons data into a queryable knowledge graph.

    Args:
        lessons_path: Path to lessons.md.
        db_path: Path to system.db (unused directly; passed for future causal link queries).

    Returns:
        Dict with keys: nodes, clusters, causal_links, contradictions, cross_domain, stats.
    """
    from ..enhancements.self_improvement import parse_lessons

    graph: dict = {
        "nodes": [],
        "clusters": [],
        "causal_links": [],
        "contradictions": [],
        "cross_domain": [],
        "stats": {},
    }

    if not lessons_path.is_file():
        graph["stats"] = {
            "total_nodes": 0,
            "clusters": 0,
            "contradictions": 0,
            "cross_domain": 0,
            "causal_links": 0,
        }
        return graph

    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)

    # Nodes: each lesson is a node
    for lesson in lessons:
        graph["nodes"].append({
            "id": f"{lesson.category}:{lesson.description[:40]}",
            "description": lesson.description,
            "category": lesson.category,
            "confidence": lesson.confidence,
            "state": lesson.state.name,
            "fire_count": getattr(lesson, "fire_count", 0),
        })

    # Clusters
    try:
        from ..enhancements.clustering import cluster_rules  # type: ignore[import]
        graph["clusters"] = [
            {
                "cluster_id": c.cluster_id,
                "domain": c.domain,
                "category": c.category,
                "size": c.size,
                "confidence": c.cluster_confidence,
                "has_contradictions": c.has_contradictions,
            }
            for c in cluster_rules(lessons)
        ]
    except (ImportError, Exception):
        pass

    # Contradictions (across graduated rules)
    try:
        from ..enhancements.clustering import detect_contradictions  # type: ignore[import]
        graduated = [l for l in lessons if l.state.name in ("RULE", "PATTERN")]
        graph["contradictions"] = [
            {"rule_a": a, "rule_b": b}
            for a, b in detect_contradictions(graduated)
        ]
    except (ImportError, Exception):
        pass

    # Cross-domain candidates
    try:
        from ..enhancements.meta_rules import (
            detect_cross_domain_candidates,  # type: ignore[import]
        )
        graph["cross_domain"] = detect_cross_domain_candidates(lessons)
    except (ImportError, Exception):
        pass

    graph["stats"] = {
        "total_nodes": len(graph["nodes"]),
        "clusters": len(graph["clusters"]),
        "contradictions": len(graph["contradictions"]),
        "cross_domain": len(graph["cross_domain"]),
        "causal_links": len(graph["causal_links"]),
    }

    return graph


# ---------------------------------------------------------------------------
# Rule verification (pre-execution filter + post-hoc output checker)
# Merged from rule_verifier.py for consolidation.
# ---------------------------------------------------------------------------

TOOL_RULE_MATRIX: dict[str, list[str]] = {
    "Write": ["DRAFTING", "ARCHITECTURE", "IP_PROTECTION", "ACCURACY"],
    "Edit": ["DRAFTING", "ARCHITECTURE", "ACCURACY"],
    "Bash": ["PROCESS", "VERIFICATION", "CONSTRAINT"],
    "email_draft": ["DRAFTING", "COMMUNICATION", "POSITIONING", "PRICING"],
    "demo_prep": ["DEMO_PREP", "ACCURACY", "PRESENTATION"],
    "prospecting": ["LEADS", "CONSTRAINT", "DATA_INTEGRITY"],
    "code": ["ARCHITECTURE", "THOROUGHNESS", "VERIFICATION"],
}


def should_verify(tool_type: str, rule_category: str) -> bool:
    """Pre-execution gate: True if rule category is relevant for the tool."""
    relevant = TOOL_RULE_MATRIX.get(tool_type)
    if relevant is None:
        return True
    return rule_category.upper() in (c.upper() for c in relevant)


def get_relevant_rules(tool_type: str, all_rules: list[dict]) -> list[dict]:
    """Filter rules to those relevant for the tool/task per TOOL_RULE_MATRIX."""
    return [
        rule for rule in all_rules
        if should_verify(tool_type, rule.get("category", "UNKNOWN"))
    ]


_PATTERNS: list[tuple[str, str, bool, str]] = [
    ("em dash", r"\u2014|--", True, "contains em dash or double dash"),
    ("em dashes", r"\u2014|--", True, "contains em dash or double dash"),
    ("pricing", r"\$\d+", True, "contains dollar amount"),
    ("dollar", r"\$\d+", True, "contains dollar amount"),
    ("booking link", r"https?://\S+/\S+", False, "missing booking link"),
    ("hyperlink", r"<a\s+href=", False, "missing HTML hyperlink"),
    ("bold", r"\*\*[^*]+\*\*", True, "contains markdown bold"),
    ("annual", r"\bannual\b|\byearly\b|\bper year\b", True, "references annual pricing"),
    ("raw url", r"(?<!\")https?://\S+(?!\")", True, "contains raw URL (should be hyperlinked)"),
]


@dataclass
class RuleVerification:
    rule_category: str
    rule_description: str
    passed: bool
    violation_detail: str = ""
    output_snippet: str = ""


def auto_detect_verification(rule_description: str) -> list[tuple[re.Pattern, bool, str]]:
    """Scan rule description for checkable regex patterns."""
    desc_lower = rule_description.lower()
    checks = []
    seen = set()
    for keyword, pattern, absent, desc in _PATTERNS:
        if keyword in desc_lower and pattern not in seen:
            checks.append((re.compile(pattern, re.IGNORECASE), absent, desc))
            seen.add(pattern)
    return checks


def verify_rules(
    output: str,
    applied_rules: list[dict],
    context: dict | None = None,
) -> list[RuleVerification]:
    """Check output against applied rules; returns one RuleVerification per checkable rule."""
    tool_type = (context or {}).get("tool_type", "")
    if tool_type:
        applied_rules = get_relevant_rules(tool_type, applied_rules)

    results = []
    for rule in applied_rules:
        desc = rule.get("description", "")
        cat = rule.get("category", "UNKNOWN")
        checks = auto_detect_verification(desc)
        if not checks:
            continue
        for regex, should_be_absent, violation_desc in checks:
            match = regex.search(output)
            if should_be_absent and match:
                results.append(RuleVerification(
                    rule_category=cat,
                    rule_description=desc[:200],
                    passed=False,
                    violation_detail=violation_desc,
                    output_snippet=output[max(0, match.start() - 30):match.end() + 30][:200],
                ))
            elif not should_be_absent and not match:
                results.append(RuleVerification(
                    rule_category=cat,
                    rule_description=desc[:200],
                    passed=False,
                    violation_detail=violation_desc,
                    output_snippet=output[:200],
                ))
            else:
                results.append(RuleVerification(
                    rule_category=cat,
                    rule_description=desc[:200],
                    passed=True,
                ))
    return results


_CREATE_VERIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS rule_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session INTEGER,
    rule_category TEXT,
    rule_description TEXT,
    passed BOOLEAN,
    violation_detail TEXT,
    output_snippet TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_table(db_path: Path) -> None:
    from .._db import ensure_table as _ensure
    from .._db import get_connection
    conn = get_connection(db_path)
    _ensure(conn, _CREATE_VERIFICATIONS_TABLE)
    conn.close()


def log_verification(
    session: int,
    results: list[RuleVerification],
    db_path: Path,
) -> None:
    """Write verification results to SQLite."""
    ensure_table(db_path)
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(str(db_path)) as conn:
        for r in results:
            conn.execute(
                "INSERT INTO rule_verifications "
                "(session, rule_category, rule_description, passed, violation_detail, output_snippet, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session, r.rule_category, r.rule_description, r.passed,
                 r.violation_detail, r.output_snippet, now),
            )


def get_verification_stats(db_path: Path) -> dict:
    """Return summary stats from the rule_verifications table."""
    ensure_table(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM rule_verifications").fetchone()[0]
        passed = conn.execute("SELECT COUNT(*) FROM rule_verifications WHERE passed = 1").fetchone()[0]
        violations = conn.execute(
            "SELECT rule_category, COUNT(*) FROM rule_verifications "
            "WHERE passed = 0 GROUP BY rule_category ORDER BY COUNT(*) DESC"
        ).fetchall()
    return {
        "total_checks": total,
        "passed": passed,
        "pass_rate": passed / total if total > 0 else 1.0,
        "violations_by_category": dict(violations),
    }
