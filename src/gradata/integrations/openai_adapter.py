"""
OpenAI Integration — Patch OpenAI client with brain memory.
============================================================
Wraps the OpenAI chat completions API to inject brain rules
and capture conversations for learning.

Usage:
    from openai import OpenAI
    from gradata.integrations.openai_adapter import patch_openai

    client = OpenAI()
    client = patch_openai(client, brain_dir="./my-brain")

    # Now every chat completion automatically:
    # 1. Injects applicable brain rules into the system message
    # 2. Captures the conversation for fact extraction
    # 3. Logs the AI output for correction tracking
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Draft an email..."}],
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("gradata.integrations.openai")


def patch_openai(client: Any, brain_dir: str | Path = "./brain") -> Any:
    """Patch an OpenAI client to use brain memory.

    Non-destructive: wraps the create method, doesn't modify the client class.
    Falls back to normal behavior if the brain is unavailable.

    Args:
        client: An OpenAI client instance.
        brain_dir: Path to the brain directory.

    Returns:
        The same client with patched chat.completions.create().
    """
    from gradata.brain import Brain

    try:
        brain = Brain(brain_dir)
    except Exception as e:
        logger.warning("Brain not found, OpenAI adapter disabled: %s", e)
        return client

    original_create = client.chat.completions.create

    def patched_create(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages", args[1] if len(args) > 1 else [])

        # Inject brain rules into system message
        try:
            user_msg = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                "",
            )
            rules = brain.apply_brain_rules("general", {"task": user_msg[:100]})

            if rules:
                # Prepend rules to system message or create one
                has_system = any(m.get("role") == "system" for m in messages)
                if has_system:
                    for m in messages:
                        if m.get("role") == "system":
                            m["content"] = f"{rules}\n\n{m['content']}"
                            break
                else:
                    messages.insert(0, {"role": "system", "content": rules})
        except Exception as e:
            logger.debug("Rule injection skipped: %s", e)

        # Call original
        response = original_create(*args, **kwargs)

        # Capture response for tracking
        try:
            ai_content = response.choices[0].message.content
            if ai_content:
                brain.log_output(ai_content, output_type="chat")
                # Observe the full conversation for fact extraction
                if hasattr(brain, 'observe'):
                    brain.observe([*messages, {"role": "assistant", "content": ai_content}])
        except Exception as e:
            logger.debug("Response capture skipped: %s", e)

        return response

    client.chat.completions.create = patched_create
    client._brain = brain  # Expose for correction tracking
    return client