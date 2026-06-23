from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from .ollama import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OllamaError, list_local_models


DEFAULT_SHARED_OLLAMA_COMPOSE_FILE = Path("/home/pyu/docker/ollama/docker-compose.yml")
DEFAULT_LOCAL_OLLAMA_COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.ollama.yml"


class OllamaServiceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OllamaServiceConfig:
    base_url: str
    model_name: str
    compose_file: Path | None
    manage_service: bool
    shutdown_when_done: bool
    pull_model_when_missing: bool
    startup_timeout_seconds: float
    poll_interval_seconds: float


def resolve_ollama_service_config() -> OllamaServiceConfig:
    compose_file_raw = os.getenv("JOB_APPLICATION_OLLAMA_COMPOSE_FILE")
    if compose_file_raw is None or not compose_file_raw.strip():
        compose_file = _discover_default_compose_file()
    else:
        compose_file_value = compose_file_raw.strip()
        if compose_file_value.lower() in {"none", "null", "off", "false"}:
            compose_file = None
        else:
            compose_file = Path(compose_file_value).expanduser()

    return OllamaServiceConfig(
        base_url=os.getenv("JOB_APPLICATION_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip() or DEFAULT_OLLAMA_BASE_URL,
        model_name=os.getenv("JOB_APPLICATION_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL,
        compose_file=compose_file,
        manage_service=_read_bool_env("JOB_APPLICATION_OLLAMA_MANAGE_SERVICE", default=True),
        shutdown_when_done=_read_bool_env("JOB_APPLICATION_OLLAMA_SHUTDOWN_WHEN_DONE", default=True),
        pull_model_when_missing=_read_bool_env("JOB_APPLICATION_OLLAMA_PULL_MODEL_WHEN_MISSING", default=True),
        startup_timeout_seconds=float(os.getenv("JOB_APPLICATION_OLLAMA_STARTUP_TIMEOUT_SECONDS", "180")),
        poll_interval_seconds=float(os.getenv("JOB_APPLICATION_OLLAMA_POLL_INTERVAL_SECONDS", "2")),
    )


def _discover_default_compose_file() -> Path:
    if DEFAULT_SHARED_OLLAMA_COMPOSE_FILE.exists():
        return DEFAULT_SHARED_OLLAMA_COMPOSE_FILE
    return DEFAULT_LOCAL_OLLAMA_COMPOSE_FILE


@contextmanager
def managed_ollama_service(
    *,
    on_event: Callable[[str], None] | None = None,
    runner: Callable[..., object] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> Iterator[None]:
    config = resolve_ollama_service_config()
    if not config.manage_service:
        yield
        return

    if _is_ollama_ready(config.base_url):
        if config.pull_model_when_missing:
            _ensure_model_available(
                model_name=config.model_name,
                base_url=config.base_url,
                compose_file=config.compose_file,
                runner=runner,
                on_event=on_event,
            )
        yield
        return

    if config.compose_file is None:
        raise OllamaServiceError(
            "Ollama não está disponível e nenhuma configuração de Docker Compose foi fornecida."
        )

    if not config.compose_file.exists():
        raise OllamaServiceError(f"docker-compose do Ollama não encontrado: {config.compose_file}")

    started_by_us = False
    try:
        if on_event:
            on_event("Ollama não estava ativo; subindo container local")
        _run_compose(
            ["up", "-d", "ollama"],
            compose_file=config.compose_file,
            runner=runner,
        )
        started_by_us = True
        _wait_until_ready(
            base_url=config.base_url,
            timeout_seconds=config.startup_timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
            sleeper=sleeper,
        )
        if config.pull_model_when_missing:
            _ensure_model_available(
                model_name=config.model_name,
                base_url=config.base_url,
                compose_file=config.compose_file,
                runner=runner,
                on_event=on_event,
            )
        if on_event:
            on_event("Ollama local pronto")
        yield
    finally:
        if started_by_us and config.shutdown_when_done:
            if on_event:
                on_event("Desligando Ollama local")
            _run_compose(
                ["down"],
                compose_file=config.compose_file,
                runner=runner,
            )


def _is_ollama_ready(base_url: str) -> bool:
    try:
        list_local_models(base_url=base_url, request_timeout=5.0)
        return True
    except OllamaError:
        return False


def _wait_until_ready(
    *,
    base_url: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
    sleeper: Callable[[float], None],
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None

    while time.monotonic() < deadline:
        try:
            list_local_models(base_url=base_url, request_timeout=5.0)
            return
        except OllamaError as exc:
            last_error = str(exc)
            sleeper(poll_interval_seconds)

    raise OllamaServiceError(
        f"Ollama não ficou pronto dentro de {timeout_seconds:.0f}s. Último erro: {last_error or 'indisponível'}"
    )


def _ensure_model_available(
    *,
    model_name: str,
    base_url: str,
    compose_file: Path | None,
    runner: Callable[..., object],
    on_event: Callable[[str], None] | None,
) -> None:
    models_payload = list_local_models(base_url=base_url, request_timeout=15.0)
    if _model_is_present(models_payload, model_name):
        return

    if compose_file is None:
        raise OllamaServiceError(
            f"O modelo '{model_name}' não está disponível e não foi possível executá-lo sem Docker Compose."
        )

    if on_event:
        on_event(f"Modelo '{model_name}' ausente; baixando via ollama pull")
    _run_compose(
        ["exec", "-T", "ollama", "ollama", "pull", model_name],
        compose_file=compose_file,
        runner=runner,
    )


def _model_is_present(models_payload: dict, model_name: str) -> bool:
    models = models_payload.get("models", [])
    if not isinstance(models, list):
        return False

    target = model_name.strip().lower()
    if not target:
        return False

    for item in models:
        if not isinstance(item, dict):
            continue
        names = [
            item.get("name"),
            item.get("model"),
            item.get("digest"),
        ]
        for name in names:
            if isinstance(name, str) and name.strip().lower() == target:
                return True
    return False


def _run_compose(
    args: list[str],
    *,
    compose_file: Path,
    runner: Callable[..., object],
) -> None:
    completed = runner(
        ["docker", "compose", "-f", str(compose_file), *args],
        cwd=compose_file.parent,
        stdout=None,
        stderr=None,
        timeout=600,
    )
    if getattr(completed, "returncode", 0) != 0:
        raise OllamaServiceError(f"Falha ao executar docker compose {' '.join(args)} para o Ollama.")


def _read_bool_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default
