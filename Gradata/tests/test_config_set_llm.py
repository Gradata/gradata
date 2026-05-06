from __future__ import annotations

import json

from gradata.cli import main


def test_config_set_llm_cli_writes_config(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["gradata", "config", "set-llm", "cli"])

    main()

    data = json.loads((tmp_path / "brain-config.json").read_text(encoding="utf-8"))
    assert data["llm_mode"] == "cli"
    assert "llm_api_key" not in data
    assert "LLM provider set to cli" in capsys.readouterr().out


def test_config_set_llm_api_writes_explicit_key(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "gradata",
            "config",
            "set-llm",
            "api",
            "--vendor",
            "openai",
            "--key",
            "sk-proj-test",
            "--model",
            "gpt-test",
        ],
    )

    main()

    data = json.loads((tmp_path / "brain-config.json").read_text(encoding="utf-8"))
    assert data["llm_mode"] == "api"
    assert data["llm_vendor"] == "openai"
    assert data["llm_api_key"] == "sk-proj-test"
    assert data["llm_model"] == "gpt-test"


def test_config_set_llm_api_reads_env_key(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.setattr(
        "sys.argv",
        ["gradata", "config", "set-llm", "api", "--vendor", "google"],
    )

    main()

    data = json.loads((tmp_path / "brain-config.json").read_text(encoding="utf-8"))
    assert data["llm_mode"] == "api"
    assert data["llm_vendor"] == "google"
    assert data["llm_api_key"] == "google-test"
