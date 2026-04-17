"""LLM provider abstraction for behavioral extraction.

Supports Anthropic (default), OpenAI, and any OpenAI-compatible endpoint
(Ollama, vLLM, Together, etc.) via GenericHTTPProvider.

Provider is selected via:
  1. Brain(llm_provider=...) constructor arg
  2. GRADATA_LLM_PROVIDER env var ("anthropic", "openai", "generic")
  3. Default: "anthropic" (falls back to template-only if SDK not installed)
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

_log = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Base class for LLM providers used in behavioral extraction."""

    @abstractmethod
    def complete(self, prompt: str, *, max_tokens: int = 100, timeout: float = 12.0) -> str | None:
        """Send a prompt and return the completion text, or None on failure."""


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider (default)."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", auth_token: str | None = None):
        self.model = model
        self._auth = auth_token

    def complete(self, prompt: str, *, max_tokens: int = 100, timeout: float = 12.0) -> str | None:
        try:
            import anthropic
        except ImportError:
            _log.debug("anthropic SDK not installed")
            return None

        try:
            kwargs: dict = {"timeout": timeout}
            if self._auth:
                kwargs["api_key"] = self._auth
            client = anthropic.Anthropic(**kwargs)
            msg = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()  # type: ignore[union-attr]
            return text if 5 < len(text) < 500 else None
        except Exception as e:
            _log.debug("Anthropic completion failed: %s", e)
            return None


def _openai_complete(
    *, model: str, prompt: str, max_tokens: int, timeout: float,
    api_key: str | None = None, base_url: str | None = None, log_label: str = "OpenAI",
) -> str | None:
    """Shared OpenAI-compatible chat completion. Returns text or None on any failure."""
    try:
        import openai
    except ImportError:
        _log.debug("openai SDK not installed (needed for %s provider)", log_label)
        return None

    try:
        kwargs: dict = {"timeout": timeout}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        client = openai.OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (resp.choices[0].message.content or "").strip()
        return text if 5 < len(text) < 500 else None
    except Exception as e:
        _log.debug("%s completion failed: %s", log_label, e)
        return None


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (works with OpenAI, Azure OpenAI)."""

    def __init__(self, model: str = "gpt-4o-mini", auth_token: str | None = None,
                 base_url: str | None = None):
        self.model = model
        self._auth = auth_token
        self.base_url = base_url

    def complete(self, prompt: str, *, max_tokens: int = 100, timeout: float = 12.0) -> str | None:
        return _openai_complete(
            model=self.model, prompt=prompt, max_tokens=max_tokens, timeout=timeout,
            api_key=self._auth, base_url=self.base_url, log_label="OpenAI",
        )


class GenericHTTPProvider(LLMProvider):
    """Generic OpenAI-compatible HTTP endpoint (Ollama, vLLM, Together, LM Studio, etc.).

    Configure via env vars:
        GRADATA_LLM_BASE_URL  (default: http://localhost:11434/v1)
        GRADATA_LLM_MODEL     (default: llama3)
        GRADATA_LLM_AUTH      (optional)
    """

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 auth_token: str | None = None):
        self.base_url = base_url or os.environ.get("GRADATA_LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.environ.get("GRADATA_LLM_MODEL", "llama3")
        self._auth = auth_token or os.environ.get("GRADATA_LLM_AUTH", "")
        # SSRF / bearer-key exfil guard: refuse HTTP to non-local hosts at construction time
        from gradata._http import require_https
        require_https(self.base_url, "GRADATA_LLM_BASE_URL")

    def complete(self, prompt: str, *, max_tokens: int = 100, timeout: float = 12.0) -> str | None:
        # openai SDK requires a key even for local — use placeholder if none set
        return _openai_complete(
            model=self.model, prompt=prompt, max_tokens=max_tokens, timeout=timeout,
            api_key=self._auth or "local", base_url=self.base_url, log_label="Generic HTTP",
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "generic": GenericHTTPProvider,
}


def get_provider(name: str | None = None, **kwargs) -> LLMProvider:
    """Get an LLM provider by name.

    Args:
        name: "anthropic", "openai", or "generic". Defaults to GRADATA_LLM_PROVIDER
              env var, then "anthropic".
        **kwargs: Passed to the provider constructor (model, auth_token, base_url).
    """
    name = name or os.environ.get("GRADATA_LLM_PROVIDER", "anthropic")
    cls = _PROVIDERS.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {name!r}. Choose from: {list(_PROVIDERS)}")
    return cls(**kwargs)
