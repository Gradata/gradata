"""Brain mixin — Core Learning Loop methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainLearningMixin:
    """Correction capture, output logging, rule application, and graduation for Brain."""

    # ── Core Learning Loop (correction capture) ────────────────────────

    def correct(
        self,
        draft: str,
        final: str,
        category: str | None = None,
        context: dict | None = None,
        session: int | None = None,
    ) -> dict:
        """Record a correction: the user edited a draft into a final version.

        This is the primary learning signal. The founding docs call it the
        biggest technical risk — how corrections get INTO the system.

        This method:
        1. Computes diff (edit distance + severity)
        2. Classifies edits (tone/content/structure/factual/style)
        3. Emits a CORRECTION event with full metadata
        4. Returns the analysis for immediate use

        Args:
            draft: The AI-generated text before user editing.
            final: The text after user editing.
            category: Optional override for correction category.
            context: Optional session context dict for scope building.
            session: Session number (auto-detected if omitted).
        """
        import logging
        logger = logging.getLogger("gradata")

        # ── Input validation ──────────────────────────────────────────
        if not draft and not final:
            raise ValueError("Both draft and final are empty — nothing to correct.")
        if draft == final:
            raise ValueError("draft and final are identical — no correction detected.")
        max_input = 100_000
        if len(draft) + len(final) > max_input:
            raise ValueError(
                f"Combined input length ({len(draft) + len(final)}) exceeds "
                f"limit ({max_input}). Truncate inputs before calling correct()."
            )
        if session is not None and (not isinstance(session, int) or session < 1):
            raise ValueError(f"session must be a positive integer, got {session!r}")

        # Route to cloud if connected, otherwise run locally
        if self._cloud and self._cloud.connected:
            try:
                return self._cloud.correct(draft, final, category, context, session)
            except Exception as e:
                logger.warning("Cloud correct() failed, falling back to local: %s", e)
                self._cloud.connected = False

        # Try full enhancement pipeline (diff + classify + extract)
        # Prefer gradata_cloud (proprietary), fall back to enhancements/ (bundled)
        try:
            from gradata.enhancements.diff_engine import compute_diff
            try:
                from gradata_cloud.graduation.edit_classifier import classify_edits, summarize_edits
            except ImportError:
                from gradata.enhancements.edit_classifier import classify_edits, summarize_edits
        except ImportError:
            # Enhancements not installed — basic correction logging only
            data = {
                "draft_text": draft[:2000],
                "final_text": final[:2000],
                "edit_distance": 0.0,
                "severity": "unknown",
                "outcome": "unknown",
                "major_edit": False,
                "category": category or "UNKNOWN",
                "summary": "",
                "classifications": [],
            }
            tags = [f"category:{category or 'UNKNOWN'}"]
            return self.emit("CORRECTION", "brain.correct", data, tags, session)

        from gradata._scope import build_scope

        diff = compute_diff(draft, final)
        classifications = classify_edits(diff)
        summary = summarize_edits(classifications)

        # Auto-detect category from classifications if not provided
        if not category and classifications:
            category = classifications[0].category.upper()

        # Build scope from context (Engineering Spec: every correction is scoped)
        scope_data = {}
        if context:
            from gradata._scope import scope_to_dict
            scope_data = scope_to_dict(build_scope(context))

        data = {
            # Engineering Spec fields: draft_text, final_text, edit_distance, outcome, major_edit
            "draft_text": draft[:2000],
            "final_text": final[:2000],
            "edit_distance": diff.edit_distance,
            "severity": diff.severity,
            "outcome": diff.severity,  # as-is / minor / moderate / major / discarded
            "major_edit": diff.severity in ("major", "discarded"),
            "category": category or "UNKNOWN",
            "summary": summary,
            "classifications": [
                {"category": c.category, "severity": c.severity, "description": c.description}
                for c in classifications
            ],
            "lines_added": diff.summary_stats.get("lines_added", 0),
            "lines_removed": diff.summary_stats.get("lines_removed", 0),
        }
        if scope_data:
            data["scope"] = scope_data

        tags = [f"category:{category or 'UNKNOWN'}", f"severity:{diff.severity}"]
        if diff.severity in ("major", "discarded"):
            tags.append("major_edit:true")

        event = self.emit("CORRECTION", "brain.correct", data, tags, session)
        event["diff"] = diff
        event["classifications"] = classifications

        # Auto-extract patterns from classifications (step 3 of core loop)
        patterns = []
        try:
            try:
                from gradata_cloud.graduation.pattern_extractor import extract_patterns
            except ImportError:
                from gradata.enhancements.pattern_extractor import extract_patterns
            scope_obj = build_scope(context) if context else None
            patterns = extract_patterns(classifications, scope=scope_obj)
            if patterns:
                event["patterns_extracted"] = len(patterns)
                logger.debug("Extracted %d patterns from correction", len(patterns))
        except Exception as e:
            logger.warning("Pattern extraction failed: %s", e)

        # Step 3b: CLOSE THE LOOP — every correction becomes a lesson candidate
        # This is the critical link: correction → lesson in lessons.md → rules
        # Key insight: don't wait for pattern clustering. Each correction with
        # sufficient severity is a lesson candidate. Graduation handles quality.
        try:
            from datetime import date as _date
            from gradata._types import Lesson, LessonState, CorrectionType
            try:
                from gradata_cloud.graduation.self_improvement import (
                    parse_lessons, format_lessons, update_confidence,
                    INITIAL_CONFIDENCE,
                )
            except ImportError:
                from gradata.enhancements.self_improvement import (
                    parse_lessons, format_lessons, update_confidence,
                    INITIAL_CONFIDENCE,
                )

            # Only create lessons for meaningful corrections (not trivial typos)
            if diff.severity not in ("as-is",):
                lessons_path = self._find_lessons_path(create=True)
                if lessons_path:
                    existing_text = ""
                    if lessons_path.is_file():
                        existing_text = lessons_path.read_text(encoding="utf-8")
                    existing_lessons = parse_lessons(existing_text) if existing_text else []

                    # Build lesson description from the correction
                    cat = (category or "UNKNOWN").upper()
                    desc = summary if summary else f"Corrected {cat.lower()} ({diff.severity})"

                    # Deduplicate: same category + similar description = same lesson
                    existing_keys = {
                        (l.category, l.description[:40]) for l in existing_lessons
                    }
                    key = (cat, desc[:40])

                    if key not in existing_keys:
                        # New lesson — start as INSTINCT
                        new_lesson = Lesson(
                            date=_date.today().isoformat(),
                            state=LessonState.INSTINCT,
                            confidence=INITIAL_CONFIDENCE,
                            category=cat,
                            description=desc,
                        )
                        existing_lessons.append(new_lesson)
                        event["lessons_created"] = 1
                        logger.info("New lesson: [INSTINCT:%.2f] %s: %s",
                                   INITIAL_CONFIDENCE, cat, desc[:60])

                    # Update confidence on ALL lessons based on this correction
                    correction_data = [{
                        "category": cat,
                        "severity_label": diff.severity,
                    }]
                    severity_data = {cat: diff.severity}
                    existing_lessons = update_confidence(
                        existing_lessons,
                        correction_data,
                        severity_data=severity_data,
                    )

                    # Write back
                    lessons_path.write_text(
                        format_lessons(existing_lessons),
                        encoding="utf-8",
                    )
                    if "lessons_created" not in event:
                        event["lessons_updated"] = True

        except Exception as e:
            logger.warning("Lesson creation failed: %s", e)

        # Step 4: Run through the learning pipeline (observe→cluster→discriminate→route→bracket)
        if self._learning_pipeline:
            try:
                task_type = ""
                if context:
                    task_type = context.get("task_type", context.get("task", ""))
                pipeline_result = self._learning_pipeline.process_correction(
                    draft=draft,
                    final=final,
                    severity=diff.severity,
                    category=category or "UNKNOWN",
                    session_id=str(session or ""),
                    task_type=task_type,
                    occurrence_count=1,
                )
                event["pipeline"] = {
                    "stages_completed": pipeline_result.stages_completed,
                    "is_high_value": pipeline_result.is_high_value,
                    "discriminator_confidence": pipeline_result.discriminator_confidence,
                    "recommendation": pipeline_result.discriminator_recommendation,
                    "cluster_id": pipeline_result.cluster_id,
                    "context_bracket": pipeline_result.context_bracket,
                    "memory_type": pipeline_result.memory_type,
                    "processing_time_ms": pipeline_result.processing_time_ms,
                }
                logger.debug(
                    "Pipeline: %d stages, high_value=%s, bracket=%s",
                    len(pipeline_result.stages_completed),
                    pipeline_result.is_high_value,
                    pipeline_result.context_bracket,
                )
            except Exception as e:
                logger.warning("Learning pipeline failed: %s", e)

        return event

    def log_output(
        self,
        text: str,
        output_type: str = "general",
        prompt: str | None = None,
        self_score: float | None = None,
        scope: dict | None = None,
        session: int | None = None,
        rules_applied: list[str] | None = None,
    ) -> dict:
        """Log an AI-generated output for tracking.

        Per Engineering Spec: each output needs prompt, draft_text,
        edit_distance, outcome, major_edit. The draft is captured here;
        edit_distance and outcome are computed when correct() is called.

        Args:
            text: The AI-generated draft text.
            output_type: Type of output (email, research, code, etc).
            prompt: The user prompt that triggered this output.
            self_score: Self-assessment score (0-10). Used for Brier calibration.
            scope: Optional scope dict (domain, task_type, audience, channel, stakes).
            session: Session number (auto-detected if omitted).
            rules_applied: List of rule IDs active when this output was generated.
                Enables external signal → rule attribution for outcome feedback.
        """
        data = {
            "output_type": output_type,
            "output_text": text[:5000],
            "outcome": "pending",        # pending -> accepted / minor / moderate / major / discarded
            "major_edit": False,
            "rules_applied": rules_applied or [],
        }
        if prompt is not None:
            data["prompt"] = prompt[:2000]
        if self_score is not None:
            data["self_score"] = self_score
        if scope is not None:
            data["scope"] = scope

        tags = [f"output:{output_type}"]
        return self.emit("OUTPUT", "brain.log_output", data, tags, session)

    def apply_brain_rules(
        self,
        task: str,
        context: dict | None = None,
    ) -> str:
        """Get applicable brain rules for a task, formatted for prompt injection.

        Args:
            task: Description of the task being performed.
            context: Optional context dict with domain, prospect info, etc.
        """
        import logging
        logger = logging.getLogger("gradata")

        # Route to cloud if connected
        if self._cloud and self._cloud.connected:
            try:
                return self._cloud.apply_rules(task, context)
            except Exception as e:
                logger.warning("Cloud apply_rules() failed, falling back to local: %s", e)
                self._cloud.connected = False

        try:
            try:
                from gradata_cloud.graduation.self_improvement import parse_lessons
            except ImportError:
                from gradata.enhancements.self_improvement import parse_lessons
        except ImportError:
            return ""  # Neither cloud nor enhancements installed — no rules available
        from gradata._scope import build_scope
        from gradata.patterns.rule_engine import apply_rules, format_rules_for_prompt

        from pathlib import Path
        ctx = context or {}
        ctx.setdefault("task", task)
        scope = build_scope(ctx)

        # Load lessons — check env var, brain dir, then parent's .claude/ for compat
        import os
        env_path = os.environ.get("BRAIN_LESSONS_PATH", "")
        lessons_path = None
        if env_path and Path(env_path).is_file():
            lessons_path = Path(env_path)
        elif (self.dir / "lessons.md").is_file():
            lessons_path = self.dir / "lessons.md"
        elif (self.dir.parent / ".claude" / "lessons.md").is_file():
            lessons_path = self.dir.parent / ".claude" / "lessons.md"
        if lessons_path is None:
            return ""

        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
        applied = apply_rules(lessons, scope)
        return format_rules_for_prompt(applied)

    # ── Session-End Graduation (auto-promote survivors) ─────────────────

    def end_session(
        self,
        session_corrections: list[dict] | None = None,
        session_type: str = "full",
    ) -> dict:
        """Run full graduation sweep at end of session.

        This is the auto-promotion mechanism. Every lesson that SURVIVED
        this session (wasn't contradicted) gets a confidence bump. Lessons
        that cross thresholds (0.60 → PATTERN, 0.90 → RULE) get promoted.
        Lessons that hit kill limits get archived.

        Should be called at session end (wrap-up, hook, or manually).

        Args:
            session_corrections: All corrections from this session.
            session_type: "full", "sales", or "systems" for decay scoping.

        Returns:
            Dict with promotion/demotion/kill counts.
        """
        import logging
        logger = logging.getLogger("gradata")

        try:
            try:
                from gradata_cloud.graduation.self_improvement import (
                    parse_lessons, format_lessons, update_confidence, graduate,
                )
            except ImportError:
                from gradata.enhancements.self_improvement import (
                    parse_lessons, format_lessons, update_confidence, graduate,
                )

            lessons_path = self._find_lessons_path()
            if not lessons_path or not lessons_path.is_file():
                return {"error": "no lessons.md found"}

            text = lessons_path.read_text(encoding="utf-8")
            lessons = parse_lessons(text)
            if not lessons:
                return {"lessons": 0, "promotions": 0, "demotions": 0}

            before_states = {l.description[:40]: l.state.value for l in lessons}

            # Run full confidence update with all session corrections
            lessons = update_confidence(
                lessons,
                session_corrections or [],
                session_type=session_type,
            )

            # Run graduation (promote/demote/kill)
            active, graduated = graduate(lessons)

            # Count changes
            promotions = 0
            demotions = 0
            kills = 0
            for l in active + graduated:
                key = l.description[:40]
                old_state = before_states.get(key, "")
                new_state = l.state.value
                if old_state and new_state != old_state:
                    if new_state in ("PATTERN", "RULE"):
                        promotions += 1
                    elif new_state == "INSTINCT" and old_state == "PATTERN":
                        demotions += 1
                    elif new_state in ("KILLED", "UNTESTABLE"):
                        kills += 1

            # Write back
            all_lessons = active + graduated
            lessons_path.write_text(
                format_lessons(all_lessons),
                encoding="utf-8",
            )

            # Archive graduated RULE lessons to lessons-archive.md
            archive_path = lessons_path.parent / "lessons-archive.md"
            new_rules = [l for l in graduated if l.state.value == "RULE"
                        and before_states.get(l.description[:40]) != "RULE"]
            if new_rules and archive_path.exists():
                from datetime import date
                archive_text = archive_path.read_text(encoding="utf-8")
                archive_lines = [archive_text.rstrip()]
                archive_lines.append(f"\n## Graduated {date.today().isoformat()} (auto)")
                for r in new_rules:
                    archive_lines.append(
                        f"[{r.date}] {r.category}: {r.description} → Auto-graduated (confidence {r.confidence:.2f})"
                    )
                archive_path.write_text("\n".join(archive_lines) + "\n", encoding="utf-8")

            result = {
                "total_lessons": len(all_lessons),
                "active": len(active),
                "graduated": len(graduated),
                "promotions": promotions,
                "demotions": demotions,
                "kills": kills,
                "new_rules": [l.description[:60] for l in new_rules] if new_rules else [],
            }

            if promotions or demotions or kills:
                logger.info(
                    "Graduation sweep: %d promotions, %d demotions, %d kills",
                    promotions, demotions, kills,
                )

            return result

        except Exception as e:
            logger.warning("Graduation sweep failed: %s", e)
            return {"error": str(e)}

    # ── Implicit Feedback Detection (novel — neither Mem0 nor Letta has this)

    def detect_implicit_feedback(self, user_message: str, session: int = None) -> dict:
        """Detect implicit behavioral feedback in user prompts.

        The correction pipeline captures explicit draft→final edits. But most
        feedback is implicit: "are you sure?", "what about X?", "make sure you..."
        These signals indicate the AI missed something, forgot something, or
        needs behavioral adjustment.

        This is a novel signal source. No competitor captures it.

        Args:
            user_message: The user's raw prompt text.
            session: Session number (auto-detected if omitted).

        Returns:
            Dict with 'signals' (list of detected signal types),
            'has_feedback' (bool), and 'event' (if feedback was detected).
        """
        signals = []
        text = user_message.lower()

        # Pushback: user is correcting or disagreeing
        pushback_markers = [
            "are you sure", "that's wrong", "that's not right", "not accurate",
            "no, not that", "no don't", "stop doing", "why did you", "why didn't you",
        ]
        for marker in pushback_markers:
            if marker in text:
                signals.append({"type": "pushback", "marker": marker})

        # Reminder: user is repeating an instruction
        reminder_markers = [
            "make sure", "don't forget", "remember to", "you should always",
            "i already told", "i just said", "as i mentioned", "like i said",
        ]
        for marker in reminder_markers:
            if marker in text:
                signals.append({"type": "reminder", "marker": marker})

        # Gap: user is pointing out something missed
        gap_markers = [
            "what about", "you forgot", "you missed", "you skipped",
            "you ignored", "you dropped", "did you check", "did you verify",
        ]
        for marker in gap_markers:
            if marker in text:
                signals.append({"type": "gap", "marker": marker})

        # Challenge: user is questioning quality/completeness
        challenge_markers = [
            "are we sure", "is that right", "is that correct",
            "won't that", "won't people", "i feel like",
        ]
        for marker in challenge_markers:
            if marker in text:
                signals.append({"type": "challenge", "marker": marker})

        has_feedback = len(signals) > 0
        event = None

        if has_feedback:
            event = self.emit(
                "IMPLICIT_FEEDBACK", "brain.detect_implicit_feedback",
                {
                    "signals": [s["type"] for s in signals],
                    "markers": [s["marker"] for s in signals],
                    "snippet": user_message[:200],
                },
                tags=[f"signal:{s['type']}" for s in signals],
                session=session,
            )

        return {
            "signals": signals,
            "has_feedback": has_feedback,
            "event": event,
        }
