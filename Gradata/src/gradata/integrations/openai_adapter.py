"""OpenAI Integration — DEPRECATED.

.. deprecated::
    ``gradata.integrations.openai_adapter`` is deprecated and will be
    removed in v0.8.0.  Use ``gradata.middleware.openai_adapter`` instead::

        from gradata.middleware import wrap_openai
        client = wrap_openai(OpenAI(), brain_path="./brain")

    ``wrap_openai`` returns an ``OpenAIMiddleware`` proxy with richer rule
    enforcement via :class:`~gradata.middleware._core.RuleSource`.  If you
    need the legacy in-place patch behaviour, pin to gradata<0.8.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.openai_adapter is deprecated and will be removed "
    "in v0.8.0.  Use 'from gradata.middleware import wrap_openai' instead.",
    DeprecationWarning,
    stacklevel=2,
)

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("gradata.integrations.openai")


def patch_openai(client: Any, brain_dir: str | Path = "./brain") -> Any:
    """Patch an OpenAI client to use brain memory.

    .. deprecated::
        Use :func:`gradata.middleware.wrap_openai` instead.
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

        try:
            user_msg = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                "",
            )
            rules = brain.apply_brain_rules("general", {"task": user_msg[:100]})

            if rules:
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

        response = original_create(*args, **kwargs)

        try:
            ai_content = response.choices[0].message.content
            if ai_content:
                brain.log_output(ai_content, output_type="chat")
                if hasattr(brain, "observe"):
                    brain.observe([*messages, {"role": "assistant", "content": ai_content}])
        except Exception as e:
            logger.debug("Response capture skipped: %s", e)

        return response

    client.chat.completions.create = patched_create
    client._brain = brain
    return client
