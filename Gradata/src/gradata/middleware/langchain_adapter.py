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
injection covers every prompt / message batch entry in a single callback
invocation: ``on_llm_start`` prepends the block to every prompt in the
list, and ``on_chat_model_start`` injects a system message into every
batch. For stricter control (e.g. structured responses), prefer the
:class:`gradata.middleware.OpenAIMiddleware` wrapper over the underlying
client.
"""

from __future__ import annotations
import logging

from pathlib import Path
from typing import Any

from gradata.middleware._core import (
    RuleSource,
    _get,
    build_brain_rules_block,
    check_output,
)
logger = logging.getLogger(__name__)


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
        session_id: str | None = None,
    ) -> None:
        super().__init__()
        self._source = source or RuleSource(brain_path=brain_path)
        self._strict = strict
        if session_id is None:
            import uuid

            session_id = str(uuid.uuid4())
        self._session_id = session_id

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
        # Prepend block to every prompt in the batch (LangChain uses the list
        # in-place and a batch call can contain multiple prompts).
        for i, prompt in enumerate(prompts):
            prompts[i] = f"{block}\n\n{prompt}"

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        block = build_brain_rules_block(self._source)
        if not block or not messages:
            return
        system_cls = None
        for batch in messages:
            if not batch:
                continue
            first = batch[0]
            content = getattr(first, "content", None)
            msg_type = getattr(first, "type", "")
            if content is not None and msg_type == "system":
                # BaseMessage.content may be a str or a list of content blocks
                # (multimodal). Preserve structure in both cases.
                if isinstance(content, str):
                    first.content = f"{content}\n\n{block}"
                elif isinstance(content, list):
                    first.content = [*content, {"type": "text", "text": block}]
                else:
                    first.content = [content, {"type": "text", "text": block}]
                continue
            if system_cls is None:
                try:
                    from langchain_core.messages import SystemMessage
                except ImportError:  # pragma: no cover
                    return
                system_cls = SystemMessage
            batch.insert(0, system_cls(content=block))

    # -- enforcement ------------------------------------------------------

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        text = _extract_llm_text(response)
        if not text:
            return
        check_output(self._source, text, strict=self._strict)

        brain_path = self._source._brain_path
        if brain_path:
            try:
                from gradata._transcript import log_turn

                log_turn(str(brain_path), self._session_id, "assistant", text)
            except Exception:
                logger.warning('Suppressed exception in LangChainCallback.on_llm_end', exc_info=True)


def _extract_llm_text(response: Any) -> str:
    """Best-effort text extraction from a LangChain ``LLMResult``."""
    generations = _get(response, "generations") or []
    parts: list[str] = []
    for batch in generations:
        for gen in batch:
            text = _get(gen, "text")
            if text:
                parts.append(str(text))
    return "\n".join(parts)
