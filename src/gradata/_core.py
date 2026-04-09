"""Brain core — Heavy methods extracted from mixins for the consolidated Brain class.

These functions take a Brain instance as the first argument and implement
the heavy logic for correct(), end_session(), auto_evolve(), etc.
Brain.py delegates to these to stay under 500 lines.
"""

from __future__ import annotations

import contextlib
import logging
import re  # used by export functions for slug sanitization
from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from gradata._types import Lesson
    from gradata.brain import Brain

_log = logging.getLogger("gradata")

# Lesson state ordering for filtering by minimum state
_STATE_RANK = {"INSTINCT": 0, "PATTERN": 1, "RULE": 2}
# Severity ordering for min_severity gating
_SEV_RANK = {"as-is": 0, "minor": 1, "moderate": 2, "major": 3, "discarded": 4}

# Map evaluator dimension names to correction categories
_DIMENSION_CATEGORY_MAP = {
    "task_alignment": "ACCURACY", "completeness": "STRUCTURE",
    "accuracy": "ACCURACY", "clarity": "DRAFTING", "conciseness": "DRAFTING",
    "tone": "TONE", "formatting": "FORMAT", "security": "SECURITY",
}


def _filter_lessons_by_state(lessons, min_state: str = "PATTERN"):
    """Filter lessons by minimum state rank."""
    min_rank = _STATE_RANK.get(min_state.upper(), 1)
    return [lesson for lesson in lessons
            if _STATE_RANK.get(lesson.state.value, -1) >= min_rank and lesson.confidence > 0.0]


# ── correct() ──────────────────────────────────────────────────────────


def _attribute_domain_fires(
    brain: Brain,
    correction_category: str,
    correction_desc: str,
) -> None:
    """Attribute fires and misfires to rules active in this session.

    For each fired rule, increment fires for the correction's category.
    If the correction contradicts the rule, also increment misfires.
    """
    from gradata.enhancements.self_improvement import _classify_correction_direction

    for rule in brain._fired_rules:
        if not hasattr(rule, "domain_scores"):
            continue
        domain = correction_category.upper()
        if domain not in rule.domain_scores:
            rule.domain_scores[domain] = {"fires": 0, "misfires": 0}
        rule.domain_scores[domain]["fires"] += 1

        direction = _classify_correction_direction(correction_desc, rule.description)
        if direction == "CONTRADICTING":
            rule.domain_scores[domain]["misfires"] += 1

            # Record conflict in rule graph
            if hasattr(brain, '_rule_graph') and brain._rule_graph:
                rule_id = f"{rule.category}:{hash(rule.description) % 10000:04d}"
                correction_id = f"{correction_category}:{hash(correction_desc) % 10000:04d}"
                brain._rule_graph.add_conflict(rule_id, correction_id)


