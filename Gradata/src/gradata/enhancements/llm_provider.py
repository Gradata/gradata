"""LLM provider abstraction for behavioral extraction and meta-rule synthesis.

Supports five modes:
  * ``anthropic``  — Anthropic Claude SDK (BYO ANTHROPIC_API_KEY)
  * ``openai``     — OpenAI / OpenAI-compatible SDK (BYO OPENAI_API_KEY)
  * ``generic``    — Generic OpenAI-compat HTTP endpoint (Ollama / vLLM / Together)
  * ``cli``        — BYO-CLI: subprocess-shell to ``claude`` / ``codex`` / ``gemini``
                     (uses the user's existing Max-plan OAuth — no API key needed)
  * ``cloud``      — Gradata Cloud relay (subscription-billed, server holds the key)
  * ``gemma``      — Google native Gemma API (free tier)

Provider is selected via:
  1. Brain(llm_provider=...) constructor arg
  2. ``GRADATA_LLM_PROVIDER`` env var
  3. Default: ``auto`` — resolves cli → anthropic → openai → cloud → None

All providers implement ``complete(prompt, max_tokens, timeout) -> str | None`` and
share a per-instance circuit breaker (3 consecutive failures = open for 5 min).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from gradata._env import env_str
from gradata._http import require_https

_log = logging.getLogger(__name__)

# Per-instance circuit breaker tunables
_CB_THRESHOLD = 3
_CB_COOLDOWN_SEC = 300.0


class LLMProvider(ABC):
    """Base class for LLM providers used in behavioral extraction.

    Subclasses implement ``_complete_impl``. The base ``complete`` wrapper:
      * gates calls behind the circuit breaker
      * records consecutive failures
      * runs the optional pre-prompt sanitization hook
    """

    name: str = "base"

    def __init__(self) -> None:
        self._cb_fails = 0
        self._cb_opened_at: float | None = None

    # -- circuit breaker ----------------------------------------------------
    def _circuit_open(self) -> bool:
        if self._cb_opened_at is None:
            return False
        if time.monotonic() - self._cb_opened_at > _CB_COOLDOWN_SEC:
            # cooldown expired — half-open: reset counters
            self._cb_fails = 0
            self._cb_opened_at = None
            return False
        return True

    def _record_failure(self) -> None:
        self._cb_fails += 1
        if self._cb_fails >= _CB_THRESHOLD:
            self._cb_opened_at = time.monotonic()
            _log.debug("%s provider circuit opened after %d failures", self.name, self._cb_fails)

    def _record_success(self) -> None:
        self._cb_fails = 0
        self._cb_opened_at = None

    # -- pre-prompt hook ----------------------------------------------------
    @staticmethod
    def _sanitize(prompt: str) -> str:
        """Pre-prompt hook: neutralize prompt-injection in lesson content."""
        try:
            from gradata.enhancements._sanitize import sanitize_lesson_content

            return sanitize_lesson_content(prompt, "llm_prompt")
        except Exception:
            return prompt

    # -- public entry -------------------------------------------------------
    def complete(
        self, prompt: str, *, max_tokens: int = 100, timeout: float = 12.0, sanitize: bool = False
    ) -> str | None:
        if self._circuit_open():
            _log.debug("%s provider: circuit open, skipping", self.name)
            return None
        if sanitize:
            prompt = self._sanitize(prompt)
        try:
            out = self._complete_impl(prompt, max_tokens=max_tokens, timeout=timeout)
        except Exception as exc:  # never raise out of complete()
            _log.debug("%s provider raised: %s", self.name, exc)
            self._record_failure()
            return None
        if out is None:
            self._record_failure()
        else:
            self._record_success()
        return out

    @abstractmethod
    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None: ...


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider (BYO ANTHROPIC_API_KEY)."""

    name = "anthropic"

    def __init__(self, model: str = "claude-haiku-4-5-20251001", auth_token: str | None = None):
        super().__init__()
        self.model = model
        self._auth = auth_token

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        try:
            import anthropic
        except ImportError:
            _log.debug("anthropic SDK not installed")
            return None
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
        return text if 5 < len(text) < 5000 else None


