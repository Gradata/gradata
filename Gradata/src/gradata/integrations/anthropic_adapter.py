"""Anthropic Integration — DEPRECATED.

.. deprecated::
    ``gradata.integrations.anthropic_adapter`` is deprecated and will be
    removed in v0.8.0.  Use ``gradata.middleware.anthropic_adapter`` instead::

        from gradata.middleware import wrap_anthropic
        client = wrap_anthropic(Anthropic(), brain_path="./brain")

    ``wrap_anthropic`` returns an ``AnthropicMiddleware`` wrapper (richer rule
    enforcement via :class:`~gradata.middleware._core.RuleSource`).  If you
    need the legacy in-place patch behaviour, pin to gradata<0.8.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.anthropic_adapter is deprecated and will be removed "
    "in v0.8.0.  Use 'from gradata.middleware import wrap_anthropic' instead.",
    DeprecationWarning,
    stacklevel=2,
)

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("gradata.integrations.anthropic")


def patch_anthropic(client: Any, brain_dir: str | Path = "./brain") -> Any:
    """Patch an Anthropic client to use brain memory.

    .. deprecated::
        Use :func:`gradata.middleware.wrap_anthropic` instead.
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

        try:
            user_msg = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                "",
            )
            if isinstance(user_msg, list):
                user_msg = " ".join(b.get("text", "") for b in user_msg if isinstance(b, dict))
            rules = brain.apply_brain_rules("general", {"task": str(user_msg)[:100]})

            if rules:
                if system:
                    kwargs["system"] = f"{rules}\n\n{system}"
                else:
                    kwargs["system"] = rules
        except Exception as e:
            logger.debug("Rule injection skipped: %s", e)

        response = original_create(*args, **kwargs)

        try:
            ai_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    ai_content += block.text

            if ai_content:
                brain.log_output(ai_content, output_type="chat")
                all_msgs = [*messages, {"role": "assistant", "content": ai_content}]
                if hasattr(brain, "observe"):
                    brain.observe(all_msgs)
        except Exception as e:
            logger.debug("Response capture skipped: %s", e)

        return response

    client.messages.create = patched_create
    client._brain = brain
    return client