def brain_correct(
    brain: Brain, draft: str, final: str, *,
    category: str | None = None, context: dict | None = None,
    session: int | None = None, agent_type: str | None = None,
    approval_required: bool = False, dry_run: bool = False,
    min_severity: str = "as-is", scope: str | None = None,
) -> dict:
    """Record a correction: user edited draft into final version."""
    # Input validation
    draft = draft or ""
    final = final or ""
    if not draft and not final:
        raise ValueError("Both draft and final are empty — nothing to correct.")
    if draft == final:
        raise ValueError("draft and final are identical — no correction detected.")
    max_input = 100_000
    if len(draft) + len(final) > max_input:
        raise ValueError(f"Combined input length ({len(draft) + len(final)}) exceeds limit ({max_input}).")
    if session is not None and (not isinstance(session, int) or session < 1):
        raise ValueError(f"session must be a positive integer, got {session!r}")

    # Normalize and validate scope
    _valid_scopes = {"domain", "one_off", "universal", "project"}
    if scope is not None:
        scope = str(scope).strip().lower() or None
        if scope is not None and scope not in _valid_scopes:
            raise ValueError(f"Unsupported correction scope: {scope!r}. Must be one of {_valid_scopes}")

    # Route to cloud if connected
    if brain._cloud and brain._cloud.connected:
        try:
            return brain._cloud.correct(draft, final, category, context, session)
        except Exception as e:
            _log.warning("Cloud correct() failed, falling back to local: %s", e)
            brain._cloud.connected = False

    # Full enhancement pipeline
    try:
        from gradata.enhancements.diff_engine import compute_diff
        from gradata.enhancements.edit_classifier import classify_edits, summarize_edits
    except ImportError:
        data = {"draft_text": draft[:2000], "final_text": final[:2000],
                "edit_distance": 0.0, "severity": "unknown", "outcome": "unknown",
                "major_edit": False, "category": category or "UNKNOWN",
                "summary": "", "classifications": []}
        result = brain.emit("CORRECTION", "brain.correct", data,
                            [f"category:{category or 'UNKNOWN'}"], session)
        brain.bus.emit("correction.created", {
            "lesson": {},
            "severity": "unknown",
            "category": category or "GENERAL",
            "diff": "",
            "source": "human",
        })
        return result

    from gradata._scope import build_scope

    diff = compute_diff(draft, final)
    classifications = classify_edits(diff)
    summary = summarize_edits(classifications)

    if not category and classifications:
        category = classifications[0].category.upper()

    # PII redaction — runs AFTER extraction on full text, BEFORE storage
    try:
        from gradata.safety import redact_pii_with_report
        draft_redacted, _ = redact_pii_with_report(draft)
        final_redacted, _ = redact_pii_with_report(final)
    except ImportError:
        draft_redacted, final_redacted = draft, final

    scope_obj = build_scope(context) if context else None
    scope_data = {}
    if scope_obj:
        from gradata._scope import scope_to_dict
        scope_data = scope_to_dict(scope_obj)

    # Tag correction scope (default: domain)
    correction_scope = scope or "domain"
    scope_data["correction_scope"] = correction_scope

    data = {
        "draft_text": draft_redacted[:2000], "final_text": final_redacted[:2000],
        "edit_distance": diff.edit_distance, "severity": diff.severity,
        "outcome": diff.severity, "major_edit": diff.severity in ("major", "discarded"),
        "category": category or "UNKNOWN", "summary": summary,
        "classifications": [{"category": c.category, "severity": c.severity,
                             "description": c.description} for c in classifications],
        "lines_added": diff.summary_stats.get("lines_added", 0),
        "lines_removed": diff.summary_stats.get("lines_removed", 0),
        "correction_scope": correction_scope,
    }
    if scope_data:
        data["scope"] = scope_data

    tags = [f"category:{category or 'UNKNOWN'}", f"severity:{diff.severity}"]
    if diff.severity in ("major", "discarded"):
        tags.append("major_edit:true")

    event = brain.emit("CORRECTION", "brain.correct", data, tags, session)
    event["diff"] = diff
    event["classifications"] = classifications
    event["correction_scope"] = correction_scope

    # Auto-extract patterns
    try:
        from gradata.enhancements.pattern_extractor import extract_patterns
        patterns = extract_patterns(classifications, scope=scope_obj)
        if patterns:
            event["patterns_extracted"] = len(patterns)
    except Exception as e:
        _log.warning("Pattern extraction failed: %s", e)

    # Close the loop: correction → lesson
    desc = ""  # Will be set if severity threshold is met
    try:
        from datetime import date as _date

        from gradata._types import Lesson, LessonState
        from gradata.enhancements.self_improvement import (
            INITIAL_CONFIDENCE,
            format_lessons,
            parse_lessons,
            update_confidence,
        )

        if _SEV_RANK.get(diff.severity, 0) >= _SEV_RANK.get(min_severity, 0):
            lessons_path = brain._find_lessons_path(create=True)
            if lessons_path:
                existing_text = ""
                if lessons_path.is_file():
                    existing_text = lessons_path.read_text(encoding="utf-8")
                existing_lessons = parse_lessons(existing_text) if existing_text else []

                cat = (category or "UNKNOWN").upper()
                if classifications:
                    primary = next((c for c in classifications if c.category.upper() == cat),
                                   classifications[0])
                    # Check convergence gate — skip extraction if category is settled
                    convergence_data = brain._get_convergence()
                    cat_convergence = convergence_data.get("by_category", {}).get(cat, {})
                    category_converged = cat_convergence.get("trend") == "converged"

                    if category_converged:
                        _log.debug("Skipping extraction for converged category: %s", cat)
                        desc = primary.description
                    else:
                        # Try behavioral extraction:
                        # 1. Archetype-based (sentence-level, deterministic)
                        # 2. Keyword templates (fallback)
                        # 3. LLM refinement (when connected)
                        try:
                            from gradata.enhancements.behavioral_extractor import (
                                extract_instruction,
                            )
                            behavioral_desc = extract_instruction(
                                draft, final, primary, category=cat,
                            )
                            if not behavioral_desc:
                                # Fallback to keyword templates
                                from gradata.enhancements.edit_classifier import (
                                    extract_behavioral_instruction,
                                )
                                from gradata.enhancements.instruction_cache import InstructionCache
                                if not isinstance(brain._instruction_cache, InstructionCache):
                                    brain._instruction_cache = InstructionCache(
                                        lessons_path.parent / "instruction_cache.json"
                                    )
                                behavioral_desc = extract_behavioral_instruction(
                                    diff, primary, cache=brain._instruction_cache,  # type: ignore[arg-type]
                                )
                            desc = behavioral_desc or primary.description
                        except Exception as e:
                            _log.debug("Behavioral extraction failed: %s", e)
                            desc = primary.description
                elif summary:
                    desc = summary
                else:
                    desc = f"Corrected {cat.lower()} ({diff.severity})"

                from gradata.enhancements.similarity import best_similarity

                best_match, best_sim = None, 0.0
                for existing_l in existing_lessons:
                    if existing_l.category != cat:
                        continue
                    sim = best_similarity(desc, existing_l.description)
                    if sim > best_sim:
                        best_sim = sim
                        best_match = existing_l

                from gradata._config import get_similarity_threshold
                sim_threshold = get_similarity_threshold(cat)
                if best_match and best_sim >= sim_threshold:
                    if dry_run:
                        event["dry_run"] = True
                        event["would_reinforce"] = {"category": cat, "description": best_match.description[:200], "similarity": round(best_sim, 3)}
                        return event
                    best_match.fire_count += 1
                    if len(desc) > len(best_match.description):
                        best_match.description = desc
                    correction_id = str(event.get("id", "")) if event.get("id") else ""
                    if correction_id and correction_id not in best_match.correction_event_ids:
                        best_match.correction_event_ids.append(correction_id)
                    event["lesson_reinforced"] = True
                    event["lesson_category"] = cat
                    try:
                        brain.emit("LESSON_CHANGE", "brain.correct", {
                            "action": "reinforced", "lesson_category": cat,
                            "lesson_description": best_match.description[:200],
                            "fire_count": best_match.fire_count,
                            "source_correction_id": event.get("id"),
                        }, [f"category:{cat}", "provenance"], session)
                    except Exception as e:
                        _log.debug("Provenance emit failed: %s", e)
                else:
                    import json as _json
                    lesson_scope = ""
                    if agent_type or context:
                        scope_ctx = dict(context or {})
                        if agent_type:
                            scope_ctx["agent_type"] = agent_type
                        scope_obj = build_scope(scope_ctx)
                        scope_dict = {k: v for k, v in scope_obj.__dict__.items() if v and v != "normal"}
                    else:
                        scope_dict = {}
                    # Always tag correction_scope on new lessons
                    scope_dict["correction_scope"] = correction_scope
                    lesson_scope = _json.dumps(scope_dict)

                    init_conf = 0.0 if approval_required else INITIAL_CONFIDENCE
                    correction_id = str(event.get("id", "")) if event.get("id") else ""
                    new_lesson = Lesson(
                        date=_date.today().isoformat(), state=LessonState.INSTINCT,
                        confidence=init_conf, category=cat, description=desc,
                        scope_json=lesson_scope, agent_type=agent_type or "",
                        correction_event_ids=[correction_id] if correction_id else [],
                        pending_approval=approval_required)

                    if dry_run:
                        event["dry_run"] = True
                        event["proposed_lesson"] = {
                            "category": cat, "description": desc,
                            "state": LessonState.INSTINCT.value, "confidence": init_conf,
                            "scope": lesson_scope or None, "approval_required": approval_required}
                        return event

                    existing_lessons.append(new_lesson)
                    event["lessons_created"] = 1
                    if approval_required:
                        event["approval_required"] = True
                        try:
                            from gradata._db import get_connection
                            with get_connection(brain.db_path) as conn:
                                conn.execute(
                                    "INSERT INTO pending_approvals "
                                    "(lesson_category, lesson_description, draft_text, final_text, "
                                    "severity, correction_event_id, agent_type, created_at) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                    (cat, desc[:500], draft_redacted[:2000], final_redacted[:2000],
                                     diff.severity, correction_id, agent_type or "",
                                     _date.today().isoformat()))
                        except Exception as e:
                            _log.debug("pending_approvals insert failed: %s", e)
                    _log.info("New lesson: [INSTINCT:%.2f] %s", init_conf, cat)
                    try:
                        brain.emit("LESSON_CHANGE", "brain.correct", {
                            "action": "created", "lesson_category": cat,
                            "lesson_description": desc[:200],
                            "initial_confidence": INITIAL_CONFIDENCE,
                            "source_correction_id": event.get("id"),
                        }, [f"category:{cat}", "provenance"], session)
                    except Exception as e:
                        _log.debug("Provenance emit failed: %s", e)

                # Update confidence
                correction_data = [{"category": cat, "severity_label": diff.severity, "description": desc}]
                severity_data = {cat: diff.severity}
                existing_lessons = update_confidence(
                    existing_lessons, correction_data, severity_data=severity_data,
                    salt=getattr(brain, "_brain_salt", ""))

                from gradata._db import write_lessons_safe
                write_lessons_safe(lessons_path, format_lessons(existing_lessons))
                if "lessons_created" not in event:
                    event["lessons_updated"] = True

    except Exception as e:
        _log.warning("Lesson creation failed: %s", e)

    # Domain-scoped misfire attribution (then clear fired rules to prevent unbounded growth)
    try:
        if brain._fired_rules and (category or classifications):
            correction_desc = desc if desc else (summary or "")
            _attribute_domain_fires(brain, category or "UNKNOWN", correction_desc)
            brain._fired_rules = []
    except Exception as e:
        _log.debug("Domain fire attribution failed: %s", e)

    # Self-healing: detect rule failures
    try:
        from gradata.enhancements.self_healing import detect_rule_failure
        from gradata.enhancements.self_improvement import parse_lessons as _sh_parse

        _sh_lessons_path = brain._find_lessons_path()
        _sh_all_lessons = _sh_parse(
            _sh_lessons_path.read_text(encoding="utf-8")
        ) if _sh_lessons_path and _sh_lessons_path.is_file() else []

        failure = detect_rule_failure(
            lessons=_sh_all_lessons,
            correction_category=category or "UNKNOWN",
            correction_description=desc or summary or "",
        )
        if failure:
            failure["correction_event_id"] = event.get("id")
            failure["correction_severity"] = diff.severity
            brain.emit(
                "RULE_FAILURE", "brain.correct:self_healing",
                failure,
                [f"category:{failure['failed_rule_category']}", "self_healing"],
                session,
            )
            event["rule_failure_detected"] = True
    except Exception as e:
        _log.debug("Self-healing detection failed: %s", e)

    # Persist rule graph
    if hasattr(brain, '_rule_graph') and brain._rule_graph:
        with contextlib.suppress(Exception):
            brain._rule_graph.save()

    # Index into FTS5
    try:
        from datetime import date as _fts_date

        from gradata._query import fts_index
        fts_index(source="corrections", file_type="correction",
                  text=f"{category or 'UNKNOWN'}: {summary or diff.severity} - {final_redacted[:500]}",
                  embed_date=_fts_date.today().isoformat(), ctx=brain.ctx)
    except Exception as e:
        _log.debug("FTS index failed: %s", e)

    # Derive task_type once for pipeline + Q-router
    task_type = context.get("task_type", context.get("task", "")) if context else ""

    # Run through procedural memory pipeline
    if brain._learning_pipeline:
        try:
            pipeline_result = brain._learning_pipeline.process_correction(
                draft=draft, final=final, severity=diff.severity,
                category=category or "UNKNOWN", session_id=str(session or ""),
                task_type=task_type, occurrence_count=1)
            event["pipeline"] = {
                "stages_completed": pipeline_result.stages_completed,
                "is_high_value": pipeline_result.is_high_value,
                "discriminator_confidence": pipeline_result.discriminator_confidence,
                "recommendation": pipeline_result.discriminator_recommendation,
                "cluster_id": pipeline_result.cluster_id,
                "context_bracket": pipeline_result.context_bracket,
                "memory_type": pipeline_result.memory_type,
                "processing_time_ms": pipeline_result.processing_time_ms}
        except Exception as e:
            _log.warning("Learning pipeline failed: %s", e)

    # Feed Q-router
    if agent_type:
        try:
            from gradata.enhancements.pattern_integration import feed_q_router
            feed_q_router(brain, diff.severity, agent_type=agent_type, task_type=task_type)
        except Exception as e:
            _log.debug("Q-router feed failed: %s", e)

    brain.bus.emit("correction.created", {
        "lesson": event.get("lesson", {}),
        "severity": event.get("data", {}).get("severity", "unknown"),
        "category": category or "GENERAL",
        "diff": str(event.get("diff", "")),
        "source": "human",
    })

    # Correction provenance — HMAC-signed proof of who corrected what
    try:
        import hashlib as _hashlib
        import json

        from gradata.security.correction_provenance import create_provenance_record
        correction_hash = _hashlib.sha256(
            json.dumps([draft, final], separators=(",", ":")).encode()
        ).hexdigest()
        user_id = context.get("user_id", "unknown") if context else "unknown"
        _prov_salt = getattr(brain, "_brain_salt", "")
        if not _prov_salt:
            _log.warning("brain._brain_salt is empty; skipping provenance HMAC")
            raise ValueError("empty salt")
        provenance = create_provenance_record(
            user_id=user_id, correction_hash=correction_hash,
            session=session or 0,
            salt=_prov_salt,
        )
        event["provenance"] = provenance
    except Exception:
        pass  # Never block corrections

    return event


