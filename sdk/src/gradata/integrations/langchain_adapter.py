"""
LangChain Integration — Brain-backed memory for LangChain chains.
=================================================================
Provides a LangChain-compatible memory class that uses the brain
for storage and retrieval, with behavioral adaptation.

Usage:
    from gradata.integrations.langchain_adapter import BrainMemory
    from langchain.chains import ConversationChain
    from langchain_openai import ChatOpenAI

    memory = BrainMemory(brain_dir="./my-brain")
    chain = ConversationChain(
        llm=ChatOpenAI(),
        memory=memory,
    )
    response = chain.invoke({"input": "Draft an email to the CFO"})
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("gradata.integrations.langchain")


class BrainMemory:
    """LangChain-compatible memory backed by an Gradata.

    Implements the minimal interface LangChain expects:
    - memory_variables: list of variable names
    - load_memory_variables(): returns context dict
    - save_context(): stores interaction
    - clear(): resets (no-op for persistent brain)

    Also injects brain rules into the context automatically.
    """

    memory_key: str = "brain_context"
    input_key: str = "input"
    output_key: str = "output"

    def __init__(self, brain_dir: str | Path = "./brain") -> None:
        from gradata.brain import Brain

        self.brain = Brain(brain_dir)
        self._messages: list[dict] = []

    @property
    def memory_variables(self) -> list[str]:
        return [self.memory_key]

    def load_memory_variables(self, inputs: dict | None = None) -> dict:
        """Load brain context for the current input.

        Combines applicable rules + relevant brain knowledge.
        """
        user_input = (inputs or {}).get(self.input_key, "")

        parts: list[str] = []

        # Inject rules
        try:
            rules = self.brain.apply_brain_rules("general", {"task": str(user_input)[:100]})
            if rules:
                parts.append(rules)
        except Exception:
            pass

        # Inject relevant context
        try:
            context = self.brain.context_for(str(user_input)[:200])
            if context:
                parts.append(context)
        except Exception:
            pass

        return {self.memory_key: "\n\n".join(parts)}

    def save_context(self, inputs: dict, outputs: dict) -> None:
        """Save an interaction to the brain.

        Logs the AI output and extracts facts from the conversation.
        """
        user_msg = inputs.get(self.input_key, "")
        ai_msg = outputs.get(self.output_key, "")

        if ai_msg:
            try:
                self.brain.log_output(str(ai_msg), output_type="chat")
            except Exception:
                pass

        # Observe conversation for fact extraction
        messages = []
        if user_msg:
            messages.append({"role": "user", "content": str(user_msg)})
        if ai_msg:
            messages.append({"role": "assistant", "content": str(ai_msg)})

        if messages:
            try:
                self.brain.observe(messages)
            except Exception:
                pass

    def clear(self) -> None:
        """No-op for persistent brain memory."""
        pass
