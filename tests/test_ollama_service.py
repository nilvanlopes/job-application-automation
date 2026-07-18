from __future__ import annotations

from types import SimpleNamespace

import pytest

from job_application_automation import ollama_service
from job_application_automation.ollama import OllamaError


def test_managed_ollama_service_stops_configured_compose_when_endpoint_is_ready(monkeypatch, tmp_path):
    compose_file = tmp_path / "docker-compose.ollama.yml"
    compose_file.write_text("services: {}", encoding="utf-8")
    events: list[str] = []
    commands: list[list[str]] = []

    monkeypatch.setattr(
        ollama_service,
        "resolve_ollama_service_config",
        lambda: ollama_service.OllamaServiceConfig(
            base_url="http://localhost:11434/api",
            model_name="qwen2.5:7b",
            email_analysis_model_name="qwen3.5:9b",
            email_model_name="qwen2.5:7b",
            compose_file=compose_file,
            manage_service=True,
            shutdown_when_done=True,
            pull_model_when_missing=True,
            startup_timeout_seconds=1,
            poll_interval_seconds=0,
        ),
    )
    monkeypatch.setattr(
        ollama_service,
        "list_local_models",
        lambda **kwargs: {"models": [{"name": "qwen2.5:7b"}, {"name": "qwen3.5:9b"}]},
    )
    monkeypatch.setattr(
        ollama_service,
        "_run_compose",
        lambda args, **kwargs: commands.append(args),
    )

    with ollama_service.managed_ollama_service(on_event=events.append):
        pass

    assert commands == [["down"]]
    assert events == ["Desligando Ollama local"]


def test_managed_ollama_service_starts_and_stops_when_needed(monkeypatch, tmp_path):
    compose_file = tmp_path / "docker-compose.ollama.yml"
    compose_file.write_text("services: {}", encoding="utf-8")
    events: list[str] = []
    commands: list[list[str]] = []
    ready_calls = {"count": 0}

    def fake_list_local_models(**kwargs):
        ready_calls["count"] += 1
        if ready_calls["count"] == 1:
            raise OllamaError("not ready")
        return {"models": []}

    def fake_runner(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        ollama_service,
        "resolve_ollama_service_config",
        lambda: ollama_service.OllamaServiceConfig(
            base_url="http://localhost:11434/api",
            model_name="qwen2.5:7b",
            email_analysis_model_name="qwen3.5:9b",
            email_model_name="qwen2.5:7b",
            compose_file=compose_file,
            manage_service=True,
            shutdown_when_done=True,
            pull_model_when_missing=True,
            startup_timeout_seconds=1,
            poll_interval_seconds=0,
        ),
    )
    monkeypatch.setattr(ollama_service, "list_local_models", fake_list_local_models)

    with ollama_service.managed_ollama_service(on_event=events.append, runner=fake_runner, sleeper=lambda _: None):
        pass

    assert commands[0][:7] == ["docker", "compose", "-f", str(compose_file), "up", "-d", "ollama"]
    assert commands[1][:8] == ["docker", "compose", "-f", str(compose_file), "exec", "-T", "ollama", "ollama"]
    assert commands[1][8:] == ["pull", "qwen2.5:7b"]
    assert commands[2][:8] == ["docker", "compose", "-f", str(compose_file), "exec", "-T", "ollama", "ollama"]
    assert commands[2][8:] == ["pull", "qwen3.5:9b"]
    assert commands[3][:5] == ["docker", "compose", "-f", str(compose_file), "down"]
    assert "Ollama não estava ativo; subindo container local" in events
    assert "Modelo 'qwen2.5:7b' ausente; baixando via ollama pull" in events
    assert "Modelo 'qwen3.5:9b' ausente; baixando via ollama pull" in events
    assert "Ollama local pronto" in events
    assert "Desligando Ollama local" in events
    assert ready_calls["count"] >= 2