# ── end_session() ──────────────────────────────────────────────────────


def _graduation_message(old_state: str, lesson: Lesson) -> str:
    """Generate a user-facing graduation notification message."""
    if lesson.state.value == "PATTERN":
        return (f"You've corrected this {lesson.fire_count} times — "
                f"Gradata learned it: \"{lesson.description[:80]}\"")
    elif lesson.state.value == "RULE":
        return (f"Graduated to RULE: \"{lesson.description[:80]}\" — "
                f"this correction is now permanent ({lesson.confidence:.0%} confidence)")
    return f"Lesson updated: {lesson.description[:80]}"


def brain_end_session(
    brain: Brain, *, session_corrections: list[dict] | None = None,
    session_type: str = "full", machine_mode: bool | None = None,
    skip_meta_rules: bool = False,
) -> dict:
    """Run full graduation sweep at end of session."""
    try:
        from gradata.enhancements.self_improvement import (
            format_lessons,
            graduate,
            parse_lessons,
            update_confidence,
        )

        lessons_path = brain._find_lessons_path()
        if not lessons_path or not lessons_path.is_file():
            return {"error": "no lessons.md found"}

        lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
        if not lessons:
            return {"session": brain.session, "lessons": 0, "promotions": 0, "demotions": 0}

        # Use category + description prefix as key to avoid collisions
        # when two lessons share the same first 40 chars of description.
        def _lesson_key(lesson):
            return f"{lesson.category}:{lesson.description[:60]}"
        before_states = {_lesson_key(lesson): lesson.state.value for lesson in lessons}

        lessons = update_confidence(
            lessons, session_corrections or [],
            session_type=session_type, machine_mode=machine_mode,
            salt=getattr(brain, "_brain_salt", ""))

        # Auto-detect machine mode: human sessions rarely exceed 30 corrections.
        # Previous threshold of 10 misclassified productive human sessions.
        is_machine = machine_mode if machine_mode is not None else (
            len(session_corrections or []) > 30)
        _salt = getattr(brain, "_brain_salt", "")
        active, graduated = graduate(lessons, machine_mode=is_machine, salt=_salt)

        promotions, demotions, kills = 0, 0, 0
        transitions = []
        for lesson in active + graduated:
            key = _lesson_key(lesson)
            old_state = before_states.get(key, "")
            new_state = lesson.state.value
            if old_state and new_state != old_state:
                transitions.append((lesson, old_state, new_state))
                if new_state in ("PATTERN", "RULE"):
                    promotions += 1
                elif new_state == "INSTINCT" and old_state == "PATTERN":
                    demotions += 1
                elif new_state in ("KILLED", "UNTESTABLE"):
                    kills += 1

        for lesson, old_state, new_state in transitions:
            if new_state in ("PATTERN", "RULE"):
                try:
                    brain.emit("GRADUATION", "end_session", {
                        "lesson": lesson.description[:100], "category": lesson.category,
                        "from_state": old_state, "to_state": new_state,
                        "confidence": lesson.confidence, "fire_count": lesson.fire_count})
                except Exception as e:
                    _log.debug("Graduation emit failed: %s", e)
                # User-facing graduation notification
                try:
                    brain.bus.emit("lesson.graduated", {
                        "category": lesson.category,
                        "description": lesson.description[:100],
                        "old_state": old_state,
                        "new_state": new_state,
                        "fire_count": lesson.fire_count,
                        "confidence": lesson.confidence,
                        "message": _graduation_message(old_state, lesson),
                    })
                except Exception as e:
                    _log.debug("lesson.graduated emit failed: %s", e)

        # Persist lineage (table created by _migrations.py)
        if transitions and brain.db_path.is_file():
            try:
                from datetime import UTC, datetime

                from gradata._db import get_connection
                now = datetime.now(UTC).isoformat()
                with get_connection(brain.db_path) as conn:
                    for lesson, old_state, new_state in transitions:
                        conn.execute(
                            "INSERT INTO lesson_transitions "
                            "(lesson_desc, category, old_state, new_state, confidence, "
                            "fire_count, session, transitioned_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (lesson.description[:100], lesson.category, old_state, new_state,
                             lesson.confidence, lesson.fire_count, None, now))
            except Exception as e:
                _log.debug("Lineage logging failed: %s", e)

            # Write rule provenance for promotions to PATTERN or RULE
            try:
                from datetime import UTC, datetime

                from gradata.audit import write_provenance
                from gradata.inspection import _make_rule_id
                now_prov = datetime.now(UTC).isoformat()
                for lesson, _old_state, new_state in transitions:
                    if new_state in ("PATTERN", "RULE"):
                        rid = _make_rule_id(lesson)
                        if lesson.correction_event_ids:
                            for eid in lesson.correction_event_ids:
                                write_provenance(
                                    brain.db_path,
                                    rule_id=rid,
                                    correction_event_id=eid,
                                    session=brain.session,
                                    timestamp=now_prov,
                                    user_context=session_type,
                                )
                        else:
                            # Still record provenance even without event IDs
                            write_provenance(
                                brain.db_path,
                                rule_id=rid,
                                correction_event_id=None,
                                session=brain.session,
                                timestamp=now_prov,
                                user_context=session_type,
                            )
            except Exception as e:
                _log.debug("Provenance logging failed: %s", e)

        all_lessons = active + graduated
        from gradata._db import write_lessons_safe
        if all_lessons:  # guard against wiping lessons file when all lessons are killed
            write_lessons_safe(lessons_path, format_lessons(all_lessons))

        # Archive graduated RULE lessons
        new_rules = [l for l in graduated if l.state.value == "RULE"
                     and before_states.get(_lesson_key(l)) != "RULE"]
        archive_path = lessons_path.parent / "lessons-archive.md"
        if new_rules and archive_path.parent.is_dir():
            from datetime import date
            archive_text = archive_path.read_text(encoding="utf-8") if archive_path.exists() else "# Lessons Archive"
            archive_lines = [archive_text.rstrip(), f"\n## Graduated {date.today().isoformat()} (auto)"]
            for r in new_rules:
                archive_lines.append(
                    f"[{r.date}] {r.category}: {r.description} → Auto-graduated (confidence {r.confidence:.2f})")
            archive_path.write_text("\n".join(archive_lines) + "\n", encoding="utf-8")

        # Detect session number early so meta-rules and events use the real value
        current_session = brain.session

        # Meta-rule discovery
        meta_rules_discovered = 0
        if not skip_meta_rules:
            try:
                from gradata.enhancements.meta_rules import refresh_meta_rules
                from gradata.enhancements.meta_rules_storage import load_meta_rules, save_meta_rules
                existing_metas = load_meta_rules(brain.db_path)
                llm_key = getattr(brain, '_llm_key', None)
                new_metas = refresh_meta_rules(
                    all_lessons, existing_metas, session_corrections or [],
                    current_session=current_session,
                    **({'api_key': llm_key} if llm_key else {}))
                if new_metas:
                    if any(l.parent_meta_rule_id for l in all_lessons):
                        from gradata.enhancements.self_improvement import propagate_confidence
                        propagate_confidence(all_lessons, new_metas)
                        # Re-write lessons to persist propagated confidence
                        if all_lessons:
                            write_lessons_safe(lessons_path, format_lessons(all_lessons))
                    save_meta_rules(brain.db_path, new_metas)
                    # Count genuinely new meta-rules by ID, not list length.
                    # Length comparison hides new discoveries when invalidations
                    # reduce the total below the previous count.
                    existing_ids = {m.id for m in existing_metas}
                    meta_rules_discovered = sum(1 for m in new_metas if m.id not in existing_ids)
                    if meta_rules_discovered > 0:
                        _log.info("Meta-rules: %d new (%d total)", meta_rules_discovered, len(new_metas))
                        for meta in new_metas:
                            if meta.id not in existing_ids:
                                try:
                                    brain.bus.emit("meta_rule.created", {
                                        "id": meta.id,
                                        "principle": meta.principle,
                                        "description": meta.principle,
                                        "source_categories": getattr(meta, "source_categories", []),
                                        "confidence": getattr(meta, "confidence", 0.0),
                                        "session": current_session,
                                    })
                                except Exception as e:
                                    _log.debug("Meta-rule event emit failed: %s", e)
            except ImportError as e:
                _log.warning("Meta-rules unavailable: %s", e)
            except Exception as e:
                _log.warning("Meta-rule discovery failed: %s", e)

        # Build graduated_rules detail list from transitions
        from gradata.inspection import _make_rule_id
        graduated_rules = []
        for l, old_s, new_s in transitions:
            if new_s in ("PATTERN", "RULE"):
                graduated_rules.append({
                    "rule_id": _make_rule_id(l),
                    "category": l.category,
                    "description": l.description[:100],
                    "old_state": old_s,
                    "new_state": new_s,
                    "confidence": l.confidence,
                })

        result = {
            "session": current_session,
            "total_lessons": len(all_lessons), "active": len(active),
            "graduated": len(graduated), "promotions": promotions,
            "demotions": demotions, "kills": kills,
            "new_rules": [l.description[:60] for l in new_rules] if new_rules else [],
            "graduated_rules": graduated_rules,
            "meta_rules_discovered": meta_rules_discovered}

        # Session boundary marker for dashboard queries
        try:
            brain.emit("SESSION_END", "brain.end_session", {
                "session": current_session,
                "total_lessons": len(all_lessons),
                "promotions": promotions, "demotions": demotions,
                "graduated_rules": len(new_rules),
            }, session=current_session)
        except Exception as e:
            _log.warning("SESSION_END emit failed: %s", e)

        if promotions or demotions or kills:
            _log.info("Graduation sweep: %d promotions, %d demotions, %d kills",
                      promotions, demotions, kills)
        brain.bus.emit("session.ended", {
            "session_number": brain.session,
            "stats": result,
        })

        return result

    except Exception as e:
        _log.warning("Graduation sweep failed: %s", e)
        return {"error": str(e)}


