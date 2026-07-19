from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_CONTEXT_LENGTH,
    DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL,
    DEFAULT_OLLAMA_EMAIL_MODEL,
    DEFAULT_OLLAMA_MODEL,
    chat_completion,
)


DEFAULT_PROVIDERS_ORDER = "gemini,openrouter,ollama"
SUPPORTED_PROVIDERS = ("gemini", "openrouter", "openai", "anthropic", "lmstudio", "ollama")


class AIProviderError(RuntimeError):
    pass


class AIProviderConfigError(AIProviderError):
    pass


class AIClient(Protocol):
    def call_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: object | None,
        model_role: str = "default",
        task_label: str = "",
        context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
        think: bool = False,
        request_timeout: float = 60.0,
    ) -> dict:
        ...


@dataclass(frozen=True, slots=True)
class ProviderCandidate:
    name: str
    available: bool
    reason: str = ""


def parse_providers_order(raw: str | None = None) -> tuple[str, ...]:
    value = raw if raw is not None else os.getenv("JOB_APPLICATION_PROVIDERS_ORDER", DEFAULT_PROVIDERS_ORDER)
    providers: list[str] = []
    seen: set[str] = set()
    for item in value.split(","):
        provider = _normalize_provider_name(item)
        if not provider:
            continue
        if provider not in SUPPORTED_PROVIDERS:
            raise AIProviderConfigError(f"Provider de IA inválido: {item.strip()}")
        if provider not in seen:
            seen.add(provider)
            providers.append(provider)
    if not providers:
        raise AIProviderConfigError("Nenhum provider de IA configurado em JOB_APPLICATION_PROVIDERS_ORDER.")
    return tuple(providers)


def create_ai_client(
    *,
    provider: str = "",
    on_event: Callable[[str], None] | None = None,
    opener=urlopen,
) -> "FallbackAIClient":
    forced_provider = _normalize_provider_name(provider)
    providers = (forced_provider,) if forced_provider else parse_providers_order()
    clients: list[tuple[str, AIClient]] = []
    skipped: list[ProviderCandidate] = []
    for provider_name in providers:
        try:
            clients.append((provider_name, _provider_client(provider_name, opener=opener)))
        except AIProviderConfigError as exc:
            if forced_provider:
                raise
            skipped.append(ProviderCandidate(provider_name, available=False, reason=str(exc)))
            if on_event:
                on_event(f"Provider de IA '{provider_name}' indisponível: {exc}")

    if not clients:
        details = "; ".join(f"{item.name}: {item.reason}" for item in skipped)
        raise AIProviderConfigError(f"Nenhum provider de IA disponível. {details}".strip())
    return FallbackAIClient(clients, forced_provider=bool(forced_provider), on_event=on_event)


def providers_need_ollama(provider: str = "") -> bool:
    forced_provider = _normalize_provider_name(provider)
    providers = (forced_provider,) if forced_provider else parse_providers_order()
    return "ollama" in providers


class FallbackAIClient:
    def __init__(
        self,
        clients: list[tuple[str, AIClient]],
        *,
        forced_provider: bool = False,
        on_event: Callable[[str], None] | None = None,
    ) -> None:
        self._clients = clients
        self._forced_provider = forced_provider
        self._on_event = on_event
        self._unavailable: set[str] = set()
        self._last_announced_task: tuple[str, str, str] | None = None

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self._clients)

    def call_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: object | None,
        model_role: str = "default",
        task_label: str = "",
        context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
        think: bool = False,
        request_timeout: float = 60.0,
    ) -> dict:
        errors: list[str] = []
        for name, client in self._clients:
            if name in self._unavailable:
                continue
            model = _client_model_for_role(client, model_role)
            normalized_task_label = task_label.strip()
            current_task = (name, model, normalized_task_label)
            if self._on_event and current_task != self._last_announced_task:
                if normalized_task_label:
                    self._on_event(
                        f"{normalized_task_label} "
                        f"com provider '{name}' e modelo '{model}'"
                    )
                else:
                    self._on_event(f"Gerando IA com provider '{name}' e modelo '{model}'")
                self._last_announced_task = current_task
            try:
                payload = client.call_json(
                    messages,
                    response_format=response_format,
                    model_role=model_role,
                    context_length=context_length,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    think=think,
                    request_timeout=request_timeout,
                )
                _ensure_json_content(payload, name)
                return payload
            except AIProviderError as exc:
                if self._forced_provider:
                    raise
                self._unavailable.add(name)
                errors.append(f"{name}: {exc}")
                if self._on_event:
                    self._on_event(f"Provider de IA '{name}' falhou; tentando próximo: {exc}")
        details = "; ".join(errors) or "todos os providers configurados já estavam indisponíveis"
        raise AIProviderError(f"Nenhum provider de IA conseguiu concluir a chamada. {details}")


