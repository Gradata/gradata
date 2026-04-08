"""Brain inspection mixin — rule inspection, approval, and export methods.

Extracted from Brain to keep brain.py under 500 lines.  All methods access
the same attributes (self.db_path, self.dir, self.ctx, self.bus, self.emit,
self._find_lessons_path) so they work transparently via multiple inheritance.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class BrainInspectionMixin:
    """Mixin providing rule inspection, export, and batch approval methods.

    Must be mixed into Brain which provides: db_path, dir, ctx, bus,
    _find_lessons_path(), emit().
    """

    # Declared for Pyright — actual values come from Brain.__init__
    db_path: Path
    dir: Path
    ctx: Any
    bus: Any

    def _find_lessons_path(self) -> Path | None: ...
    def emit(self, event_type: str, source: str, data: dict | None = None,
             tags: list | None = None, session: int | None = None) -> dict: ...

    # ── Rule Inspection API ────────────────────────────────────────────

    def rules(self, *, include_all: bool = False, category: str | None = None) -> list[dict]:
        """List graduated brain rules. See gradata.inspection.list_rules."""
        from gradata.inspection import list_rules
        return list_rules(db_path=self.db_path,
                          lessons_path=self._find_lessons_path() or self.dir / "lessons.md",
                          include_all=include_all, category=category)

    def explain(self, rule_id: str) -> dict:
        """Trace a rule to its source corrections. See gradata.inspection.explain_rule."""
        from gradata.inspection import explain_rule
        return explain_rule(db_path=self.db_path,
                            events_path=self.ctx.events_jsonl if hasattr(self.ctx, "events_jsonl") else self.dir / "events.jsonl",
                            rule_id=rule_id,
                            lessons_path=self._find_lessons_path() or self.dir / "lessons.md")

    def trace(self, rule_id: str) -> dict:
        """Trace a rule's full provenance chain. See gradata.audit.trace_rule."""
        from gradata.audit import trace_rule
        return trace_rule(
            db_path=self.db_path,
            events_path=self.ctx.events_jsonl if hasattr(self.ctx, "events_jsonl") else self.dir / "events.jsonl",
            lessons_path=self._find_lessons_path() or self.dir / "lessons.md",
            rule_id=rule_id,
        )

    def export_data(self, *, output_format: str = "json") -> str:
        """Export rules as JSON or YAML. See gradata.inspection.export_rules."""
        from gradata.inspection import export_rules
        return export_rules(db_path=self.db_path,
                            lessons_path=self._find_lessons_path() or self.dir / "lessons.md",
                            output_format=output_format)

    # ── Batch Approval at Session End ─────────────────────────────────

    def pending_promotions(self) -> list[dict]:
        """List rules that have graduated (PATTERN or RULE state).

        Silent during work — call at session end to review what graduated.
        Returns list of rule dicts with id, category, state, confidence, etc.
        """
        from gradata.inspection import list_rules
        return list_rules(
            db_path=self.db_path,
            lessons_path=self._find_lessons_path() or self.dir / "lessons.md",
        )

    def approve_promotion(self, rule_id: str) -> dict:
        """Explicitly endorse a graduated rule — persists reviewed flag to disk.

        Args:
            rule_id: Stable rule ID from pending_promotions().

        Returns:
            {"approved": True} on success, {"error": "..."} if not found.
        """
        from gradata._db import write_lessons_safe
        from gradata.enhancements.self_improvement import format_lessons
        from gradata.inspection import _load_lessons_from_path, _make_rule_id

        lessons_path = self._find_lessons_path() or self.dir / "lessons.md"
        lessons = _load_lessons_from_path(lessons_path)
        target = None
        for lesson in lessons:
            if _make_rule_id(lesson) == rule_id:
                target = lesson
                break
        if target is None:
            return {"error": f"Rule not found: {rule_id}"}

        target.pending_approval = False
        write_lessons_safe(lessons_path, format_lessons(lessons))

        try:
            self.emit("PROMOTION_APPROVED", "brain.approve_promotion", {
                "rule_id": rule_id,
                "category": target.category,
                "description": target.description[:200],
                "state": target.state.value,
                "confidence": target.confidence,
            })
        except Exception as e:
            logger.debug("promotion.approved emit failed: %s", e)

        return {"approved": True}

    def reject_promotion(self, rule_id: str) -> dict:
        """Reject a graduated rule — demotes back to INSTINCT with confidence 0.40.

        Rewrites lessons file with the demoted lesson. Emits 'promotion.rejected'.

        Args:
            rule_id: Stable rule ID from pending_promotions().

        Returns:
            {"rejected": True, "demoted_from": old_state} on success,
            {"error": "..."} if not found.
        """
        from gradata._db import write_lessons_safe
        from gradata._types import LessonState
        from gradata.enhancements.self_improvement import format_lessons
        from gradata.inspection import _load_lessons_from_path, _make_rule_id

        lessons_path = self._find_lessons_path() or self.dir / "lessons.md"
        lessons = _load_lessons_from_path(lessons_path)
        target = None
        for lesson in lessons:
            if _make_rule_id(lesson) == rule_id:
                target = lesson
                break
        if target is None:
            return {"error": f"Rule not found: {rule_id}"}

        old_state = target.state.value
        target.state = LessonState.INSTINCT
        target.confidence = 0.40

        write_lessons_safe(lessons_path, format_lessons(lessons))

        try:
            self.emit("PROMOTION_REJECTED", "brain.reject_promotion", {
                "rule_id": rule_id,
                "category": target.category,
                "description": target.description[:200],
                "demoted_from": old_state,
                "new_state": "INSTINCT",
                "confidence": 0.40,
            })
        except Exception as e:
            logger.debug("promotion.rejected emit failed: %s", e)

        return {"rejected": True, "demoted_from": old_state}