# ── auto_evolve() ──────────────────────────────────────────────────────

def brain_auto_evolve(
    brain: Brain, output: str, *, task: str = "", agent_type: str = "",
    evaluator: Callable | None = None, dimensions: list | None = None,
    threshold: float = 7.0,
) -> dict:
    """Evaluate output and auto-generate corrections for failed dimensions."""
    from gradata.contrib.patterns.evaluator import QUALITY_DIMENSIONS, default_evaluator, evaluate

    dims = dimensions or QUALITY_DIMENSIONS
    eval_fn = evaluator or default_evaluator
    result = evaluate(output=output, evaluator=eval_fn, dimensions=dims)

    corrections = []
    for dim_name, score in result.scores.items():
        if score < threshold:
            feedback = result.feedback.get(dim_name, "")
            cat = _DIMENSION_CATEGORY_MAP.get(dim_name.lower(), "PROCESS")
            correction_desc = f"[AUTO] {dim_name} scored {score:.1f}/{threshold:.1f}: {feedback}"
            try:
                brain.correct(draft=output[:2000], final=correction_desc[:2000],
                              category=cat, agent_type=agent_type or "auto-evolve",
                              context={"task": task, "auto_evolve": True})
                corrections.append({"dimension": dim_name, "score": score,
                                    "category": cat, "feedback": feedback[:200]})
            except Exception as e:
                _log.warning("Auto-evolve correction failed for %s: %s", dim_name, e)

    if corrections:
        _log.info("auto_evolve: %d corrections from %d dimensions (agent=%s)",
                  len(corrections), len(dims), agent_type or "auto")

    return {"scores": result.scores, "average": result.average, "verdict": result.verdict,
            "corrections_generated": len(corrections), "corrections": corrections,
            "threshold": threshold}


