"""Bring-your-own API key LLM provider."""

from __future__ import annotations

import logging
from typing import Any, Literal

from gradata.enhancements.llm_provider import LLMProvider
from gradata.llm.telemetry import record_llm_call

Vendor = Literal["anthropic", "openai", "google"]

_log = logging.getLogger(__name__)

_DEFAULT_MODELS: dict[Vendor, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash",
}

_PRICE_PER_MILLION: dict[Vendor, tuple[float, float]] = {
    "anthropic": (0.80, 4.00),
    "openai": (0.15, 0.60),
    "google": (0.10, 0.40),
}


class BYOKeyProvider(LLMProvider):
    """Direct Anthropic/OpenAI/Google API provider using the user's API key."""

    name = "api"

    def __init__(self, vendor: str, api_key: str, model: str | None = None):
        super().__init__()
        normalized = vendor.strip().lower()
        if normalized not in _DEFAULT_MODELS:
            raise ValueError("vendor must be one of: anthropic, openai, google")
        if not api_key:
            raise ValueError("api_key is required for BYOKeyProvider")
        self.vendor: Vendor = normalized  # type: ignore[assignment]
        self.api_key = api_key
        self.model = model or _DEFAULT_MODELS[self.vendor]
        self._last_usage: dict[str, Any] = {}

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        try:
            import httpx
        except ImportError:
            _log.debug("httpx not installed; BYOKeyProvider unavailable")
            return None

        request = self._build_request(prompt, max_tokens)
        try:
            response = httpx.post(
                request["url"],
                headers=request["headers"],
                json=request["json"],
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            _log.debug("%s BYO API request failed: %s", self.vendor, exc)
            return None

        text, input_tokens, output_tokens = self._parse_response(body, prompt)
        if not text:
            return None
        self._record_call_telemetry(input_tokens, output_tokens)
        return text

    def _build_request(self, prompt: str, max_tokens: int) -> dict[str, Any]:
        if self.vendor == "anthropic":
            return {
                "url": "https://api.anthropic.com/v1/messages",
                "headers": {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                "json": {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
            }
        if self.vendor == "openai":
            return {
                "url": "https://api.openai.com/v1/chat/completions",
                "headers": {
                    "Authorization": f"Bearer {self.api_key}",
                    "content-type": "application/json",
                },
                "json": {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
            }
        return {
            "url": (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            ),
            "headers": {
                "x-goog-api-key": self.api_key,
                "content-type": "application/json",
            },
            "json": {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
        }

    def _parse_response(self, body: dict[str, Any], prompt: str) -> tuple[str, int, int]:
        if self.vendor == "anthropic":
            text = "".join(
                part.get("text", "")
                for part in body.get("content", [])
                if isinstance(part, dict) and part.get("type") in (None, "text")
            ).strip()
            usage = body.get("usage", {})
            return text, _as_int(usage.get("input_tokens"), prompt), _as_int(
                usage.get("output_tokens"), text
            )

        if self.vendor == "openai":
            choices = body.get("choices", [])
            message = choices[0].get("message", {}) if choices else {}
            text = str(message.get("content") or "").strip()
            usage = body.get("usage", {})
            return text, _as_int(usage.get("prompt_tokens"), prompt), _as_int(
                usage.get("completion_tokens"), text
            )

        candidates = body.get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        usage = body.get("usageMetadata", {})
        return text, _as_int(usage.get("promptTokenCount"), prompt), _as_int(
            usage.get("candidatesTokenCount"), text
        )

    def _record_call_telemetry(self, input_tokens: int, output_tokens: int) -> None:
        input_price, output_price = _PRICE_PER_MILLION[self.vendor]
        usd = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
        self._last_usage = {
            "provider": self.name,
            "vendor": self.vendor,
            "model": self.model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd": round(usd, 8),
        }
        record_llm_call(self._last_usage)


def _as_int(value: Any, fallback_text: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = max(1, len(fallback_text) // 4)
    return max(0, parsed)
