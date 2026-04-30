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
import logging

from pathlib import Path
from typing import Any

from gradata.middleware._core import (
    RuleSource,
    _get,
    build_brain_rules_block,
    check_output,
    inject_into_system,
)
logger = logging.getLogger(__name__)



def _require_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError as exc:  # pragma: no cover - import guard
        raise ImportError(
            "OpenAIMiddleware requires the 'openai' package. Install with: pip install openai"
        ) from exc


def _extract_text(response: Any) -> str:
    """Best-effort text extraction from an OpenAI chat.completions response."""
    choices = _get(response, "choices") or []
    parts: list[str] = []
    for choice in choices:
        message = _get(choice, "message")
        if message is None:
            continue
        content = _get(message, "content")
        if content:
            parts.append(str(content))
    return "\n".join(parts)


def _inject_into_messages(messages: list[Any], block: str) -> list[Any]:
    """Return a new messages list with rules folded into the system message.

    If a leading system message with string content exists, its content is
    extended with the block. In every other case (no system message, or a
    system message whose content is a structured multimodal list) a fresh
    system message is prepended so the original payload is preserved.
    """
    out = [dict(m) if isinstance(m, dict) else m for m in messages]
    head = out[0] if out else None
    if (
        isinstance(head, dict)
        and head.get("role") == "system"
        and isinstance(head.get("content"), (str, type(None)))
    ):
        head["content"] = inject_into_system(head.get("content"), block)
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
        session_id: str | None = None,
    ) -> None:
        _require_openai()
        self._client = client
        self._source = source or RuleSource(brain_path=brain_path)
        self._strict = strict
        if session_id is None:
            import uuid

            session_id = str(uuid.uuid4())
        self._session_id = session_id
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
        messages = kwargs.get("messages") or []
        if block:
            kwargs["messages"] = _inject_into_messages(messages, block)

        response = self._mw._orig_chat.completions.create(*args, **kwargs)
        text = _extract_text(response)
        if text:
            check_output(self._mw._source, text, strict=self._mw._strict)

        # Transcript logging (opt-in via GRADATA_TRANSCRIPT=1).
        brain_path = self._mw._source._brain_path
        if brain_path:
            try:
                from gradata._transcript import log_turn

                for msg in reversed(messages):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        log_turn(
                            str(brain_path),
                            self._mw._session_id,
                            "user",
                            str(msg.get("content") or ""),
                        )
                        break
                if text:
                    log_turn(str(brain_path), self._mw._session_id, "assistant", text)
            except Exception:
                logger.warning('Suppressed exception in _CompletionsProxy.create', exc_info=True)

        return response


def wrap_openai(
    client: Any,
    *,
    brain_path: str | Path | None = None,
    source: RuleSource | None = None,
    strict: bool = False,
    session_id: str | None = None,
) -> OpenAIMiddleware:
    """Convenience constructor — see :class:`OpenAIMiddleware`."""
    return OpenAIMiddleware(
        client,
        brain_path=brain_path,
        source=source,
        strict=strict,
        session_id=session_id,
    )