# ── detect_implicit_feedback() ─────────────────────────────────────────

def brain_detect_implicit_feedback(
    brain: Brain, user_message: str, *, session: int | None = None,
) -> dict:
    """Detect implicit behavioral feedback in user prompts."""
    signals = []
    text = user_message.lower()

    # Use word-boundary check to reduce false positives from substring
    # matching (e.g. "not inaccurate" matching "not accurate").
    def _phrase_match(phrase: str) -> bool:
        idx = text.find(phrase)
        if idx < 0:
            return False
        # Check left boundary (start of string or non-alpha)
        if idx > 0 and text[idx - 1].isalpha():
            return False
        # Check right boundary (end of string or non-alpha)
        end = idx + len(phrase)
        return not (end < len(text) and text[end].isalpha())

    for marker in ["are you sure", "that's wrong", "that's not right", "not accurate",
                    "no, not that", "no don't", "stop doing", "why did you", "why didn't you"]:
        if _phrase_match(marker):
            signals.append({"type": "pushback", "marker": marker})
    for marker in ["make sure", "don't forget", "remember to", "you should always",
                    "i already told", "i just said", "as i mentioned", "like i said"]:
        if _phrase_match(marker):
            signals.append({"type": "reminder", "marker": marker})
    for marker in ["what about", "you forgot", "you missed", "you skipped",
                    "you ignored", "you dropped", "did you check", "did you verify"]:
        if _phrase_match(marker):
            signals.append({"type": "gap", "marker": marker})
    for marker in ["are we sure", "is that right", "is that correct",
                    "won't that", "won't people", "i feel like"]:
        if _phrase_match(marker):
            signals.append({"type": "challenge", "marker": marker})

    has_feedback = len(signals) > 0
    event = None
    if has_feedback:
        event = brain.emit("IMPLICIT_FEEDBACK", "brain.detect_implicit_feedback",
                           {"signals": [s["type"] for s in signals],
                            "markers": [s["marker"] for s in signals],
                            "snippet": user_message[:200]},
                           tags=[f"signal:{s['type']}" for s in signals], session=session)

    return {"signals": signals, "has_feedback": has_feedback, "event": event}


# ── Export helpers ─────────────────────────────────────────────────────

