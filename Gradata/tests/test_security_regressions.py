"""Security regression tests — HTTPS enforcement at all network boundaries.

Sibling of ae423a7 (cloud->local rule injection fix).
Covers 5 patched sites:
  C1a — llm_synthesizer.synthesise_principle_llm  (GRADATA_LLM_BASE)
  C1b — meta_rules._call_llm_for_synthesis        (GRADATA_LLM_BASE)
  C1c — llm_provider.GenericHTTPProvider          (GRADATA_LLM_BASE_URL)
  H1  — cloud/sync.CloudClient._post              (api_base)
  HIGH — _core._cloud_sync_session                (api_url from config.toml)
  REF — cloud/client.CloudClient                  (GRADATA_ENDPOINT)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Short fake credential values — intentionally under 8 chars so the
# secret scanner does not flag them as real credentials.
_FK = "sk-test"  # fake key, 7 chars
_FT = "brr-x"  # fake bearer, 5 chars


# ---------------------------------------------------------------------------
# Shared helper: require_https
# ---------------------------------------------------------------------------


class TestRequireHttps:
    """Unit tests for the shared _http.require_https helper."""

    def test_https_passes(self):
        from gradata._http import require_https

        require_https("https://api.example.com/v1", "test")

    def test_http_localhost_passes(self):
        from gradata._http import require_https

        require_https("http://localhost:11434/v1", "test")

    def test_http_127_passes(self):
        from gradata._http import require_https

        require_https("http://127.0.0.1:8080/v1", "test")

    def test_http_ipv6_loopback_passes(self):
        from gradata._http import require_https

        # RFC 2732: IPv6 literals in URLs must be bracketed
        require_https("http://[::1]:8080/v1", "test")

    def test_empty_url_passes(self):
        from gradata._http import require_https

        require_https("", "test")

    def test_http_remote_raises(self):
        from gradata._http import require_https

        with pytest.raises(ValueError, match="HTTPS"):
            require_https("http://evil.com/steal", "test")

    def test_label_appears_in_error(self):
        from gradata._http import require_https

        with pytest.raises(ValueError, match="GRADATA_LLM_BASE"):
            require_https("http://attacker.internal/v1", "GRADATA_LLM_BASE")


# ---------------------------------------------------------------------------
# C1a — llm_synthesizer
# ---------------------------------------------------------------------------


class TestLLMSynthesizerHttpsGuard:
    """C1a: synthesise_principle_llm refuses HTTP to non-local hosts."""

    def _make_lessons(self):
        lesson = MagicMock()
        lesson.description = "test lesson"
        return [lesson]

    def test_http_remote_returns_none(self):
        from gradata.enhancements.llm_synthesizer import synthesise_principle_llm

        result = synthesise_principle_llm(
            self._make_lessons(),
            theme="style",
            api_key=_FK,
            api_base="http://evil.com/v1",
        )
        assert result is None

    def test_https_remote_reaches_network(self):
        """HTTPS URL passes the guard and the function issues a real request (mocked)."""
        from gradata.enhancements import llm_synthesizer

        # Reset module-level circuit breaker so prior test failures don't bleed over.
        llm_synthesizer._circuit_open = False  # type: ignore[attr-defined]

        # The function requires 15 <= len(content) <= 500 to return non-None.
        _principle = "When writing, use short sentences instead of long compound ones."
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = (
                f'{{"choices":[{{"message":{{"content":"{_principle}"}}}}]}}'
            ).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = llm_synthesizer.synthesise_principle_llm(
                self._make_lessons(),
                theme="style",
                api_key=_FK,
                api_base="https://api.openai.com/v1",
            )
        assert result == _principle

    def test_http_localhost_reaches_network(self):
        """Localhost HTTP is allowed (local Ollama / vLLM dev server)."""
        from gradata.enhancements import llm_synthesizer

        llm_synthesizer._circuit_open = False

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = (
                b'{"choices":[{"message":{"content":"Use active voice."}}]}'
            )
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = llm_synthesizer.synthesise_principle_llm(
                self._make_lessons(),
                theme="style",
                api_key="local",
                api_base="http://localhost:11434/v1",
            )
        assert result == "Use active voice."


# ---------------------------------------------------------------------------
# C1b — meta_rules._call_llm_for_synthesis
# ---------------------------------------------------------------------------


class TestMetaRulesHttpsGuard:
    """C1b: _call_llm_for_synthesis raises for HTTP non-local base."""

    def test_http_remote_raises(self, monkeypatch):
        from gradata.enhancements import meta_rules

        monkeypatch.setenv("GRADATA_LLM_KEY", _FK)
        monkeypatch.setenv("GRADATA_LLM_BASE", "http://attacker.internal/v1")
        monkeypatch.setenv("GRADATA_LLM_MODEL", "gpt-4o-mini")

        with pytest.raises((ValueError, RuntimeError)):
            meta_rules._call_llm_for_synthesis("style", ["be concise"])

    def test_https_remote_allowed(self, monkeypatch):
        from gradata.enhancements import meta_rules

        monkeypatch.setenv("GRADATA_LLM_KEY", _FK)
        monkeypatch.setenv("GRADATA_LLM_BASE", "https://api.openai.com/v1")
        monkeypatch.setenv("GRADATA_LLM_MODEL", "gpt-4o-mini")

        # _call_llm_for_synthesis parses body["choices"][0]["message"]["content"]
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"choices":[{"message":{"content":"[{\\"directive\\":\\"Be concise.\\",\\"confidence\\":0.9}]"}}]}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = meta_rules._call_llm_for_synthesis("style", ["be concise"])
        assert "Be concise" in result


# ---------------------------------------------------------------------------
# C1c — llm_provider.GenericHTTPProvider
# ---------------------------------------------------------------------------


class TestGenericHTTPProviderHttpsGuard:
    """C1c: GenericHTTPProvider raises ValueError at construction for HTTP non-local."""

    def test_http_remote_raises_on_init(self):
        from gradata.enhancements.llm_provider import GenericHTTPProvider

        with pytest.raises(ValueError, match="HTTPS"):
            GenericHTTPProvider(base_url="http://evil.com/v1")

    def test_http_localhost_allowed(self):
        from gradata.enhancements.llm_provider import GenericHTTPProvider

        provider = GenericHTTPProvider(base_url="http://localhost:11434/v1")
        assert "localhost" in provider.base_url

    def test_https_remote_allowed(self):
        from gradata.enhancements.llm_provider import GenericHTTPProvider

        provider = GenericHTTPProvider(base_url="https://api.together.xyz/v1")
        assert "together" in provider.base_url

    def test_env_var_http_remote_raises(self, monkeypatch):
        from gradata.enhancements import llm_provider

        monkeypatch.setenv("GRADATA_LLM_BASE_URL", "http://attacker.com/v1")
        with pytest.raises(ValueError, match="HTTPS"):
            llm_provider.GenericHTTPProvider()


# ---------------------------------------------------------------------------
# H1 — cloud/sync.CloudClient._post
# ---------------------------------------------------------------------------


class TestSyncClientHttpsGuard:
    """H1: sync.CloudClient refuses HTTP non-local api_base at construction and in _post."""

    def _make_client(self, api_base: str, tmp_path: Path):
        from gradata.cloud.sync import CloudClient, CloudConfig

        cfg = CloudConfig(sync_enabled=True, api_base=api_base)
        cfg.token = _FT  # noqa: S105 — intentionally short fake value
        return CloudClient(brain_dir=tmp_path, config=cfg)

    def test_http_remote_post_returns_none(self, tmp_path):
        # Constructor now raises before _post is ever reached — stronger guard.
        from gradata.cloud.sync import CloudClient, CloudConfig

        cfg = CloudConfig(sync_enabled=True, api_base="http://evil.com")
        cfg.token = _FT
        with pytest.raises(ValueError, match="HTTPS"):
            CloudClient(brain_dir=tmp_path, config=cfg)

    def test_https_remote_post_attempts_request(self, tmp_path):
        client = self._make_client("https://api.gradata.ai", tmp_path)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"ok": true}'
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = client._post("/telemetry/metrics", {"x": 1})
        assert result == {"ok": True}

    def test_http_localhost_post_attempts_request(self, tmp_path):
        client = self._make_client("http://localhost:8080", tmp_path)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"{}"
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = client._post("/test", {})
        assert result == {}


# ---------------------------------------------------------------------------
# REF — cloud/client.CloudClient constructor
# ---------------------------------------------------------------------------


class TestCloudClientHttpsGuard:
    """REF: cloud/client.CloudClient refuses HTTP endpoint at construction."""

    def test_http_remote_raises(self, tmp_path):
        from gradata.cloud.client import CloudClient

        with pytest.raises(ValueError, match="HTTPS"):
            CloudClient(brain_dir=tmp_path, endpoint="http://evil.com/v1")

    def test_https_remote_accepted(self, tmp_path):
        from gradata.cloud.client import CloudClient

        client = CloudClient(brain_dir=tmp_path, endpoint="https://api.gradata.com/v1")
        assert client.endpoint == "https://api.gradata.com/v1"

    def test_http_localhost_accepted(self, tmp_path):
        from gradata.cloud.client import CloudClient

        client = CloudClient(brain_dir=tmp_path, endpoint="http://localhost:9000/v1")
        assert "localhost" in client.endpoint

    def test_env_var_http_remote_raises(self, tmp_path, monkeypatch):
        from gradata.cloud import client as cloud_client_mod

        monkeypatch.setenv("GRADATA_ENDPOINT", "http://attacker.com/v1")
        with pytest.raises(ValueError, match="HTTPS"):
            cloud_client_mod.CloudClient(brain_dir=tmp_path)


# ---------------------------------------------------------------------------
# HIGH — _core._cloud_sync_session api_url guard
# ---------------------------------------------------------------------------


class TestCoreSyncSessionHttpsGuard:
    """HIGH: _cloud_sync_session returns early when api_url is HTTP non-local."""

    def test_http_remote_api_url_aborts_sync(self, tmp_path, monkeypatch, caplog):
        """When config.toml contains an http:// api_url, sync aborts before any
        network call — bearer credential must not be transmitted."""
        import logging

        monkeypatch.setenv("GRADATA_API_KEY", _FK)

        with patch("gradata._core._parse_toml_cloud") as mock_toml:
            mock_toml.return_value = {
                "api_key": _FK,
                "api_url": "http://attacker.internal/v1",
                "brain_id": "test-brain",
            }
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("gradata.cloud.sync.CloudClient") as mock_sync:
                    from gradata import _core

                    brain = MagicMock()
                    brain.dir = tmp_path
                    brain.db_path = tmp_path / "system.db"

                    with caplog.at_level(logging.ERROR, logger="gradata._core"):
                        _core._cloud_sync_session(
                            brain=brain,
                            session=1,
                            session_corrections=[],
                            all_lessons=[],
                            result={},
                        )

                    # SyncClient must NOT be instantiated — sync was aborted
                    mock_sync.assert_not_called()

        assert any("HTTPS" in r.message or "aborted" in r.message for r in caplog.records)