def test_managed_ollama_service_requires_compose_when_start_is_needed(monkeypatch):
    monkeypatch.setattr(
        ollama_service,
        "resolve_ollama_service_config",
        lambda: ollama_service.OllamaServiceConfig(
            base_url="http://localhost:11434/api",
            model_name="qwen2.5:7b",
            email_analysis_model_name="qwen3.5:9b",
            email_model_name="qwen2.5:7b",
            compose_file=None,
            manage_service=True,
            shutdown_when_done=True,
            pull_model_when_missing=True,
            startup_timeout_seconds=1,
            poll_interval_seconds=0,
        ),
    )
    monkeypatch.setattr(
        ollama_service,
        "list_local_models",
        lambda **kwargs: (_ for _ in ()).throw(OllamaError("not ready")),
    )

    with pytest.raises(ollama_service.OllamaServiceError, match="nenhuma configuração de Docker Compose"):
        with ollama_service.managed_ollama_service():
            pass


def test_managed_ollama_service_pulls_missing_models(monkeypatch, tmp_path):
    compose_file = tmp_path / "docker-compose.ollama.yml"
    compose_file.write_text("services: {}", encoding="utf-8")
    events: list[str] = []
    commands: list[list[str]] = []

    monkeypatch.setattr(
        ollama_service,
        "resolve_ollama_service_config",
        lambda: ollama_service.OllamaServiceConfig(
            base_url="http://localhost:11434/api",
            model_name="qwen2.5:7b",
            email_analysis_model_name="qwen3.5:9b",
            email_model_name="qwen2.5:14b-instruct-q3_K_M",
            compose_file=compose_file,
            manage_service=True,
            shutdown_when_done=True,
            pull_model_when_missing=True,
            startup_timeout_seconds=1,
            poll_interval_seconds=0,
        ),
    )
    monkeypatch.setattr(
        ollama_service,
        "list_local_models",
        lambda **kwargs: {"models": [{"name": "another-model"}]},
    )

    def fake_runner(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with ollama_service.managed_ollama_service(on_event=events.append, runner=fake_runner, sleeper=lambda _: None):
        pass

    assert commands[0][:8] == ["docker", "compose", "-f", str(compose_file), "exec", "-T", "ollama", "ollama"]
    assert commands[0][8:] == ["pull", "qwen2.5:7b"]
    assert commands[1][:8] == ["docker", "compose", "-f", str(compose_file), "exec", "-T", "ollama", "ollama"]
    assert commands[1][8:] == ["pull", "qwen3.5:9b"]
    assert commands[2][:8] == ["docker", "compose", "-f", str(compose_file), "exec", "-T", "ollama", "ollama"]
    assert commands[2][8:] == ["pull", "qwen2.5:14b-instruct-q3_K_M"]
    assert commands[3][:5] == ["docker", "compose", "-f", str(compose_file), "down"]
    assert "Modelo 'qwen2.5:7b' ausente; baixando via ollama pull" in events
    assert "Modelo 'qwen3.5:9b' ausente; baixando via ollama pull" in events
    assert "Modelo 'qwen2.5:14b-instruct-q3_K_M' ausente; baixando via ollama pull" in events
    assert "Desligando Ollama local" in events


def test_resolve_ollama_service_config_uses_default_compose_file(monkeypatch):
    monkeypatch.delenv("JOB_APPLICATION_OLLAMA_COMPOSE_FILE", raising=False)
    monkeypatch.delenv("JOB_APPLICATION_OLLAMA_EMAIL_ANALYSIS_MODEL", raising=False)
    monkeypatch.delenv("JOB_APPLICATION_OLLAMA_EMAIL_MODEL", raising=False)
    monkeypatch.setattr(
        ollama_service,
        "_discover_default_compose_file",
        lambda: ollama_service.DEFAULT_LOCAL_OLLAMA_COMPOSE_FILE,
    )
    config = ollama_service.resolve_ollama_service_config()

    assert config.compose_file == ollama_service.DEFAULT_LOCAL_OLLAMA_COMPOSE_FILE
    assert config.email_analysis_model_name == ollama_service.DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL
    assert config.email_model_name == ollama_service.DEFAULT_OLLAMA_EMAIL_MODEL
