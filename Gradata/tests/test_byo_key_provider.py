from __future__ import annotations

from gradata.llm.byo_key import BYOKeyProvider


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_anthropic_request_body(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _Response(
            {
                "content": [{"type": "text", "text": "Use concrete nouns."}],
                "usage": {"input_tokens": 10, "output_tokens": 4},
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)
    provider = BYOKeyProvider("anthropic", "sk-ant-test", "claude-test")

    assert provider.complete("hello", max_tokens=77, timeout=3) == "Use concrete nouns."
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-ant-test"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"] == {
        "model": "claude-test",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 77,
    }


def test_openai_request_body(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _Response(
            {
                "choices": [{"message": {"content": "Lead with the answer."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5},
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)
    provider = BYOKeyProvider("openai", "sk-proj-test", "gpt-test")

    assert provider.complete("hello", max_tokens=88, timeout=4) == "Lead with the answer."
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-proj-test"
    assert captured["json"] == {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 88,
    }


def test_google_request_body(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _Response(
            {
                "candidates": [{"content": {"parts": [{"text": "Prefer short examples."}]}}],
                "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4},
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)
    provider = BYOKeyProvider("google", "AIza-test", "gemini-test")

    assert provider.complete("hello", max_tokens=99, timeout=5) == "Prefer short examples."
    assert (
        captured["url"]
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "AIza-test"
    assert captured["json"] == {
        "contents": [{"role": "user", "parts": [{"text": "hello"}]}],
        "generationConfig": {"maxOutputTokens": 99},
    }
