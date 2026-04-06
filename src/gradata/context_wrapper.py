"""
Learning Context Wrapper — One-line behavioral adaptation for any LLM call.
============================================================================
Inspired by: Letta's Learning SDK (wraps any LLM call with memory).

Usage:
    from gradata import brain_context

    with brain_context("./my-brain"):
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Draft an email..."}],
        )
    # Brain automatically:
    # 1. Injected relevant rules into the system message
    # 2. Captured the conversation for fact extraction
    # 3. Ready to track corrections if user edits the response

    # Record correction (call after user edits)
    brain_context.correct(response.choices[0].message.content, user_edited_version)

This is the distribution mechanism. One import, one context manager, works
with OpenAI, Anthropic, or any chat completions API.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger("gradata.context_wrapper")


@contextmanager
def brain_context(
    brain_dir: str | Path = "./brain",
    user_id: str = "default",
    inject_rules: bool = True,
    observe: bool = True,
) -> Generator[BrainContextState, None, None]:
    """Wrap any LLM call with behavioral adaptation.

    Inspired by Letta's Learning SDK pattern. One context manager
    gives you memory injection, fact extraction, and correction tracking.

    Args:
        brain_dir: Path to the brain directory.
        user_id: User identifier for scoped memories.
        inject_rules: If True, applicable rules are injected into context.
        observe: If True, conversation is captured for fact extraction.

    Yields:
        BrainContextState with helper methods for the active context.

    Example::

        with brain_context("./my-brain") as ctx:
            # ctx.rules contains applicable rules as a string
            # ctx.context contains relevant brain context
            response = my_llm_call(system=ctx.system_prompt("Draft email"))
            ctx.capture_response(response)

        # After context exits, call correct() if user edited
        ctx.correct(original_response, user_edited_version)
    """
    from gradata.brain import Brain

    try:
        brain = Brain(brain_dir)
    except Exception as e:
        logger.warning("Brain not found at %s, running without adaptation: %s", brain_dir, e)
        yield BrainContextState(None, user_id)
        return

    state = BrainContextState(brain, user_id, inject_rules=inject_rules)

    try:
        yield state
    finally:
        # Post-context: extract facts from captured conversation
        if observe and state._captured_messages:
            try:
                brain.observe(state._captured_messages, user_id=user_id)
            except Exception as e:
                logger.warning("Fact extraction failed: %s", e)


class BrainContextState:
    """State object yielded by brain_context().

    Provides helper methods for rule injection, response capture,
    and correction tracking within the context manager.
    """

    def __init__(
        self,
        brain: Any | None,
        user_id: str = "default",
        inject_rules: bool = True,
    ) -> None:
        self._brain = brain
        self._user_id = user_id
        self._inject_rules = inject_rules
        self._captured_messages: list[dict] = []
        self._last_ai_output: str | None = None
        self._rules_text: str = ""

        # Pre-load rules if brain available
        if brain and inject_rules:
            try:
                self._rules_text = brain.apply_brain_rules("general")
            except Exception:
                pass

    @property
    def rules(self) -> str:
        """Applicable brain rules as a formatted string."""
        return self._rules_text

    @property
    def has_brain(self) -> bool:
        """True if a brain is active."""
        return self._brain is not None

    def system_prompt(self, task: str = "", context: dict | None = None) -> str:
        """Build a system prompt with injected brain rules and context.

        Args:
            task: Description of the current task (for scoped rule selection).
            context: Optional context dict for more precise rule matching.

        Returns:
            Formatted string to prepend to or use as the system message.
        """
        parts: list[str] = []

        # Get task-specific rules
        if self._brain and task:
            try:
                rules = self._brain.apply_brain_rules(task, context)
                if rules:
                    parts.append(rules)
            except Exception:
                pass
        elif self._rules_text:
            parts.append(self._rules_text)

        # Get relevant context from brain
        if self._brain and task:
            try:
                brain_ctx = self._brain.context_for(task)
                if brain_ctx:
                    parts.append(brain_ctx)
            except Exception:
                pass

        return "\n\n".join(parts)


    def capture_response(self, response: str) -> None:
        """Capture the AI's response for tracking.

        Call this after the LLM generates output so the brain can
        track it and later compare against user corrections.
        """
        self._last_ai_output = response
        self._captured_messages.append({"role": "assistant", "content": response})

        # Log the output
        if self._brain:
            try:
                self._brain.log_output(response, output_type="general")
            except Exception:
                pass

    def correct(self, draft: str | None = None, final: str = "") -> dict | None:
        """Record a correction (user edited the AI's output).

        Args:
            draft: The original AI output. If None, uses the last captured response.
            final: The user's edited version.

        Returns:
            Correction event dict, or None if no brain.
        """
        if not self._brain:
            if final:
                logger.warning("Correction dropped: no brain connected. Learning signal lost.")
            return None

        if draft is None:
            draft = self._last_ai_output
        if not draft:
            logger.warning("No draft to correct. Call capture_response() first.")
            return None

        try:
            return self._brain.correct(draft, final)
        except Exception as e:
            logger.warning("Correction failed: %s", e)
            return None
