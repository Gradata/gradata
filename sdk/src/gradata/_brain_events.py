"""Brain mixin — Events and Facts methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainEventsMixin:
    """Event emission, querying, and fact extraction for Brain."""

    # ── Events ─────────────────────────────────────────────────────────

    def emit(self, event_type: str, source: str, data: dict = None,
             tags: list = None, session: int = None) -> dict:
        """Emit an event to the brain's event log."""
        from gradata._events import emit
        return emit(event_type, source, data or {}, tags or [], session, ctx=self.ctx)

    def query_events(self, event_type: str = None, session: int = None,
                     last_n_sessions: int = None, limit: int = 100) -> list[dict]:
        """Query events from the brain's event log."""
        try:
            from gradata._events import query
            return query(event_type=event_type, session=session,
                         last_n_sessions=last_n_sessions, limit=limit, ctx=self.ctx)
        except ImportError:
            return []

    # ── Facts ──────────────────────────────────────────────────────────

    def get_facts(self, prospect: str = None, fact_type: str = None) -> list[dict]:
        """Query structured facts from the brain."""
        try:
            from gradata._fact_extractor import query_facts
            return query_facts(prospect=prospect, fact_type=fact_type, ctx=self.ctx)
        except ImportError:
            return []

    def extract_facts(self) -> int:
        """Extract structured facts from all prospect files."""
        try:
            from gradata._fact_extractor import extract_all, store_facts
            facts = extract_all(ctx=self.ctx)
            store_facts(facts, ctx=self.ctx)
            return len(facts)
        except ImportError:
            return 0

    # ── Passive Memory Extraction (stolen from Mem0) ────────────────────

    def observe(self, messages: list[dict], user_id: str = "default") -> list[dict]:
        """Extract facts from a conversation without requiring corrections.

        Stolen from Mem0's passive extraction pipeline. Captures preferences,
        entities, relationships, and action items from any conversation.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            user_id: User identifier for scoped fact storage.

        Returns:
            List of reconcile action dicts (add/update/invalidate/skip).
        """
        import logging
        logger = logging.getLogger("gradata")

        try:
            try:
                from gradata_cloud.scoring.memory_extraction import MemoryExtractor
            except ImportError:
                from gradata.enhancements.memory_extraction import MemoryExtractor
        except ImportError:
            return []

        extractor = MemoryExtractor()
        candidates = extractor.extract(messages)

        if not candidates:
            return []

        # Get existing facts for reconciliation
        existing = self.get_facts()
        actions = extractor.reconcile(candidates, existing)

        # Execute actions
        results = []
        for action in actions:
            if action.op == "add":
                event = self.emit(
                    "FACT_EXTRACTED", "brain.observe",
                    {
                        "content": action.fact.content,
                        "fact_type": action.fact.fact_type,
                        "confidence": action.fact.confidence,
                        "source_role": action.fact.source_role,
                        "entities": action.fact.entities,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "add", "fact": action.fact.content, "event": event})
            elif action.op == "invalidate":
                event = self.emit(
                    "FACT_INVALIDATED", "brain.observe",
                    {
                        "target_id": action.target_id,
                        "reason": action.reason,
                        "superseded_by": action.fact.content,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "invalidate", "target": action.target_id, "event": event})
            elif action.op == "update":
                event = self.emit(
                    "FACT_UPDATED", "brain.observe",
                    {
                        "target_id": action.target_id,
                        "new_content": action.fact.content,
                        "user_id": user_id,
                    },
                )
                results.append({"op": "update", "target": action.target_id, "event": event})

        if results:
            logger.info("Observed %d facts from %d messages (%d actions)",
                       len(candidates), len(messages), len(results))

        return results
