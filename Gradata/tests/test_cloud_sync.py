"""Tests for gradata.cloud.sync — opt-in cloud telemetry client."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata.cloud.sync import (
    CloudClient,
    CloudConfig,
    TelemetryPayload,
    load_config,
    save_config,
    sync_metrics,
)


def _payload(brain_id: str = "test", session: int = 1) -> TelemetryPayload:
    return TelemetryPayload(
        brain_id=brain_id,
        session=session,
        window_size=10,
        sample_size=5,
        rewrite_rate=0.2,
        edit_distance_avg=12.5,
        correction_density=0.1,
        blandness_score=0.3,
        rule_success_rate=0.8,
        rule_misfire_rate=0.05,
        rules_active=3,
        rules_graduated=1,
    )


class TestCloudConfig:
    def test_default_config_is_disabled(self):
        cfg = CloudConfig()
        assert cfg.sync_enabled is False
        assert cfg.token == ""
        assert cfg.contribute_corpus is False

    def test_load_config_missing_file_returns_defaults(self, tmp_path: Path):
        cfg = load_config(tmp_path)
        assert cfg.sync_enabled is False
        assert cfg.token == ""

    def test_save_then_load_roundtrip(self, tmp_path: Path):
        original = CloudConfig(
            sync_enabled=True,
            token="test-token-123",
            contribute_corpus=True,
        )
        save_config(tmp_path, original)
        loaded = load_config(tmp_path)
        assert loaded.sync_enabled is True
        assert loaded.token == "test-token-123"
        assert loaded.contribute_corpus is True

    def test_load_handles_corrupt_file(self, tmp_path: Path):
        (tmp_path / "cloud-config.json").write_text("not json {", encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg.sync_enabled is False  # falls back to defaults


class TestCloudClient:
    def test_client_disabled_by_default(self, tmp_path: Path):
        client = CloudClient(tmp_path)
        assert client.enabled is False

    def test_client_disabled_without_token(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="")  # no token
        client = CloudClient(tmp_path, cfg)
        assert client.enabled is False

    def test_client_enabled_with_sync_and_token(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="abc123")
        client = CloudClient(tmp_path, cfg)
        assert client.enabled is True

    def test_sync_metrics_skipped_when_disabled(self, tmp_path: Path):
        client = CloudClient(tmp_path)
        result = client.sync_metrics(_payload())
        assert result is False

    def test_sync_metrics_posts_when_enabled(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="abc")
        client = CloudClient(tmp_path, cfg)

        with patch.object(client, "_post", return_value={"ok": True}) as mock_post:
            result = client.sync_metrics(_payload())

        assert result is True
        mock_post.assert_called_once()
        call_path = mock_post.call_args[0][0]
        assert call_path == "/api/v1/telemetry/metrics"

    def test_sync_metrics_updates_last_sync_at_on_success(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="abc")
        client = CloudClient(tmp_path, cfg)

        with patch.object(client, "_post", return_value={}):
            client.sync_metrics(_payload())

        # Reload config to verify persistence
        reloaded = load_config(tmp_path)
        assert reloaded.last_sync_at != ""

    def test_sync_metrics_failure_does_not_update_last_sync(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="abc")
        client = CloudClient(tmp_path, cfg)

        with patch.object(client, "_post", return_value=None):
            result = client.sync_metrics(_payload())

        assert result is False
        reloaded = load_config(tmp_path)
        assert reloaded.last_sync_at == ""

    def test_contribute_corpus_requires_both_flags(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="abc", contribute_corpus=False)
        client = CloudClient(tmp_path, cfg)
        result = client.contribute_corpus([{"pattern": "test"}])
        assert result is False  # corpus flag not set

    def test_contribute_corpus_posts_when_both_flags_set(self, tmp_path: Path):
        cfg = CloudConfig(sync_enabled=True, token="abc", contribute_corpus=True)
        client = CloudClient(tmp_path, cfg)

        with patch.object(client, "_post", return_value={}) as mock_post:
            result = client.contribute_corpus([{"pattern": "test"}])

        assert result is True
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "/v1/corpus/contribute"


class TestConvenienceSync:
    def test_convenience_wrapper_returns_false_when_disabled(self, tmp_path: Path):
        result = sync_metrics(tmp_path, _payload())
        assert result is False

    def test_convenience_wrapper_never_raises(self, tmp_path: Path):
        # Even with corrupt config, must not raise
        (tmp_path / "cloud-config.json").write_text("}{", encoding="utf-8")
        result = sync_metrics(tmp_path, _payload())
        assert result is False


class TestPayload:
    def test_payload_has_sent_at_timestamp(self):
        p = _payload()
        assert p.sent_at  # auto-populated
        assert "T" in p.sent_at  # ISO format

    def test_payload_serializes_to_json(self):
        from dataclasses import asdict

        p = _payload()
        data = asdict(p)
        json_str = json.dumps(data)
        assert "brain_id" in json_str
        assert "edit_distance_avg" in json_str