def brain_export_rules(brain: Brain, *, min_state: str = "PATTERN", skill_name: str = "") -> str:
    """Export graduated brain rules as OpenSpace-compatible SKILL.md."""
    try:
        from gradata.enhancements.self_improvement import parse_lessons
    except ImportError:
        return ""

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return ""

    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    qualified = _filter_lessons_by_state(lessons, min_state)
    qualified.sort(key=lambda l: (-_STATE_RANK.get(l.state.value, 0), -l.confidence))
    if not qualified:
        return ""

    domain = "general"
    if brain.manifest_path.is_file():
        import json
        try:
            manifest = json.loads(brain.manifest_path.read_text(encoding="utf-8"))
            domain = manifest.get("metadata", {}).get("domain", "general")
        except Exception:
            pass

    if not skill_name:
        skill_name = f"gradata-{domain.lower().replace(' ', '-')}-rules"
    # agentskills.io spec: lowercase a-z, 0-9, hyphens only, no consecutive hyphens
    skill_name = re.sub(r"[^a-z0-9\-]", "-", skill_name.lower())
    skill_name = re.sub(r"-{2,}", "-", skill_name).strip("-")

    by_category: dict[str, list] = {}
    for l in qualified:
        by_category.setdefault(l.category, []).append(l)

    categories_str = ", ".join(sorted(by_category.keys())).lower()
    lines = [
        "---", f"name: {skill_name}",
        f"description: Behavioral rules for {domain} tasks covering {categories_str}. "
        f"Graduated from {len(qualified)} corrections via Gradata.",
        "license: AGPL-3.0",
        "compatibility: Requires Python 3.11+ and gradata SDK",
        "metadata:",
        "  author: gradata",
        '  version: "1.0"',
        f"  domain: {domain}",
        f"  rules-count: \"{len(qualified)}\"",
        "---", "", f"# {skill_name.replace('-', ' ').title()}", "",
        "## Purpose", "",
        f"Behavioral rules adapted from human corrections in the {domain} domain.",
        "Apply these rules to avoid repeating past mistakes.", "",
        "## When to Apply", "",
        f"- Any {domain} task involving: {categories_str}",
        f"- {len(qualified)} rules across {len(by_category)} categories", "",
        "## Rules", ""]

    for cat, cat_lessons in sorted(by_category.items()):
        lines.append(f"### {cat}")
        lines.append("")
        for i, l in enumerate(cat_lessons, 1):
            lines.append(f"{i}. **[{l.state.value}:{int(l.confidence * 100)}%]** {l.description}")
            if l.example_draft and l.example_corrected:
                lines.append(f"   - Before: {l.example_draft}")
                lines.append(f"   - After: {l.example_corrected}")
        lines.append("")

    top_rules = qualified[:5]
    if top_rules:
        lines.extend(["## Guidelines", ""])
        for i, l in enumerate(top_rules, 1):
            lines.append(f"{i}. {l.category}: {l.description}")
        lines.append("")

    lines.extend(["## Provenance", "",
                   "- Source: Gradata correction-based procedural memory",
                   f"- Domain: {domain}", f"- Rules exported: {len(qualified)}",
                   f"- Categories: {len(by_category)}", f"- Min graduation tier: {min_state}", ""])
    return "\n".join(lines)


def brain_export_rules_json(brain: Brain, *, min_state: str = "PATTERN") -> list[dict]:
    """Export graduated rules as a flat, sorted JSON array."""
    try:
        from gradata.enhancements.self_improvement import parse_lessons
    except ImportError:
        return []
    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return []
    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    qualified = _filter_lessons_by_state(lessons, min_state)
    qualified.sort(key=lambda l: (l.category, l.description))
    return [{"category": l.category, "description": l.description,
             "state": l.state.value, "confidence": round(l.confidence, 2),
             "fire_count": l.fire_count, "date": l.date} for l in qualified]


def brain_export_skill(brain: Brain, *, output_dir: str | None = None,
                       min_state: str = "PATTERN", skill_name: str = "") -> Path:
    """Export graduated rules as a full skill directory."""
    import hashlib
    import json
    from datetime import UTC, datetime
    from pathlib import Path

    content = brain_export_rules(brain, min_state=min_state, skill_name=skill_name)
    if not content:
        raise ValueError("No qualified rules to export. Train the brain first.")

    for line in content.splitlines():
        if line.startswith("name:"):
            skill_name = line.split(":", 1)[1].strip()
            break

    base = Path(output_dir).resolve() if output_dir else brain.dir / "skills"
    skill_dir = base / skill_name  # skill_name already sanitized by brain_export_rules
    skill_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    brain_hash = hashlib.sha256(brain.dir.name.encode() + skill_name.encode()).hexdigest()[:8]
    skill_id = f"{skill_name}__imp_{brain_hash}"
    (skill_dir / ".skill_id").write_text(skill_id, encoding="utf-8")

    provenance = {"source": "gradata", "skill_id": skill_id,
                  "brain_name": brain.dir.name, "exported_at": datetime.now(UTC).isoformat(),
                  "min_state": min_state}
    if brain.manifest_path.is_file():
        try:
            manifest = json.loads(brain.manifest_path.read_text(encoding="utf-8"))
            provenance["domain"] = manifest.get("metadata", {}).get("domain", "")
            provenance["sessions_trained"] = manifest.get("metadata", {}).get("sessions_trained", 0)
        except Exception:
            pass
    (skill_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return skill_dir


def brain_export_skills(brain: Brain, *, output_dir: str | None = None,
                        min_state: str = "PATTERN") -> list[str]:
    """Export graduated rules as per-category SKILL.md files."""
    from collections import defaultdict
    from pathlib import Path

    rules = brain_export_rules_json(brain, min_state=min_state)
    if not rules:
        return []

    by_category: dict[str, list[dict]] = defaultdict(list)
    for rule in rules:
        by_category[rule["category"]].append(rule)

    domain = "general"
    try:
        if hasattr(brain, "manifest_path") and brain.manifest_path.is_file():
            import json
            manifest = json.loads(brain.manifest_path.read_text(encoding="utf-8"))
            domain = manifest.get("metadata", {}).get("domain", "general").lower()
    except Exception:
        pass

    base = Path(output_dir).resolve() if output_dir else brain.dir / "skills"
    created = []
    for cat, cat_rules in sorted(by_category.items()):
        slug = re.sub(r"[^\w\-]", "_", cat.lower())
        skill_dir = base / f"gradata-{slug}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        lines = ["---", f'name: "gradata-{domain}-{slug}"',
                  f'description: "Behavioral rules for {cat} from {len(cat_rules)} corrections"',
                  f"tags: [{domain}, {slug}, gradata]", "source: gradata",
                  "compatible_with: [hermes, mindstudio, openspace]",
                  "---", "", f"# {cat} Rules ({domain.title()})", ""]
        for i, rule in enumerate(cat_rules, 1):
            lines.append(f"{i}. [{rule['state']}:{rule['confidence']:.2f}] {rule['description']}")
        lines.append("")
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text("\n".join(lines), encoding="utf-8")
        created.append(str(skill_path))
    return created


# ── convergence() ─────────────────────────────────────────────────────

def _mann_kendall(data: list[int] | list[float]) -> tuple[str, float]:
    """Mann-Kendall trend test — delegates to _stats.trend_analysis().

    Returns (trend, p_value) where trend is "decreasing", "increasing", or "no_trend".
    """
    if len(data) < 3:
        return "no_trend", 1.0

    from gradata._stats import trend_analysis
    slope, p_value = trend_analysis([float(x) for x in data])

    trend = ("decreasing" if slope < 0 else "increasing") if p_value < 0.05 else "no_trend"

    return trend, round(p_value, 4)


