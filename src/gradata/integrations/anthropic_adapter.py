"""
Anthropic Integration — Patch Anthropic client with brain memory.
=================================================================
Wraps the Anthropic messages API to inject brain rules and capture
conversations for learning.

Usage:
    from anthropic import Anthropic
    from gradata.integrations.anthropic_adapter import patch_anthropic

    client = Anthropic()
    client = patch_anthropic(client, brain_dir="./my-brain")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Draft an email..."}],
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("gradata.integrations.anthropic")


def patch_anthropic(client: Any, brain_dir: str | Path = "./brain") -> Any:
    """Patch an Anthropic client to use brain memory.

    Args:
        client: An Anthropic client instance.
        brain_dir: Path to the brain directory.

    Returns:
        The same client with patched messages.create().
    """
    from gradata.brain import Brain

    try:
        brain = Brain(brain_dir)
    except Exception as e:
        logger.warning("Brain not found, Anthropic adapter disabled: %s", e)
        return client

    original_create = client.messages.create

    def patched_create(*args: Any, **kwargs: Any) -> Any:
        messages = kwargs.get("messages", [])
        system = kwargs.get("system", "")

        # Inject brain rules into system prompt
        try:
            user_msg = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                "",
            )
            if isinstance(user_msg, list):
                user_msg = " ".join(
                    b.get("text", "") for b in user_msg if isinstance(b, dict)
                )
            rules = brain.apply_brain_rules("general", {"task": str(user_msg)[:100]})

            if rules:
                if system:
                    kwargs["system"] = f"{rules}\n\n{system}"
                else:
                    kwargs["system"] = rules
        except Exception as e:
            logger.debug("Rule injection skipped: %s", e)

        # Call original
        response = original_create(*args, **kwargs)

        # Capture response
        try:
            ai_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    ai_content += block.text

            if ai_content:
                brain.log_output(ai_content, output_type="chat")
                all_msgs = messages + [{"role": "assistant", "content": ai_content}]
                if hasattr(brain, 'observe'):
                    brain.observe(all_msgs)
        except Exception as e:
            logger.debug("Response capture skipped: %s", e)

        return response

    client.messages.create = patched_create
    client._brain = brain
    return client
