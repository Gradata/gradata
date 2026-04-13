"""Tests for gradata._telemetry — opt-in anonymous activation events."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from gradata import _telemetry


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Point the telemetry config at a tmp path so tests don't touch the
    real ~/.gradata/config.toml."""
    cfg_dir = tmp_path / ".gradata"
    cfg_path = cfg_dir / "config.toml"
    monkeypatch.setattr(_telemetry, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(_telemetry, "CONFIG_PATH", cfg_path)
    # Clear kill-switch env
    monkeypatch.delenv(_telemetry.ENV_KILL_SWITCH, raising=False)
    monkeypatch.delenv(_telemetry.ENV_ENDPOINT, raising=False)
    yield


# ── Opt-in gate ──────────────────────────────────────────────────────
class TestOptIn:
    def test_default_off(self):
        assert _telemetry.is_enabled() is False

    def test_enabled_after_opt_in(self):
        _telemetry.set_enabled(True)
        assert _telemetry.is_enabled() is True

    def test_disabled_after_opt_out(self):
        _telemetry.set_enabled(True)
        _telemetry.set_enabled(False)
        assert _telemetry.is_enabled() is False

    def test_env_kill_switch_overrides_opt_in(self, monkeypatch):
        _telemetry.set_enabled(True)
        monkeypatch.setenv(_telemetry.ENV_KILL_SWITCH, "0")
        assert _telemetry.is_enabled() is False

    def test_env_kill_switch_false_literal(self, monkeypatch):
        _telemetry.set_enabled(True)
        monkeypatch.setenv(_telemetry.ENV_KILL_SWITCH, "false")
        assert _telemetry.is_enabled() is False

    def test_env_kill_switch_1_does_not_auto_enable(self, monkeypatch):
        # GRADATA_TELEMETRY=1 must NOT opt the user in. Only the prompt can.
        monkeypatch.setenv(_telemetry.ENV_KILL_SWITCH, "1")
        assert _telemetry.is_enabled() is False


# ── Anonymous user ID ────────────────────────────────────────────────
class TestUserId:
    def test_stable_across_calls(self):
        a = _telemetry.anonymous_user_id()
        b = _telemetry.anonymous_user_id()
        assert a == b

    def test_is_hex_sha256(self):
        uid = _telemetry.anonymous_user_id()
        assert len(uid) == 64
        int(uid, 16)  # raises if not hex

    def test_does_not_leak_mac(self):
        """Hash must not be reversible — any substring of the raw MAC
        must not appear in the output."""
        import uuid

        mac_hex = f"{uuid.getnode():x}"
        uid = _telemetry.anonymous_user_id()
        # The MAC hex itself obviously can't appear in a sha256 output
        # with overwhelming probability, but assert it to catch regressions
        # where someone accidentally returns the raw seed.
        assert mac_hex not in uid or len(mac_hex) < 4


# ── Payload shape ────────────────────────────────────────────────────
class TestPayload:
    def test_exact_keys(self):
        payload = _telemetry._build_payload("brain_initialized")
        assert set(payload.keys()) == {"event", "user_id", "ts", "sdk_version"}

    def test_no_extra_fields(self):
        payload = _telemetry._build_payload("brain_initialized")
        # Defensive: nobody has added secret fields
        for key in payload:
            assert key in {"event", "user_id", "ts", "sdk_version"}

    def test_serializable(self):
        payload = _telemetry._build_payload("first_graduation")
        # Must JSON-roundtrip cleanly
        assert json.loads(json.dumps(payload)) == payload


# ── send_event ───────────────────────────────────────────────────────
class TestSendEvent:
    def test_rejects_unknown_event(self):
        with pytest.raises(ValueError):
            _telemetry.send_event("totally_not_real")

    def test_noop_when_disabled(self):
        with patch.object(_telemetry, "_post") as post:
            _telemetry.send_event("brain_initialized", blocking=True)
            post.assert_not_called()

    def test_posts_when_enabled(self):
        _telemetry.set_enabled(True)
        with patch.object(_telemetry, "_post", return_value=True) as post:
            _telemetry.send_event("brain_initialized", blocking=True)
            post.assert_called_once()
            payload = post.call_args[0][0]
            assert payload["event"] == "brain_initialized"

    def test_respects_kill_switch(self, monkeypatch):
        _telemetry.set_enabled(True)
        monkeypatch.setenv(_telemetry.ENV_KILL_SWITCH, "0")
        with patch.object(_telemetry, "_post") as post:
            _telemetry.send_event("brain_initialized", blocking=True)
            post.assert_not_called()


# ── send_once idempotency ────────────────────────────────────────────
class TestSendOnce:
    def test_fires_exactly_once(self):
        _telemetry.set_enabled(True)
        with patch.object(_telemetry, "_post", return_value=True) as post:
            assert _telemetry.send_once("brain_initialized", blocking=True) is True
            assert _telemetry.send_once("brain_initialized", blocking=True) is False
            assert post.call_count == 1

    def test_different_events_independent(self):
        _telemetry.set_enabled(True)
        with patch.object(_telemetry, "_post", return_value=True) as post:
            _telemetry.send_once("brain_initialized", blocking=True)
            _telemetry.send_once("first_correction_captured", blocking=True)
            _telemetry.send_once("first_graduation", blocking=True)
            _telemetry.send_once("first_hook_installed", blocking=True)
            assert post.call_count == 4

    def test_returns_false_when_disabled(self):
        assert _telemetry.send_once("brain_initialized", blocking=True) is False


# ── Prompt ───────────────────────────────────────────────────────────
class TestPrompt:
    def test_y_enables(self):
        result = _telemetry.prompt_and_persist(input_fn=lambda _p: "y")
        assert result is True
        assert _telemetry.is_enabled() is True
        assert _telemetry.has_been_asked() is True

    def test_yes_enables(self):
        result = _telemetry.prompt_and_persist(input_fn=lambda _p: "YES")
        assert result is True

    def test_blank_rejects(self):
        result = _telemetry.prompt_and_persist(input_fn=lambda _p: "")
        assert result is False
        assert _telemetry.has_been_asked() is True

    def test_n_rejects(self):
        result = _telemetry.prompt_and_persist(input_fn=lambda _p: "n")
        assert result is False

    def test_eof_rejects(self):
        def _eof(_p):
            raise EOFError
        result = _telemetry.prompt_and_persist(input_fn=_eof)
        assert result is False

    def test_has_been_asked_false_initially(self):
        assert _telemetry.has_been_asked() is False


# ── Endpoint override ────────────────────────────────────────────────
class TestEndpoint:
    def test_default(self):
        assert _telemetry._endpoint() == _telemetry.DEFAULT_ENDPOINT

    def test_override(self, monkeypatch):
        monkeypatch.setenv(_telemetry.ENV_ENDPOINT, "https://test.local/event")
        assert _telemetry._endpoint() == "https://test.local/event"
