"""HTTPS-at-the-boundary enforcement. Call ``require_https(url)`` before any
``urllib.request.Request`` or third-party client call. Stdlib only; localhost/loopback
exempted so local LLM servers (Ollama/vLLM/LM Studio) work."""

from __future__ import annotations

from urllib.parse import urlparse

# Hostnames that are allowed over plain HTTP (never routable off-host).
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def require_https(url: str, label: str = "URL") -> None:
    """Raise ``ValueError`` if *url* uses HTTP and is not a loopback address.

    Args:
        url:   The URL to validate.
        label: Human-readable label for the URL (used in the error message).

    Raises:
        ValueError: If the URL scheme is ``http://`` and the host is not
                    localhost / 127.0.0.1 / ::1.

    Examples::

        require_https("https://api.example.com/v1")  # OK — no-op
        require_https("http://localhost:11434/v1")    # OK — loopback exempted
        require_https("http://evil.com/steal")        # raises ValueError
    """
    if not url:
        return  # Empty string: caller's validation problem, not ours.

    parsed = urlparse(url)
    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower()
        if host not in _LOCAL_HOSTS:
            raise ValueError(f"{label} must use HTTPS for non-local hosts, got: {url!r}")