def _openai_complete(
    *,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: float,
    api_key: str | None = None,
    base_url: str | None = None,
    log_label: str = "OpenAI",
) -> str | None:
    try:
        import openai
    except ImportError:
        _log.debug("openai SDK not installed (needed for %s provider)", log_label)
        return None
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
    return text if 5 < len(text) < 5000 else None


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (works with OpenAI / Azure OpenAI)."""

    name = "openai"

    def __init__(
        self, model: str = "gpt-4o-mini", auth_token: str | None = None, base_url: str | None = None
    ):
        super().__init__()
        self.model = model
        self._auth = auth_token
        self.base_url = base_url
        if base_url:
            require_https(base_url, "OPENAI_BASE_URL")

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        return _openai_complete(
            model=self.model,
            prompt=prompt,
            max_tokens=max_tokens,
            timeout=timeout,
            api_key=self._auth,
            base_url=self.base_url,
            log_label="OpenAI",
        )


class GenericHTTPProvider(LLMProvider):
    """Generic OpenAI-compatible HTTP endpoint (Ollama, vLLM, Together, LM Studio)."""

    name = "generic"

    def __init__(
        self, base_url: str | None = None, model: str | None = None, auth_token: str | None = None
    ):
        super().__init__()
        self.base_url = base_url or os.environ.get(
            "GRADATA_LLM_BASE_URL", "http://localhost:11434/v1"
        )
        self.model = model or env_str("GRADATA_LLM_MODEL", "llama3")
        self._auth = auth_token or os.environ.get("GRADATA_LLM_AUTH", "")
        require_https(self.base_url, "GRADATA_LLM_BASE_URL")

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        return _openai_complete(
            model=self.model,
            prompt=prompt,
            max_tokens=max_tokens,
            timeout=timeout,
            api_key=self._auth or "local",
            base_url=self.base_url,
            log_label="Generic HTTP",
        )


class CLIProvider(LLMProvider):
    """BYO-CLI provider — shells to a local CLI (claude / codex / gemini).

    Reuses the user's existing Max-plan OAuth or ChatGPT Plus subscription.
    No API key required. Mirrors ``rule_synthesizer._try_claude_cli`` pattern.

    Selection order for ``cli_name``:
      1. explicit constructor arg
      2. ``GRADATA_LLM_CLI`` env var
      3. ``claude`` if on PATH
      4. ``codex`` if on PATH
      5. ``gemini`` if on PATH
    """

    name = "cli"

    def __init__(self, cli_name: str | None = None, model: str | None = None):
        super().__init__()
        self.cli_name = cli_name or env_str("GRADATA_LLM_CLI", "") or self._auto_detect()
        self.model = model or env_str("GRADATA_LLM_CLI_MODEL", "")

    @staticmethod
    def _auto_detect() -> str | None:
        for candidate in ("claude", "codex", "gemini"):
            if shutil.which(candidate):
                return candidate
        return None

    def _build_argv(self, prompt: str) -> list[str] | None:
        if not self.cli_name:
            return None
        exe = shutil.which(self.cli_name)
        if not exe:
            return None
        if self.cli_name == "claude":
            argv = [exe, "-p", prompt, "--output-format", "text"]
            if self.model:
                argv[3:3] = ["--model", self.model]
            return argv
        if self.cli_name == "codex":
            model = self.model or "gpt-5.5"
            return [
                exe,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "-m",
                model,
                prompt,
            ]
        if self.cli_name == "gemini":
            argv = [exe, "-p", prompt]
            if self.model:
                argv[2:2] = ["-m", self.model]
            return argv
        # Unknown CLI — best-effort generic shape
        return [exe, "-p", prompt]

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        argv = self._build_argv(prompt)
        if argv is None:
            _log.debug("CLI provider: no CLI binary available")
            return None
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=max(timeout, 60.0),
                check=False,
                encoding="utf-8",
                stdin=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            _log.debug("CLI %s invocation failed: %s", self.cli_name, exc)
            return None
        if proc.returncode != 0:
            _log.debug(
                "CLI %s returned %d: %s", self.cli_name, proc.returncode, (proc.stderr or "")[:200]
            )
            return None
        out = (proc.stdout or "").strip()
        return out or None


class GradataCloudProvider(LLMProvider):
    """Cloud-Paid mode — POSTs to a Gradata-hosted relay.

    Server holds the LLM API key. Billing flows through the Gradata
    subscription. Local SDK only needs ``GRADATA_API_KEY`` and an endpoint.

    Env contract:
      * ``GRADATA_API_KEY``    — bearer token
      * ``GRADATA_ENDPOINT``   — base URL (default: https://api.gradata.cloud)
      * Path: ``/meta-rules/synthesize``
    """

    name = "cloud"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        super().__init__()
        self._auth = api_key or env_str("GRADATA_API_KEY", "")
        self.endpoint = (
            endpoint or env_str("GRADATA_ENDPOINT", "https://api.gradata.cloud")
        ).rstrip("/")
        require_https(self.endpoint, "GRADATA_ENDPOINT")

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        if not self._auth:
            _log.debug("Cloud provider: GRADATA_API_KEY not set")
            return None
        url = f"{self.endpoint}/meta-rules/synthesize"
        payload = json.dumps({"prompt": prompt, "max_tokens": max_tokens}).encode()
        headers = {
            "Authorization": f"Bearer {self._auth}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 402:
                _log.warning("Gradata Cloud: 402 Payment Required (quota exhausted)")
                return None
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                _log.warning("Gradata Cloud: 429 rate-limited (Retry-After=%s)", retry_after)
                return None
            _log.debug("Gradata Cloud HTTPError %s", exc)
            return None
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            _log.debug("Gradata Cloud request failed: %s", exc)
            return None
        text = (body.get("text") or body.get("completion") or "").strip()
        return text or None


class GoogleGemmaProvider(LLMProvider):
    """Google's native Gemma API (free tier — uses GRADATA_GEMMA_API_KEY).

    The OpenAI-compat endpoint rejects AQ. keys, so we use the native
    ``generativelanguage.googleapis.com/.../generateContent`` shape.
    """

    name = "gemma"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        super().__init__()
        self._auth = api_key or env_str("GRADATA_GEMMA_API_KEY", "")
        self.model = model or env_str("GRADATA_GEMMA_MODEL", "gemma-3-27b-it")

    def _complete_impl(self, prompt: str, *, max_tokens: int, timeout: float) -> str | None:
        if not self._auth:
            return None
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3},
            }
        ).encode()
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._auth}
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
            text = body["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            OSError,
            KeyError,
            json.JSONDecodeError,
            IndexError,
        ) as exc:
            _log.debug("Gemma native call failed: %s", exc)
            return None
        return text if 5 < len(text) < 5000 else None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "generic": GenericHTTPProvider,
    "cli": CLIProvider,
    "cloud": GradataCloudProvider,
    "gemma": GoogleGemmaProvider,
}


def _resolve_auto() -> str | None:
    """Auto-resolve preferred provider based on environment.

    Order: cli (claude/codex on PATH) → anthropic (ANTHROPIC_API_KEY) →
    openai (OPENAI_API_KEY or GRADATA_LLM_KEY) → cloud (GRADATA_API_KEY) → None.
    """
    if shutil.which("claude") or shutil.which("codex"):
        return "cli"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("GRADATA_LLM_KEY"):
        return "openai"
    if os.environ.get("GRADATA_API_KEY"):
        return "cloud"
    if os.environ.get("GRADATA_GEMMA_API_KEY"):
        return "gemma"
    return None


def get_provider(name: str | None = None, **kwargs) -> LLMProvider | None:
    """Get an LLM provider by name (or auto-resolve from environment).

    Args:
        name: One of ``anthropic``, ``openai``, ``generic``, ``cli``,
              ``cloud``, ``gemma``, or ``auto``. Defaults to
              ``GRADATA_LLM_PROVIDER`` env var, then ``auto``.
        **kwargs: Forwarded to the provider constructor.

    Returns:
        Provider instance, or ``None`` if ``auto`` couldn't find any
        configured backend (callers fall back to deterministic synthesis).
    """
    name = name or os.environ.get("GRADATA_LLM_PROVIDER", "auto")
    name = name.lower()
    if name == "auto":
        resolved = _resolve_auto()
        if resolved is None:
            return None
        name = resolved
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {name!r}. Choose from: {list(_PROVIDERS)}")
    try:
        return cls(**kwargs)
    except ValueError as exc:
        # E.g. require_https failure on a misconfigured base URL — degrade gracefully
        _log.warning("Provider %s rejected its config: %s", name, exc)
        return None
