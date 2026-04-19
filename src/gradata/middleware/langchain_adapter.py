"""LangChain BaseCallbackHandler: injects <brain-rules> on prompt start and
validates output against RULE regexes on llm_end. For stricter control prefer
gradata.middleware.OpenAIMiddleware around the underlying client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._core import (
    RuleSource,
    _get,
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
        _elt_parts: list[str] = []
        for _elt_batch in _get(response, "generations") or []:
            for _elt_gen in _elt_batch:
                _elt_t = _get(_elt_gen, "text")
                if _elt_t:
                    _elt_parts.append(str(_elt_t))
        text = "\n".join(_elt_parts)
        if not text:
            return
        check_output(self._source, text, strict=self._strict)