def brain_convergence(brain: Brain) -> dict:
    """Compute corrections-per-session convergence data.

    Uses Mann-Kendall trend test for statistical rigor.
    Includes per-category breakdown.

    Returns dict with:
        sessions: list of session numbers
        corrections_per_session: list of correction counts per session
        trend: "converging" | "converged" | "diverging" | "insufficient_data"
        p_value: float (Mann-Kendall p-value, lower = stronger trend)
        by_category: dict of category -> {corrections_per_session, trend}
        total_corrections: int
        total_sessions: int
    """
    empty = {"sessions": [], "corrections_per_session": [], "trend": "insufficient_data",
             "p_value": 1.0, "changepoints": [], "by_category": {},
             "total_corrections": 0, "total_sessions": 0,
             "edit_distance_per_session": [], "edit_distance_trend": "insufficient_data"}

    try:
        from gradata._db import get_connection
        with get_connection(brain.db_path) as conn:
            rows = conn.execute(
                "SELECT session, COUNT(*) as cnt FROM events "
                "WHERE type = 'CORRECTION' AND session IS NOT NULL AND session > 0 "
                "GROUP BY session ORDER BY session"
            ).fetchall()

            # Per-category counts pushed to SQL (avoids fetching all JSON blobs)
            cat_rows = conn.execute(
                "SELECT session, json_extract(data_json, '$.category') as cat, COUNT(*) as cnt "
                "FROM events "
                "WHERE type = 'CORRECTION' AND session IS NOT NULL AND session > 0 "
                "GROUP BY session, cat ORDER BY session"
            ).fetchall()

            ed_rows = conn.execute(
                "SELECT session, AVG(json_extract(data_json, '$.edit_distance')) as avg_ed "
                "FROM events "
                "WHERE type = 'CORRECTION' AND session IS NOT NULL AND session > 0 "
                "AND json_extract(data_json, '$.edit_distance') IS NOT NULL "
                "GROUP BY session ORDER BY session"
            ).fetchall()
    except Exception:
        return empty

    if not rows:
        return empty

    sessions = [r[0] for r in rows]
    counts = [r[1] for r in rows]

    # Mann-Kendall trend test
    mk_trend, p_value = _mann_kendall(counts)
    if mk_trend == "decreasing":
        trend = "converging"
    elif mk_trend == "increasing":
        trend = "diverging"
    elif len(counts) >= 3:
        # No trend detected — distinguish flat/converged from noisy/no-signal.
        # Low coefficient of variation = genuinely stable. High = random noise.
        avg = sum(counts) / len(counts)
        cv = (sum((x - avg) ** 2 for x in counts) / len(counts)) ** 0.5 / avg if avg > 0 else 0
        trend = "converged" if cv < 0.5 else "no_signal"
    else:
        trend = "insufficient_data"

    # Per-category convergence (pre-grouped by SQL)
    cat_by_session: dict[str, dict[int, int]] = {}
    for session, cat, cnt in cat_rows:
        cat = (cat or "UNKNOWN").upper()
        if cat not in cat_by_session:
            cat_by_session[cat] = {}
        cat_by_session[cat][session] = cat_by_session[cat].get(session, 0) + cnt

    by_category: dict[str, dict] = {}
    for cat, session_counts in cat_by_session.items():
        cat_counts = [session_counts.get(s, 0) for s in sessions]
        cat_mk, cat_p = _mann_kendall(cat_counts)
        if cat_mk == "decreasing":
            cat_trend = "converging"
        elif cat_mk == "increasing":
            cat_trend = "diverging"
        elif len(cat_counts) >= 3:
            cat_avg = sum(cat_counts) / len(cat_counts)
            cat_cv = (sum((x - cat_avg) ** 2 for x in cat_counts) / len(cat_counts)) ** 0.5 / cat_avg if cat_avg > 0 else 0
            cat_trend = "converged" if cat_cv < 0.5 else "no_signal"
        else:
            cat_trend = "insufficient_data"
        by_category[cat] = {
            "corrections_per_session": cat_counts,
            "trend": cat_trend,
            "p_value": cat_p,
        }

    # Edit distance trend
    ed_counts = [r[1] for r in ed_rows] if ed_rows else []
    if len(ed_counts) >= 3:
        ed_mk_trend, _ed_p = _mann_kendall(ed_counts)
        ed_trend = "improving" if ed_mk_trend == "decreasing" else (
            "worsening" if ed_mk_trend == "increasing" else "stable")
    else:
        ed_trend = "insufficient_data"

    from gradata._stats import cusum_changepoints
    raw_changepoints = cusum_changepoints(counts)
    changepoint_sessions = [sessions[i] for i in raw_changepoints if i < len(sessions)]

    return {
        "sessions": sessions,
        "corrections_per_session": counts,
        "trend": trend,
        "p_value": p_value,
        "changepoints": changepoint_sessions,
        "by_category": by_category,
        "total_corrections": sum(counts),
        "total_sessions": len(sessions),
        "edit_distance_per_session": [round(r[1], 4) for r in ed_rows] if ed_rows else [],
        "edit_distance_trend": ed_trend,
    }


# ── Efficiency ────────────────────────────────────────────────────────

# Average seconds saved per correction avoided (approximate).
# TODO: query actual severity distribution when real user data exists.
_AVG_SECONDS_PER_CORRECTION = 45


def brain_efficiency(brain: Brain, *, estimate_time: bool = False) -> dict:
    """Quantify effort saved by brain learning.

    Returns effort_ratio (current vs initial correction rate).
    Optional estimate_time adds severity-weighted time estimates (approximate).
    """
    convergence = brain._get_convergence()
    counts = convergence.get("corrections_per_session", [])

    if len(counts) < 3:
        result: dict = {
            "effort_ratio": 1.0,
            "corrections_initial": 0,
            "corrections_recent": 0,
            "total_corrections": convergence.get("total_corrections", 0),
            "total_sessions": convergence.get("total_sessions", 0),
        }
        if estimate_time:
            result["estimated_seconds_saved"] = 0
            result["time_breakdown"] = {}
        return result

    initial = sum(counts[:3]) / 3.0
    recent = sum(counts[-3:]) / 3.0
    effort_ratio = round(recent / initial, 2) if initial > 0 else 1.0

    result = {
        "effort_ratio": effort_ratio,
        "corrections_initial": round(initial, 1),
        "corrections_recent": round(recent, 1),
        "total_corrections": convergence.get("total_corrections", 0),
        "total_sessions": convergence.get("total_sessions", 0),
    }

    if estimate_time:
        corrections_avoided = max(0, (initial - recent) * len(counts))
        avg_severity_weight = _AVG_SECONDS_PER_CORRECTION
        estimated_seconds = int(corrections_avoided * avg_severity_weight)
        result["estimated_seconds_saved"] = estimated_seconds
        result["time_breakdown"] = {
            "corrections_avoided": round(corrections_avoided, 1),
            "avg_seconds_per_correction": avg_severity_weight,
        }

    return result


