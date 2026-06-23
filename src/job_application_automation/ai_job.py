from __future__ import annotations

import json

from .json_utils import parse_strict_json_object
from .models import JobPosting
from .ollama import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL, OllamaError, chat_completion


class AIJobExtractionError(RuntimeError):
    pass


def extract_job_with_ai(
    text: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout: float = 90.0,
    opener=None,
) -> JobPosting:
    baseline = JobPosting.from_text(text)
    resolved_model = (model or DEFAULT_OLLAMA_MODEL).strip()
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    try:
        response_payload = chat_completion(
            _build_messages(baseline.raw_text),
            base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
            model=resolved_model,
            response_format=_schema(),
            request_timeout=request_timeout,
            **kwargs,
        )
    except OllamaError as exc:
        raise AIJobExtractionError(str(exc)) from exc

    content = _extract_output_text(response_payload)
    _log_ai_output(content)
    try:
        data = parse_strict_json_object(content)
    except json.JSONDecodeError as exc:
        raise AIJobExtractionError(
            f"A IA não retornou JSON válido para a vaga. Resposta bruta: {content.strip()}"
        ) from exc

    return JobPosting(
        raw_text=baseline.raw_text,
        title=_string(data.get("title")),
        company=_string(data.get("company")),
        location=_string(data.get("location")),
        work_model=_string(data.get("work_model")),
        contact_email=_string(data.get("contact_email")),
        contact_whatsapp=_string(data.get("contact_whatsapp")),
        description=_string(data.get("description")),
        requirements=_strings(data.get("requirements")),
        nice_to_have=_strings(data.get("nice_to_have")),
        benefits=_strings(data.get("benefits")),
        keywords=_strings(data.get("keywords")),
    )


def _build_messages(raw_text: str) -> list[dict[str, str]]:
    system_content = (
        "Você estrutura anúncios de vagas em português do Brasil. Analise somente o texto "
        "fornecido, corrija ruídos evidentes de OCR e preencha os campos relevantes. "
        "Não invente empresa, contato, requisitos, benefícios ou tecnologias. Use string "
        "vazia ou lista vazia quando a informação não estiver presente. Preserve e-mails e "
        "telefones exatamente como aparecem. O título deve conter somente o nome do cargo."
    )
    return [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": json.dumps(
                {"objetivo": "Estruturar os dados da vaga", "texto_extraido": raw_text},
                ensure_ascii=False,
            ),
        },
    ]


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "location": {"type": "string"},
            "work_model": {"type": "string"},
            "contact_email": {"type": "string"},
            "contact_whatsapp": {"type": "string"},
            "description": {"type": "string"},
            "requirements": {"type": "array", "items": {"type": "string"}},
            "nice_to_have": {"type": "array", "items": {"type": "string"}},
            "benefits": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "title",
            "company",
            "location",
            "work_model",
            "contact_email",
            "contact_whatsapp",
            "description",
            "requirements",
            "nice_to_have",
            "benefits",
            "keywords",
        ],
        "additionalProperties": False,
    }


def _extract_output_text(payload: dict) -> str:
    message = payload.get("message", {})
    if isinstance(message, dict):
        if message.get("refusal"):
            raise AIJobExtractionError(f"A IA recusou a estruturação: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        if message.get("refusal"):
            raise AIJobExtractionError(f"A IA recusou a estruturação: {message['refusal']}")
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise AIJobExtractionError("O Ollama não retornou texto para a vaga.")


def _log_ai_output(content: str) -> None:
    if content.strip():
        print("[job-application] Resposta bruta da IA na estruturação da vaga:", flush=True)
        print(content.strip(), flush=True)


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
