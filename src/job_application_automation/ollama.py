from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/api"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL = "qwen3.5:9b"
DEFAULT_OLLAMA_EMAIL_MODEL = DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL
DEFAULT_OLLAMA_CONTEXT_LENGTH = 32768


class OllamaError(RuntimeError):
    pass


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    base_url: str | None = None,
    response_format: object | None = None,
    context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
    max_output_tokens: int | None = None,
    temperature: float = 0.0,
    think: bool | str = False,
    request_timeout: float = 60.0,
    opener=urlopen,
) -> dict:
    options: dict[str, object] = {"temperature": temperature}
    if context_length is not None:
        options["num_ctx"] = context_length
    if max_output_tokens is not None:
        options["num_predict"] = max_output_tokens
    payload: dict[str, object] = {
        "model": (model or DEFAULT_OLLAMA_MODEL).strip(),
        "messages": messages,
        "stream": False,
        "think": think,
        "options": options,
    }
    if response_format is not None:
        payload["format"] = response_format

    request = Request(
        _chat_url(base_url),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(f"Ollama retornou HTTP {exc.code}: {details}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise OllamaError(f"Falha ao acessar o Ollama: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise OllamaError("O Ollama retornou uma resposta JSON inválida.") from exc


def list_local_models(
    *,
    base_url: str | None = None,
    request_timeout: float = 30.0,
    opener=urlopen,
) -> dict:
    request = Request(_tags_url(base_url), method="GET")
    try:
        with opener(request, timeout=request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(f"Ollama retornou HTTP {exc.code}: {details}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise OllamaError(f"Falha ao acessar o Ollama: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise OllamaError("O Ollama retornou uma resposta JSON inválida.") from exc


def _chat_url(base_url: str | None) -> str:
    return urljoin(_normalize_base_url(base_url), "chat")


def _tags_url(base_url: str | None) -> str:
    return urljoin(_normalize_base_url(base_url), "tags")


def _normalize_base_url(base_url: str | None) -> str:
    resolved = (base_url or DEFAULT_OLLAMA_BASE_URL).strip()
    if not resolved:
        resolved = DEFAULT_OLLAMA_BASE_URL
    if not resolved.endswith("/"):
        resolved = f"{resolved}/"
    return resolved
