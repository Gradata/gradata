"""
CrewAI Integration — Brain-backed memory for CrewAI agents.
=============================================================
Provides a CrewAI-compatible memory class that uses the brain
for knowledge storage and behavioral adaptation.

Usage:
    from gradata.integrations.crewai_adapter import BrainCrewMemory
    from crewai import Agent, Crew

    memory = BrainCrewMemory(brain_dir="./my-brain")

    agent = Agent(
        role="Sales AE",
        goal="Draft follow-up emails",
        memory=True,
    )
    crew = Crew(agents=[agent], memory=memory)
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("gradata.integrations.crewai")


class BrainCrewMemory:
    """CrewAI-compatible memory backed by an Gradata.

    CrewAI's memory interface expects:
    - save(): store a memory item
    - search(): retrieve relevant memories
    - reset(): clear (no-op for persistent brain)
    """

    def __init__(self, brain_dir: str | Path = "./brain") -> None:
        from gradata.brain import Brain

        self.brain = Brain(brain_dir)

    def save(
        self,
        value: str,
        metadata: dict | None = None,
        agent: str = "",
    ) -> None:
        """Save a memory item to the brain.

        Args:
            value: The content to remember.
            metadata: Optional metadata dict.
            agent: Agent identifier (for agent-scoped memories).
        """
        try:
            self.brain.observe(
                [{"role": "assistant", "content": value}],
                user_id=agent or "default",
            )
        except Exception as e:
            logger.debug("CrewAI memory save skipped: %s", e)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search brain for relevant memories.

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of result dicts with 'content' and 'score' keys.
        """
        try:
            results = self.brain.search(query, top_k=limit)
            return [
                {
                    "content": r.get("text", ""),
                    "score": r.get("score", 0),
                    "source": r.get("source", ""),
                }
                for r in results
            ]
        except Exception:
            return []

    def reset(self) -> None:
        """No-op for persistent brain memory."""
        pass

    def get_rules(self, task: str = "", context: dict | None = None) -> str:
        """Get applicable brain rules for a task.

        CrewAI-specific helper. Inject the returned string into
        the agent's system prompt for behavioral adaptation.
        """
        try:
            return self.brain.apply_brain_rules(task, context)
        except Exception:
            return ""
