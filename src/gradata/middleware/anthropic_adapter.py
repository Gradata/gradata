"""Anthropic SDK middleware adapter.

Wraps an ``anthropic.Anthropic()`` client so every
``client.messages.create(...)`` call gets Gradata rules injected into the
system prompt and its response optionally checked against RULE-tier regex
patterns.

Usage::

    from anthropic import Anthropic
    from gradata.middleware import wrap_anthropic

    client = wrap_anthropic(Anthropic(), brain_path="./brain")
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=128,
    )

The wrapper preserves the original ``messages`` object shape; only the
``system`` kwarg is mutated on the way in, and the response is only
inspected on the way out.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gradata.middleware._core import (
    RuleSource,
    build_brain_rules_block,
    check_output,
    inject_into_system,
)


def _require_anthropic() -> None:
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "AnthropicMiddleware requires the 'anthropic' package. "
            "Install with: pip install anthropic"
        ) from exc


def _extract_text(response: Any) -> str:
    """Best-effort extraction of the assistant text from an Anthropic response."""
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content")
    if not content:
        return ""
    parts: list[str] = []
    for block in content:
        # SDK object: block.type == 'text', block.text == '...'
        block_type = getattr(block, "type", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")
        if block_type == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text", "")
            if text:
                parts.append(str(text))
    return "\n".join(parts)


class AnthropicMiddleware:
    """Wraps an Anthropic client with Gradata rule injection + enforcement."""

    def __init__(
        self,
        client: Any,
        *,
        brain_path: str | Path | None = None,
        source: RuleSource | None = None,
        strict: bool = False,
    ) -> None:
        _require_anthropic()
        self._client = client
        self._source = source or RuleSource(brain_path=brain_path)
        self._strict = strict
        # Replace the messages namespace with a wrapper that intercepts create
        self._orig_messages = client.messages
        self.messages = _MessagesProxy(self)

    # Delegate everything else to the underlying client
    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _MessagesProxy:
    """Thin proxy over ``client.messages`` that intercepts ``create``."""

    def __init__(self, mw: AnthropicMiddleware) -> None:
        self._mw = mw

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mw._orig_messages, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        block = build_brain_rules_block(self._mw._source)
        if block:
            system = kwargs.get("system")
            # Anthropic accepts either a string or a list of content blocks.
            # For lists we append a new text block; for strings we concatenate.
            if isinstance(system, list):
                kwargs["system"] = [*system, {"type": "text", "text": block}]
            else:
                kwargs["system"] = inject_into_system(system, block)

        response = self._mw._orig_messages.create(*args, **kwargs)

        text = _extract_text(response)
        if text:
            check_output(self._mw._source, text, strict=self._mw._strict)
        return response


def wrap_anthropic(
    client: Any,
    *,
    brain_path: str | Path | None = None,
    source: RuleSource | None = None,
    strict: bool = False,
) -> AnthropicMiddleware:
    """Convenience constructor — see :class:`AnthropicMiddleware`."""
    return AnthropicMiddleware(
        client, brain_path=brain_path, source=source, strict=strict,
    )