def brain_prove(brain: Brain) -> dict:
    """Generate statistical proof that this brain improves output quality."""
    convergence = brain._get_convergence()
    efficiency = brain_efficiency(brain)

    # Count graduated rules
    rule_count = 0
    try:
        lessons_path = brain._find_lessons_path()
        if lessons_path and lessons_path.is_file():
            from gradata._types import LessonState
            from gradata.enhancements.self_improvement import parse_lessons
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            rule_count = sum(1 for l in lessons if l.state in (LessonState.PATTERN, LessonState.RULE))
    except Exception:
        pass

    # Determine which categories have converged
    by_cat = convergence.get("by_category", {})
    categories_converged = [cat for cat, data in by_cat.items() if data.get("trend") == "converged"]

    # Find strongest category (lowest p-value with decreasing trend)
    strongest = None
    best_p = 1.0
    for cat, data in by_cat.items():
        if data.get("trend") == "converging" and data.get("p_value", 1.0) < best_p:
            best_p = data["p_value"]
            strongest = cat

    # Determine proof strength
    total_sessions = convergence.get("total_sessions", 0)
    total_corrections = convergence.get("total_corrections", 0)
    trend = convergence.get("trend", "insufficient_data")
    p_value = convergence.get("p_value", 1.0)
    effort_ratio = efficiency.get("effort_ratio", 1.0)

    if total_sessions < 3 or total_corrections < 5:
        confidence_level = "insufficient"
        proven = False
    elif trend == "converging" and p_value < 0.05 and effort_ratio < 0.7:
        confidence_level = "strong"
        proven = True
    elif trend in ("converging", "converged") and effort_ratio < 0.85:
        confidence_level = "moderate"
        proven = True
    elif rule_count >= 3:
        confidence_level = "weak"
        proven = True
    else:
        confidence_level = "insufficient"
        proven = False

    # Generate summary
    if proven and confidence_level == "strong":
        pct = int((1 - effort_ratio) * 100)
        summary = f"Brain reduces correction effort by {pct}% (p={p_value:.3f}, {rule_count} graduated rules, {total_sessions} sessions)"
    elif proven:
        summary = f"Brain shows improvement ({rule_count} rules graduated across {total_sessions} sessions, effort ratio {effort_ratio})"
    else:
        summary = f"Insufficient evidence ({total_sessions} sessions, {total_corrections} corrections, {rule_count} rules)"

    return {
        "proven": proven,
        "confidence_level": confidence_level,
        "evidence": {
            "convergence_trend": trend,
            "p_value": p_value,
            "changepoints": convergence.get("changepoints", []),
            "effort_ratio": effort_ratio,
            "rule_count": rule_count,
            "correction_count": total_corrections,
            "sessions": total_sessions,
            "categories_converged": categories_converged,
            "strongest_category": strongest,
            "edit_distance_trend": convergence.get("edit_distance_trend", "insufficient_data"),
        },
        "summary": summary,
    }


# ── Sharing ──────────────────────────────────────────────────────────


def brain_share(brain: Brain) -> dict:
    """Export graduated rules as a shareable package for team distribution.

    Only exports PATTERN and RULE state lessons — proven behavioral rules
    that have survived the graduation pipeline.
    """
    from datetime import datetime

    from gradata._types import LessonState

    lessons_path = brain._find_lessons_path()
    rules: list[dict] = []
    if lessons_path and lessons_path.is_file():
        from gradata.enhancements.self_improvement import parse_lessons
        all_lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
        for lesson in all_lessons:
            if lesson.state in (LessonState.PATTERN, LessonState.RULE):
                rules.append({
                    "category": lesson.category,
                    "description": lesson.description,
                    "confidence": lesson.confidence,
                    "state": lesson.state.value,
                    "fire_count": lesson.fire_count,
                    "correction_type": (
                        lesson.correction_type.value
                        if hasattr(lesson.correction_type, "value")
                        else str(lesson.correction_type)
                    ),
                })

    proof: dict = {}
    with contextlib.suppress(Exception):
        proof = brain_prove(brain)

    return {
        "brain_id": str(brain.dir),
        "exported_at": datetime.now(UTC).isoformat(),
        "rules": rules,
        "rule_count": len(rules),
        "proof": proof,
    }


def brain_absorb(brain: Brain, package: dict) -> dict:
    """Import shared rules into this brain.

    Imported rules enter as INSTINCT with initial confidence (0.40),
    not at their original confidence — the recipient brain must
    validate them through its own correction cycle.

    Skips rules that are >0.6 similar to existing lessons (duplicates).
    """
    from datetime import date as _date

    from gradata._types import CorrectionType, Lesson, LessonState
    from gradata.enhancements.self_improvement import format_lessons, parse_lessons
    from gradata.enhancements.similarity import best_similarity

    INITIAL_CONFIDENCE = 0.40

    lessons_path = brain._find_lessons_path(create=True)
    if not lessons_path:
        return {"absorbed": 0, "skipped": 0, "error": "No lessons path"}

    existing_text = ""
    if lessons_path.is_file():
        existing_text = lessons_path.read_text(encoding="utf-8")
    existing = parse_lessons(existing_text) if existing_text else []

    absorbed = 0
    skipped = 0

    for rule in package.get("rules", []):
        desc = rule.get("description", "")
        cat = rule.get("category", "UNKNOWN")

        # Check for duplicates against same-category lessons
        is_duplicate = False
        for existing_l in existing:
            if existing_l.category == cat:
                sim = best_similarity(desc, existing_l.description)
                if sim >= 0.6:
                    is_duplicate = True
                    break

        if is_duplicate:
            skipped += 1
            continue

        # Import as INSTINCT — recipient must validate
        correction_type_str = rule.get("correction_type", "behavioral")
        try:
            ct = CorrectionType(correction_type_str)
        except (ValueError, KeyError):
            ct = CorrectionType.BEHAVIORAL

        new_lesson = Lesson(
            date=_date.today().isoformat(),
            state=LessonState.INSTINCT,
            confidence=INITIAL_CONFIDENCE,
            category=cat,
            description=desc,
            correction_type=ct,
            agent_type="shared",
        )
        existing.append(new_lesson)
        absorbed += 1

    # Write back
    lessons_path.write_text(format_lessons(existing), encoding="utf-8")

    return {
        "absorbed": absorbed,
        "skipped": skipped,
        "source": package.get("brain_id", "unknown"),
        "total_rules_in_package": package.get(
            "rule_count", len(package.get("rules", []))
        ),
    }