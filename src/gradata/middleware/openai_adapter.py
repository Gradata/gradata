"""OpenAI SDK middleware adapter.

Wraps an ``openai.OpenAI()`` client so every
``client.chat.completions.create(...)`` call gets Gradata rules injected
into / prepended to the ``messages`` list as a system message, and its
response optionally checked against RULE-tier regex patterns.

Usage::

    from openai import OpenAI
    from gradata.middleware import wrap_openai

    client = wrap_openai(OpenAI(), brain_path="./brain")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hi"}],
    )
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


def _require_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "OpenAIMiddleware requires the 'openai' package. "
            "Install with: pip install openai"
        ) from exc


def _extract_text(response: Any) -> str:
    """Best-effort text extraction from an OpenAI chat.completions response."""
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        return ""
    parts: list[str] = []
    for choice in choices:
        message = getattr(choice, "message", None)
        if message is None and isinstance(choice, dict):
            message = choice.get("message")
        if message is None:
            continue
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        if content:
            parts.append(str(content))
    return "\n".join(parts)


def _inject_into_messages(messages: list[Any], block: str) -> list[Any]:
    """Return a new messages list with rules folded into the system message.

    If a leading system message exists, its ``content`` is extended with the
    block; otherwise a new system message is prepended.
    """
    if not block:
        return list(messages)
    out = [dict(m) if isinstance(m, dict) else m for m in messages]
    if out and isinstance(out[0], dict) and out[0].get("role") == "system":
        existing = out[0].get("content") or ""
        out[0]["content"] = inject_into_system(
            existing if isinstance(existing, str) else str(existing),
            block,
        )
    else:
        out.insert(0, {"role": "system", "content": block})
    return out


class OpenAIMiddleware:
    """Wraps an OpenAI client with Gradata rule injection + enforcement."""

    def __init__(
        self,
        client: Any,
        *,
        brain_path: str | Path | None = None,
        source: RuleSource | None = None,
        strict: bool = False,
    ) -> None:
        _require_openai()
        self._client = client
        self._source = source or RuleSource(brain_path=brain_path)
        self._strict = strict
        self._orig_chat = client.chat
        self.chat = _ChatProxy(self)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _ChatProxy:
    def __init__(self, mw: OpenAIMiddleware) -> None:
        self._mw = mw
        self.completions = _CompletionsProxy(mw)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mw._orig_chat, name)


class _CompletionsProxy:
    def __init__(self, mw: OpenAIMiddleware) -> None:
        self._mw = mw

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mw._orig_chat.completions, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        block = build_brain_rules_block(self._mw._source)
        if block:
            messages = kwargs.get("messages") or []
            kwargs["messages"] = _inject_into_messages(list(messages), block)

        response = self._mw._orig_chat.completions.create(*args, **kwargs)
        text = _extract_text(response)
        if text:
            check_output(self._mw._source, text, strict=self._mw._strict)
        return response


def wrap_openai(
    client: Any,
    *,
    brain_path: str | Path | None = None,
    source: RuleSource | None = None,
    strict: bool = False,
) -> OpenAIMiddleware:
    """Convenience constructor — see :class:`OpenAIMiddleware`."""
    return OpenAIMiddleware(
        client, brain_path=brain_path, source=source, strict=strict,
    )