class OllamaAIClient:
    def __init__(self, *, opener=urlopen) -> None:
        self._opener = opener

    def call_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: object | None,
        model_role: str = "default",
        task_label: str = "",
        context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
        think: bool = False,
        request_timeout: float = 60.0,
    ) -> dict:
        try:
            return chat_completion(
                messages,
                base_url=os.getenv("JOB_APPLICATION_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
                model=_ollama_model_for_role(model_role),
                response_format=response_format,
                context_length=context_length,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                think=think,
                request_timeout=request_timeout,
                opener=self._opener,
            )
        except Exception as exc:
            raise AIProviderError(str(exc)) from exc

    def model_for_role(self, model_role: str) -> str:
        return _ollama_model_for_role(model_role)


class OpenAICompatibleAIClient:
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        api_key: str,
        model: str,
        extra_payload: dict[str, object] | None = None,
        opener=urlopen,
    ) -> None:
        self._provider_name = provider_name
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._extra_payload = extra_payload or {}
        self._opener = opener

    def call_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: object | None,
        model_role: str = "default",
        task_label: str = "",
        context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
        think: bool = False,
        request_timeout: float = 60.0,
    ) -> dict:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            **self._extra_payload,
        }
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        if response_format is not None:
            payload["response_format"] = {"type": "json_object"}
        request = Request(
            urljoin(_normalize_base_url(self._base_url), "chat/completions"),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        return _post_json(request, timeout=request_timeout, opener=self._opener, provider_name=self._provider_name)

    def model_for_role(self, model_role: str) -> str:
        return self._model


class GeminiAIClient:
    def __init__(self, *, api_key: str, model: str, opener=urlopen) -> None:
        self._api_key = api_key
        self._model = model
        self._opener = opener

    def call_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: object | None,
        model_role: str = "default",
        task_label: str = "",
        context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
        think: bool = False,
        request_timeout: float = 60.0,
    ) -> dict:
        generation_config: dict[str, object] = {
            "temperature": temperature,
            "responseMimeType": "application/json",
        }
        payload: dict[str, object] = {
            "contents": _gemini_contents(messages),
            "generationConfig": generation_config,
        }
        system_instruction = _gemini_system_instruction(messages)
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if max_output_tokens is not None:
            generation_config["maxOutputTokens"] = max_output_tokens
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._api_key}"
        )
        response = _post_json(
            Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=request_timeout,
            opener=self._opener,
            provider_name="gemini",
        )
        text = _gemini_text(response)
        return {"choices": [{"message": {"content": text}}]}

    def model_for_role(self, model_role: str) -> str:
        return self._model


class AnthropicAIClient:
    def __init__(self, *, api_key: str, model: str, opener=urlopen) -> None:
        self._api_key = api_key
        self._model = model
        self._opener = opener

    def call_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: object | None,
        model_role: str = "default",
        task_label: str = "",
        context_length: int | None = DEFAULT_OLLAMA_CONTEXT_LENGTH,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
        think: bool = False,
        request_timeout: float = 60.0,
    ) -> dict:
        anthropic_messages = [item for item in messages if item.get("role") != "system"]
        payload: dict[str, object] = {
            "model": self._model,
            "messages": anthropic_messages,
            "system": "\n\n".join(item.get("content", "") for item in messages if item.get("role") == "system"),
            "temperature": temperature,
            "max_tokens": max_output_tokens or 4096,
        }
        if response_format is not None:
            anthropic_messages.append(
                {
                    "role": "user",
                    "content": "Responda somente com JSON válido, sem Markdown e sem texto fora do JSON.",
                }
            )
        response = _post_json(
            Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            ),
            timeout=request_timeout,
            opener=self._opener,
            provider_name="anthropic",
        )
        text = "".join(
            item.get("text", "")
            for item in response.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        )
        if not text.strip():
            raise AIProviderError("anthropic retornou resposta vazia.")
        return {"choices": [{"message": {"content": text}}]}

    def model_for_role(self, model_role: str) -> str:
        return self._model


