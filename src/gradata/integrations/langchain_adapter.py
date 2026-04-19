"""LangChain Integration — DEPRECATED, removed in v0.8.0. Migrate rule injection to
:class:`~gradata.middleware.langchain_adapter.LangChainCallback`; :class:`BrainMemory` remains."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.langchain_adapter is deprecated and will be removed "
    "in v0.8.0.  Use 'from gradata.middleware import LangChainCallback' for "
    "rule injection, or keep BrainMemory here until a retrieval-memory "
    "equivalent lands in gradata.middleware.",
    DeprecationWarning,
    stacklevel=2,
)

import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("gradata.integrations.langchain")


class BrainMemory:
    """LangChain-compatible memory backed by Gradata.

    .. deprecated::
        This class will be removed in v0.8.0.  Use
        :class:`gradata.middleware.LangChainCallback` for rule injection.
    """

    memory_key: str = "brain_context"
    input_key: str = "input"
    output_key: str = "output"

    def __init__(self, brain_dir: str | Path = "./brain") -> None:
        from ..brain import Brain

        self.brain = Brain(brain_dir)
        self._messages: list[dict] = []

    @property
    def memory_variables(self) -> list[str]:
        return [self.memory_key]

    def load_memory_variables(self, inputs: dict | None = None) -> dict:
        user_input = (inputs or {}).get(self.input_key, "")

        parts: list[str] = []

        try:
            rules = self.brain.apply_brain_rules("general", {"task": str(user_input)[:100]})
            if rules:
                parts.append(rules)
        except Exception:
            pass

        try:
            context = self.brain.context_for(str(user_input)[:200])
            if context:
                parts.append(context)
        except Exception:
            pass

        return {self.memory_key: "\n\n".join(parts)}

    def save_context(self, inputs: dict, outputs: dict) -> None:
        user_msg = inputs.get(self.input_key, "")
        ai_msg = outputs.get(self.output_key, "")

        if ai_msg:
            with contextlib.suppress(Exception):
                self.brain.log_output(str(ai_msg), output_type="chat")

        messages = []
        if user_msg:
            messages.append({"role": "user", "content": str(user_msg)})
        if ai_msg:
            messages.append({"role": "assistant", "content": str(ai_msg)})

        if messages:
            try:
                if hasattr(self.brain, "observe"):
                    self.brain.observe(messages)
            except Exception:
                pass

    def clear(self) -> None:
        """No-op for persistent brain memory."""
