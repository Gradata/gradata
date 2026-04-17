"""Optional LLM-enhanced principle synthesis for meta-rules.

When an OpenAI-compatible API key and base URL are configured,
synthesises natural-language behavioral principles from grouped lessons.
Falls back gracefully to None when not configured or on error — callers
use the existing regex-based synthesis as fallback.

Configuration via environment variables:
    GRADATA_LLM_BASE  — base URL for the chat completions API (required)
    GRADATA_LLM_MODEL — model identifier (default: "gpt-4o-mini")
    GRADATA_LLM_KEY   — API key (required)

Zero new dependencies: uses only ``urllib.request`` + ``json``.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata._types import Lesson

log = logging.getLogger(__name__)

_DEFAULT_BASE = os.environ.get("GRADATA_LLM_BASE", "")
_DEFAULT_MODEL = os.environ.get("GRADATA_LLM_MODEL", "gpt-4o-mini")
_MAX_RETRIES = 1
_RETRY_DELAY = 2.0

# Circuit breaker: skip all LLM calls after first failure in this process
_circuit_open = False


def synthesise_principle_llm(
    lessons: list[Lesson],
    theme: str,
    *,
    api_key: str | None = None,
    api_base: str = _DEFAULT_BASE,
    model: str = _DEFAULT_MODEL,
    timeout: float = 15.0,
) -> str | None:
    """Synthesise a behavioral principle from related lessons via LLM.

    Returns a 1-2 sentence actionable principle, or ``None`` if the LLM
    is unavailable (no key, network error, timeout, bad response).
    Callers should fall back to regex-based synthesis when this returns None.

    Args:
        lessons: Grouped lessons (typically 3+, all PATTERN or RULE).
        theme: The category/theme label for these lessons.
        api_key: API key for the LLM service. None = skip LLM entirely.
        api_base: Base URL for the chat completions API.
        model: Model identifier.
        timeout: HTTP request timeout in seconds.
    """
    global _circuit_open
    if _circuit_open or not api_key or not api_key.strip() or not lessons:
        return None

    # Require explicit base URL configuration — never call a hardcoded endpoint
    if not api_base or not api_base.strip():
        log.debug("LLM synthesis skipped: no api_base configured (set GRADATA_LLM_BASE)")
        return None

    # SSRF / bearer-key exfil guard: refuse HTTP to non-local hosts
    from gradata._http import require_https
    try:
        require_https(api_base, "GRADATA_LLM_BASE")
    except ValueError as exc:
        log.error("LLM synthesis refused — %s", exc)
        return None

    # Build bullet list of lesson descriptions
    bullets = []
    for lesson in lessons[:10]:  # Cap at 10 to limit prompt size
        desc = lesson.description
        if desc:
            bullets.append(f"- {desc}")

    if not bullets:
        return None

    bullet_text = "\n".join(bullets)
    prompt = (
        f"Given these {len(bullets)} user corrections all related to \"{theme}\":\n"
        f"{bullet_text}\n\n"
        "Write ONE actionable behavioral principle (1-2 sentences) that captures the pattern.\n"
        "Format: \"When [context], [do X] instead of [Y].\"\n"
        "Do not list individual words. Focus on the behavioral change.\n"
        "Return ONLY the principle, no preamble."
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150,
        "temperature": 0.3,
    }).encode()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(_MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                f"{api_base}/chat/completions",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())

            content = body["choices"][0]["message"]["content"].strip()
            # Basic validation: must be a real sentence
            if len(content) < 15 or len(content) > 500:
                log.debug("LLM principle too short/long (%d chars), skipping", len(content))
                return None

            log.debug("LLM-synthesised principle for theme '%s': %s", theme, content[:80])
            return content

        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError,
                json.JSONDecodeError, IndexError) as exc:
            if attempt < _MAX_RETRIES:
                log.debug("LLM synthesis attempt %d failed (%s), retrying...", attempt + 1, exc)
                time.sleep(_RETRY_DELAY)
            else:
                log.debug("LLM synthesis failed after %d attempts: %s — circuit open", _MAX_RETRIES + 1, exc)
                _circuit_open = True
                return None

    return None  # pragma: no cover — loop always returns on final attempt