def _provider_client(provider_name: str, *, opener=urlopen) -> AIClient:
    if provider_name == "ollama":
        return OllamaAIClient(opener=opener)
    if provider_name == "gemini":
        api_key = _required_env("GOOGLE_API_KEY", provider_name)
        model = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"
        return GeminiAIClient(api_key=api_key, model=model, opener=opener)
    if provider_name == "openrouter":
        api_key = _required_env("OPENROUTER_API_KEY", provider_name)
        model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free").strip()
        if not model:
            raise AIProviderConfigError("OPENROUTER_MODEL é obrigatório para o provider openrouter.")
        if ":free" not in model:
            raise AIProviderConfigError("OPENROUTER_MODEL precisa ser um modelo free (:free).")
        return OpenAICompatibleAIClient(
            provider_name=provider_name,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
            model=model,
            extra_payload={"reasoning": {"effort": "none", "exclude": True}},
            opener=opener,
        )
    if provider_name == "openai":
        return OpenAICompatibleAIClient(
            provider_name=provider_name,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=_required_env("OPENAI_API_KEY", provider_name),
            model=_required_env("OPENAI_MODEL", provider_name),
            opener=opener,
        )
    if provider_name == "lmstudio":
        return OpenAICompatibleAIClient(
            provider_name=provider_name,
            base_url=_required_env("LMSTUDIO_BASE_URL", provider_name),
            api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio").strip() or "lm-studio",
            model=_required_env("LMSTUDIO_MODEL", provider_name),
            opener=opener,
        )
    if provider_name == "anthropic":
        return AnthropicAIClient(
            api_key=_required_env("ANTHROPIC_API_KEY", provider_name),
            model=_required_env("ANTHROPIC_MODEL", provider_name),
            opener=opener,
        )
    raise AIProviderConfigError(f"Provider de IA inválido: {provider_name}")


def _required_env(name: str, provider_name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AIProviderConfigError(f"{name} é obrigatório para o provider {provider_name}.")
    return value


def _normalize_provider_name(provider: str | None) -> str:
    value = (provider or "").strip().lower()
    return "anthropic" if value == "claude" else value


def _client_model_for_role(client: AIClient, model_role: str) -> str:
    model_for_role = getattr(client, "model_for_role", None)
    if callable(model_for_role):
        model = model_for_role(model_role)
        if isinstance(model, str) and model.strip():
            return model.strip()
    return "desconhecido"


def _ensure_json_content(payload: dict, provider_name: str) -> None:
    content = ""
    message = payload.get("message", {})
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        content = message["content"]
    choices = payload.get("choices", [])
    if not content and isinstance(choices, list) and choices:
        choice_message = choices[0].get("message", {})
        if isinstance(choice_message, dict) and isinstance(choice_message.get("content"), str):
            content = choice_message["content"]
    if not content.strip():
        raise AIProviderError(f"{provider_name} retornou texto vazio.")
    try:
        json.loads(content.strip())
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"{provider_name} não retornou JSON válido.") from exc


def _ollama_model_for_role(model_role: str) -> str:
    if model_role == "email_analysis":
        return os.getenv("JOB_APPLICATION_OLLAMA_EMAIL_ANALYSIS_MODEL", DEFAULT_OLLAMA_EMAIL_ANALYSIS_MODEL).strip()
    if model_role == "email_writer":
        return os.getenv("JOB_APPLICATION_OLLAMA_EMAIL_MODEL", DEFAULT_OLLAMA_EMAIL_MODEL).strip()
    return os.getenv("JOB_APPLICATION_OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()


def _post_json(request: Request, *, timeout: float, opener, provider_name: str) -> dict:
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise AIProviderError(f"{provider_name} retornou HTTP {exc.code}: {details}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AIProviderError(f"Falha ao acessar {provider_name}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AIProviderError(f"{provider_name} retornou resposta JSON inválida.") from exc
    _reject_truncated_response(payload, provider_name)
    return payload


def _reject_truncated_response(payload: dict, provider_name: str) -> None:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        finish_reason = choices[0].get("finish_reason")
        if finish_reason in {"length", "max_tokens"}:
            raise AIProviderError(f"{provider_name} truncou a resposta.")
    if payload.get("stop_reason") == "max_tokens":
        raise AIProviderError(f"{provider_name} truncou a resposta.")


def _normalize_base_url(base_url: str) -> str:
    resolved = base_url.strip()
    if not resolved.endswith("/"):
        resolved = f"{resolved}/"
    return resolved


def _gemini_system_instruction(messages: list[dict[str, str]]) -> str:
    return "\n\n".join(item.get("content", "") for item in messages if item.get("role") == "system").strip()


def _gemini_contents(messages: list[dict[str, str]]) -> list[dict[str, object]]:
    contents: list[dict[str, object]] = []
    for message in messages:
        if message.get("role") == "system":
            continue
        role = "model" if message.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})
    return contents


def _gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise AIProviderError("gemini retornou resposta vazia.")
    finish_reason = candidates[0].get("finishReason")
    if finish_reason in {"MAX_TOKENS", "SAFETY", "RECITATION"}:
        raise AIProviderError(f"gemini interrompeu a resposta: {finish_reason}.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(item.get("text", "") for item in parts if isinstance(item, dict))
    if not text.strip():
        raise AIProviderError("gemini retornou texto vazio.")
    return text
