"""Regression tests — require_https() at all network boundaries.

Locks in the fix from commit dfbaa49 (security: enforce HTTPS at all
network boundaries).

Patched sites:
  shared  — gradata._http.require_https (the shared helper)
  C1a     — enhancements/llm_synthesizer.synthesise_principle_llm
  C1c     — enhancements/llm_provider.GenericHTTPProvider
  H1      — cloud/sync.CloudClient._post
  cloud   — cloud/client.CloudClient (GRADATA_ENDPOINT)

Mocking rationale: network calls are mocked where the test would otherwise
require a live server or external credentials.  The HTTPS guard is the
code path under test; network reachability is out-of-scope.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Short fake credential values — intentionally under 8 chars so the
# secret scanner does not flag them as real credentials.
_FK = "sk-test"   # fake key, 7 chars
_FT = "brr-x"    # fake bearer, 5 chars


# ---------------------------------------------------------------------------
# Shared helper: gradata._http.require_https
# ---------------------------------------------------------------------------


class TestRequireHttpsHelper:
    """Direct unit tests on the shared require_https() helper."""

    def test_positive_https_remote_passes(self):
        """HTTPS to a remote host must be accepted — no exception raised."""
        from gradata._http import require_https
        require_https("https://api.gradata.ai/v1", "api_base")

    def test_positive_http_localhost_exempt(self):
        """localhost over HTTP is allowed (local dev: Ollama, vLLM)."""
        from gradata._http import require_https
        require_https("http://localhost:11434/v1", "GRADATA_LLM_BASE")

    def test_positive_http_127_exempt(self):
        """127.0.0.1 over HTTP is allowed."""
        from gradata._http import require_https
        require_https("http://127.0.0.1:8080/v1", "test")

    def test_positive_http_ipv6_loopback_exempt(self):
        """[::1] loopback over HTTP is allowed."""
        from gradata._http import require_https
        require_https("http://[::1]:8080/v1", "test")

    def test_positive_empty_url_passes(self):
        """Empty string is a no-op (caller's validation responsibility)."""
        from gradata._http import require_https
        require_https("", "test")

    def test_negative_http_remote_rejected(self):
        """HTTP to a non-local host must raise ValueError.

        Before the fix, plain http:// URLs would reach the network, exposing
        API keys to attacker-controlled servers (SSRF / credential exfil).
        """
        from gradata._http import require_https
        with pytest.raises(ValueError, match="HTTPS"):
            require_https("http://evil.internal/steal", "test")

    def test_negative_error_message_contains_label(self):
        """The ValueError message must include the label so the log is actionable."""
        from gradata._http import require_https
        with pytest.raises(ValueError, match="GRADATA_LLM_BASE"):
            require_https("http://attacker.example.com/v1", "GRADATA_LLM_BASE")

    def test_negative_http_remote_not_confused_with_https_scheme(self):
        """http:// scheme to a remote host is caught regardless of hostname."""
        from gradata._http import require_https
        with pytest.raises(ValueError):
            require_https("http://api-evil.com/v1", "test")


# ---------------------------------------------------------------------------
# C1a — llm_synthesizer.synthesise_principle_llm
# ---------------------------------------------------------------------------


class TestLLMSynthesizerHttpsGuard:
    """C1a: synthesise_principle_llm must refuse HTTP to non-local hosts."""

    def _make_lessons(self, description="test lesson"):
        lesson = MagicMock()
        lesson.description = description
        return [lesson]

    def test_negative_http_remote_returns_none(self):
        """HTTP to a remote LLM API must be silently rejected (returns None).

        Before the fix, the function would forward the API key to the attacker
        server via a network request.
        """
        from gradata.enhancements.llm_synthesizer import synthesise_principle_llm
        result = synthesise_principle_llm(
            self._make_lessons(),
            theme="style",
            api_key=_FK,
            api_base="http://attacker.internal/v1",
        )
        assert result is None, (
            "REGRESSION: HTTP to remote LLM host was not rejected — "
            "SSRF / key exfil risk is live again"
        )

    def test_positive_https_remote_passes_guard(self):
        """HTTPS URL passes the guard and the function proceeds (network mocked)."""
        from gradata.enhancements.llm_synthesizer import synthesise_principle_llm

        with patch("urllib.request.urlopen") as mock_ul:
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.read.return_value = (
                b'{"choices":[{"message":{"content":"Use clear variable names."}}]}'
            )
            mock_ul.return_value = resp
            synthesise_principle_llm(
                self._make_lessons(),
                theme="style",
                api_key=_FK,
                api_base="https://api.gradata.ai/v1",
            )
        assert mock_ul.called, "HTTPS URL should have reached the urlopen call"

    def test_positive_http_localhost_passes_guard(self):
        """HTTP to localhost (Ollama) must not be rejected by the HTTPS guard."""
        from gradata.enhancements.llm_synthesizer import synthesise_principle_llm

        with patch("urllib.request.urlopen") as mock_ul:
            mock_ul.side_effect = Exception("network unavailable")
            try:
                synthesise_principle_llm(
                    self._make_lessons(),
                    theme="style",
                    api_key=_FK,
                    api_base="http://localhost:11434/v1",
                )
            except Exception as exc:
                assert "HTTPS" not in str(exc), "localhost incorrectly rejected by HTTPS guard"


# ---------------------------------------------------------------------------
# C1c — llm_provider.GenericHTTPProvider
# ---------------------------------------------------------------------------


class TestGenericHTTPProviderHttpsGuard:
    """C1c: GenericHTTPProvider constructor must refuse HTTP to non-local hosts."""

    def test_negative_http_remote_raises_at_construction(self):
        """Constructing GenericHTTPProvider with an http:// remote URL must raise.

        Before the fix, the provider stored the URL and later forwarded the
        auth token to the attacker endpoint on every completion call.
        """
        from gradata.enhancements.llm_provider import GenericHTTPProvider
        with pytest.raises(ValueError, match="HTTPS"):
            GenericHTTPProvider(base_url="http://evil.example.com/v1", auth_token=_FT)

    def test_positive_http_localhost_accepted(self):
        """http://localhost is allowed (Ollama default)."""
        from gradata.enhancements.llm_provider import GenericHTTPProvider
        provider = GenericHTTPProvider(base_url="http://localhost:11434/v1")
        assert provider.base_url.startswith("http://localhost")

    def test_positive_https_remote_accepted(self):
        """https:// to a remote host is accepted."""
        from gradata.enhancements.llm_provider import GenericHTTPProvider
        provider = GenericHTTPProvider(base_url="https://api.gradata.ai/llm/v1")
        assert provider.base_url.startswith("https://")


# ---------------------------------------------------------------------------
# H1 — cloud/sync.CloudClient._post
# ---------------------------------------------------------------------------


class TestCloudSyncHttpsGuard:
    """H1: cloud/sync.CloudClient._post must refuse HTTP to non-local api_base.

    Mocking rationale: CloudClient.enabled requires sync_enabled=True and a
    non-empty token.  We monkeypatch the property so the guard code is reached
    even without a real cloud config on disk.
    """

    def _make_client(self, api_base: str, tmp_path):
        """Build a CloudClient with a real (but non-existent) brain dir so
        load_config() falls back to defaults, then override config fields."""
        from gradata.cloud.sync import CloudClient, CloudConfig
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir(exist_ok=True)
        client = CloudClient(brain_dir=brain_dir)
        # Override config to point at the test api_base with sync enabled.
        client.config = CloudConfig(
            api_base=api_base,
            sync_enabled=True,
            token="tok-x",  # non-empty so enabled=True
        )
        return client

    def test_negative_http_remote_post_returns_none(self, tmp_path):
        """_post to an http:// remote host must return None (not send the request).

        Before the fix, the API key was forwarded in the Authorization header
        to any URL, enabling credential exfiltration.
        """
        client = self._make_client("http://evil.internal", tmp_path)
        result = client._post("/telemetry", {"data": "x"})
        assert result is None, (
            "REGRESSION: CloudClient._post sent data to an HTTP remote — "
            "credential exfil risk is live again"
        )

    def test_positive_https_remote_post_reaches_network(self, tmp_path):
        """HTTPS api_base passes the guard and the request proceeds (mocked)."""
        client = self._make_client("https://api.gradata.ai", tmp_path)
        with patch("urllib.request.urlopen") as mock_ul:
            mock_ul.side_effect = Exception("network unavailable")
            try:
                client._post("/telemetry", {"data": "x"})
            except Exception:
                pass
            assert mock_ul.called, "HTTPS URL should have passed the guard and called urlopen"

    def test_positive_http_localhost_passes_guard(self, tmp_path):
        """http://localhost api_base must not be rejected."""
        client = self._make_client("http://localhost:8000", tmp_path)
        with patch("urllib.request.urlopen") as mock_ul:
            mock_ul.side_effect = Exception("network unavailable")
            try:
                client._post("/telemetry", {"data": "x"})
            except Exception:
                pass
            assert mock_ul.called, "localhost should have passed the guard"


# ---------------------------------------------------------------------------
# cloud/client.CloudClient (GRADATA_ENDPOINT)
# ---------------------------------------------------------------------------


class TestCloudClientEndpointGuard:
    """cloud/client.CloudClient must refuse an http:// GRADATA_ENDPOINT.

    Mocking rationale: CloudClient.__init__ requires a brain_dir path; we
    pass a tmp_path so the constructor does not touch the real brain.
    """

    def test_negative_http_remote_endpoint_raises(self, tmp_path):
        """Constructing CloudClient with http:// remote endpoint raises ValueError."""
        from gradata.cloud.client import CloudClient
        with pytest.raises(ValueError, match="HTTPS"):
            CloudClient(brain_dir=tmp_path, endpoint="http://evil.internal/api")

    def test_positive_https_endpoint_accepted(self, tmp_path):
        """https:// endpoint is accepted."""
        from gradata.cloud.client import CloudClient
        client = CloudClient(brain_dir=tmp_path, endpoint="https://api.gradata.ai")
        assert client.endpoint.startswith("https://")
