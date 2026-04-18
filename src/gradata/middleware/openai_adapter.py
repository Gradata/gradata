"""OpenAI SDK middleware adapter.

Wraps an ``openai.OpenAI()`` client so every
``client.chat.completions.create(...)`` call gets Gradata rules injected
into / prepended to the ``messages`` list as a system message, and its
response optionally checked against RULE-tier regex patterns.

Usage::

    from openai import OpenAI
    from . import wrap_openai

    client = wrap_openai(OpenAI(), brain_path="./brain")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hi"}],
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._core import (
    RuleSource,
    _get,
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
            _iim_msgs = kwargs.get("messages") or []
            _iim_out = [dict(_m) if isinstance(_m, dict) else _m for _m in _iim_msgs]
            _iim_head = _iim_out[0] if _iim_out else None
            if (isinstance(_iim_head, dict) and _iim_head.get("role") == "system"
                    and isinstance(_iim_head.get("content"), (str, type(None)))):
                _iim_head["content"] = inject_into_system(_iim_head.get("content"), block)
            else:
                _iim_out.insert(0, {"role": "system", "content": block})
            kwargs["messages"] = _iim_out

        response = self._mw._orig_chat.completions.create(*args, **kwargs)
        _parts: list[str] = []
        for _choice in (_get(response, "choices") or []):
            _msg = _get(_choice, "message")
            if _msg is None:
                continue
            _c = _get(_msg, "content")
            if _c:
                _parts.append(str(_c))
        text = "\n".join(_parts)
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
