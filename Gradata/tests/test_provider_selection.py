from __future__ import annotations

import json

from gradata._config import reload_config
from gradata.enhancements.llm_provider import CLIProvider, get_provider
from gradata.llm.byo_key import BYOKeyProvider


def test_llm_mode_api_picks_byo_key_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GRADATA_LLM_PROVIDER", raising=False)
    (tmp_path / "brain-config.json").write_text(
        json.dumps(
            {
                "llm_mode": "api",
                "llm_vendor": "anthropic",
                "llm_api_key": "sk-ant-test",
                "llm_model": "claude-test",
            }
        ),
        encoding="utf-8",
    )
    reload_config(tmp_path)

    provider = get_provider()

    assert isinstance(provider, BYOKeyProvider)
    assert provider.vendor == "anthropic"
    assert provider.model == "claude-test"
    reload_config(None)


def test_llm_mode_cli_picks_cli_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GRADATA_LLM_PROVIDER", raising=False)
    (tmp_path / "brain-config.json").write_text(
        json.dumps({"llm_mode": "cli"}),
        encoding="utf-8",
    )
    reload_config(tmp_path)

    assert isinstance(get_provider(), CLIProvider)
    reload_config(None)


def test_default_llm_mode_is_cli(monkeypatch) -> None:
    monkeypatch.delenv("GRADATA_LLM_PROVIDER", raising=False)
    reload_config(None)

    assert isinstance(get_provider(), CLIProvider)
