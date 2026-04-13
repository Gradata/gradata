"""LangChain middleware adapter.

Provides :class:`LangChainCallback`, a ``BaseCallbackHandler`` that:

- Injects the Gradata ``<brain-rules>`` block into prompts at
  ``on_llm_start`` / ``on_chat_model_start``.
- Checks the LLM output against RULE-tier regex patterns at ``on_llm_end``.

Usage::

    from langchain_openai import ChatOpenAI
    from gradata.middleware import LangChainCallback

    llm = ChatOpenAI(callbacks=[LangChainCallback(brain_path="./brain")])
    llm.invoke("Write a short greeting")

Because LangChain callbacks mutate internal prompt buffers in-place, the
injection is done best-effort on the first prompt only. For stricter
control, prefer the :class:`gradata.middleware.OpenAIMiddleware` wrapper
over the underlying client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gradata.middleware._core import (
    RuleSource,
    build_brain_rules_block,
    check_output,
)

try:
    from langchain_core.callbacks import BaseCallbackHandler as _BaseCallbackHandler
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _BaseCallbackHandler = object  # type: ignore[assignment,misc]
    _LANGCHAIN_AVAILABLE = False


class LangChainCallback(_BaseCallbackHandler):  # type: ignore[misc,valid-type]
    """LangChain callback that injects Gradata rules and enforces them."""

    def __new__(cls, *args: Any, **kwargs: Any) -> LangChainCallback:
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChainCallback requires 'langchain-core'. "
                "Install with: pip install langchain-core"
            )
        return super().__new__(cls)

    def __init__(
        self,
        *,
        brain_path: str | Path | None = None,
        source: RuleSource | None = None,
        strict: bool = False,
    ) -> None:
        super().__init__()
        self._source = source or RuleSource(brain_path=brain_path)
        self._strict = strict

    # -- injection --------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        block = build_brain_rules_block(self._source)
        if not block or not prompts:
            return
        # Prepend block to the first prompt. LangChain uses the list in-place.
        prompts[0] = f"{block}\n\n{prompts[0]}"

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        block = build_brain_rules_block(self._source)
        if not block or not messages or not messages[0]:
            return
        first_batch = messages[0]
        # If the first message is a system-style message, extend its content.
        first = first_batch[0]
        content = getattr(first, "content", None)
        msg_type = getattr(first, "type", "")
        if content is not None and msg_type == "system":
            first.content = f"{content}\n\n{block}"
            return
        # Otherwise, prepend a SystemMessage if langchain_core is available.
        try:
            from langchain_core.messages import SystemMessage
        except ImportError:  # pragma: no cover
            return
        first_batch.insert(0, SystemMessage(content=block))

    # -- enforcement ------------------------------------------------------

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        text = _extract_llm_text(response)
        if not text:
            return
        check_output(self._source, text, strict=self._strict)


def _extract_llm_text(response: Any) -> str:
    """Best-effort text extraction from a LangChain ``LLMResult``."""
    generations = getattr(response, "generations", None)
    if generations is None and isinstance(response, dict):
        generations = response.get("generations")
    if not generations:
        return ""
    parts: list[str] = []
    for batch in generations:
        for gen in batch:
            text = getattr(gen, "text", None)
            if text is None and isinstance(gen, dict):
                text = gen.get("text", "")
            if text:
                parts.append(str(text))
    return "\n".join(parts)
