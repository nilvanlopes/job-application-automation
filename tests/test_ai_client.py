from __future__ import annotations

import json

import pytest

from job_application_automation.ai_client import (
    AIProviderConfigError,
    AIProviderError,
    FallbackAIClient,
    OllamaAIClient,
    create_ai_client,
    parse_providers_order,
    providers_need_ollama,
)
from job_application_automation.ollama import DEFAULT_OLLAMA_MODEL


class FakeClient:
    def __init__(self, results, model: str = "fake-model"):
        self.results = list(results)
        self.model = model
        self.calls = 0

    def call_json(self, messages, **kwargs):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return {"choices": [{"message": {"content": json.dumps(result)}}]}

    def model_for_role(self, model_role: str) -> str:
        return f"{self.model}:{model_role}"


class FakeRawClient:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def call_json(self, messages, **kwargs):
        self.calls += 1
        return {"choices": [{"message": {"content": self.content}}]}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_parse_providers_order_normalizes_aliases_and_deduplicates():
    assert parse_providers_order(" Gemini, claude, anthropic, OLLAMA, gemini ") == (
        "gemini",
        "anthropic",
        "ollama",
    )


def test_parse_providers_order_rejects_invalid_provider():
    with pytest.raises(AIProviderConfigError, match="Provider de IA inválido"):
        parse_providers_order("gemini,invalid")


def test_default_provider_order_is_job_application_specific(monkeypatch):
    monkeypatch.delenv("JOB_APPLICATION_PROVIDERS_ORDER", raising=False)
    monkeypatch.setenv("PROVIDERS_ORDER", "openai")

    assert parse_providers_order() == ("gemini", "openrouter", "ollama")


def test_create_ai_client_skips_missing_cloud_config_and_keeps_ollama(monkeypatch):
    events = []
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("JOB_APPLICATION_PROVIDERS_ORDER", "gemini,openrouter,ollama")

    client = create_ai_client(on_event=events.append)

    assert client.provider_names == ("ollama",)
    assert any("gemini" in event for event in events)
    assert any("openrouter" in event for event in events)


def test_forced_provider_config_error_is_fatal(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(AIProviderConfigError, match="GOOGLE_API_KEY"):
        create_ai_client(provider="gemini")


def test_openrouter_requires_free_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_MODEL", "paid/model")

    with pytest.raises(AIProviderConfigError, match="free"):
        create_ai_client(provider="openrouter")


def test_fallback_runtime_error_tries_next_and_marks_failed_provider_unavailable():
    first = FakeClient([AIProviderError("quota"), {"ok": False}])
    second = FakeClient([{"ok": True}, {"ok": True}])
    events = []
    client = FallbackAIClient([("gemini", first), ("ollama", second)], on_event=events.append)

    assert client.call_json([], response_format={})["choices"][0]["message"]["content"] == '{"ok": true}'
    assert client.call_json([], response_format={})["choices"][0]["message"]["content"] == '{"ok": true}'
    assert first.calls == 1
    assert second.calls == 2
    assert events.count("Gerando IA com provider 'gemini' e modelo 'fake-model:default'") == 1
    assert events.count("Gerando IA com provider 'ollama' e modelo 'fake-model:default'") == 1
    assert any("gemini" in event and "tentando próximo" in event for event in events)


def test_fallback_announces_task_label_with_provider_and_model():
    client = FallbackAIClient(
        [("ollama", FakeClient([{"ok": True}], model="qwen3.5"))],
        on_event=(events := []).append,
    )

    client.call_json(
        [],
        response_format={},
        model_role="email_analysis",
        task_label="Revisando e-mail de candidatura",
    )

    assert events == [
        "Revisando e-mail de candidatura "
        "com provider 'ollama' e modelo 'qwen3.5:email_analysis'"
    ]


def test_fallback_invalid_json_tries_next_provider():
    first = FakeRawClient("thinking... sem JSON")
    second = FakeClient([{"ok": True}])
    client = FallbackAIClient([("openrouter", first), ("ollama", second)])

    payload = client.call_json([], response_format={})

    assert json.loads(payload["choices"][0]["message"]["content"]) == {"ok": True}
    assert first.calls == 1
    assert second.calls == 1


def test_forced_provider_does_not_fallback():
    first = FakeClient([AIProviderError("offline")])
    second = FakeClient([{"ok": True}])
    client = FallbackAIClient([("gemini", first), ("ollama", second)], forced_provider=True)

    with pytest.raises(AIProviderError, match="offline"):
        client.call_json([], response_format={})

    assert second.calls == 0


def test_providers_need_ollama_respects_order_and_forced_provider(monkeypatch):
    monkeypatch.setenv("JOB_APPLICATION_PROVIDERS_ORDER", "gemini,openrouter")

    assert providers_need_ollama("") is False
    assert providers_need_ollama("ollama") is True


def test_ollama_adapter_sends_native_payload(monkeypatch):
    captured = {}
    monkeypatch.delenv("JOB_APPLICATION_OLLAMA_MODEL", raising=False)

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"message": {"content": '{"ok": true}'}})

    client = OllamaAIClient(opener=opener)
    payload = client.call_json(
        [{"role": "user", "content": "responda JSON"}],
        response_format={"type": "object"},
        context_length=2048,
        temperature=0.2,
        request_timeout=12,
    )

    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["model"] == DEFAULT_OLLAMA_MODEL
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["think"] is False
    assert captured["payload"]["format"] == {"type": "object"}
    assert captured["payload"]["options"]["num_ctx"] == 2048
    assert captured["payload"]["options"]["temperature"] == 0.2
    assert payload["message"]["content"] == '{"ok": true}'
